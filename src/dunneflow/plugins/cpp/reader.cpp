// The C and C++ reader, on the far side of a pipe, on libclang.
//
// `plugins/go/main.go` is the worked example this follows, and the two agree on every rule
// that matters:
//
// **stdout carries protocol and nothing else.** Every sentence goes to stderr, which the
// host drains into a ring buffer and never parses.
//
// **Every reply echoes the request's `id`.** The host correlates on it.
//
// **A file that will not parse is `facts` with an error, and a file that made this reader
// throw is `failed`**: only the second lets the host write the record, because a reader that
// has just crashed on a file is not the right authority on what that file is.
//
// **The work is done ahead, in parallel, and bounded.** The host asks for one file at a
// time, in the order it sent them in `open`, and a parse with a real tree's headers is
// hundreds of milliseconds. So `open` starts one thread per core, each with its own
// `CXIndex`, parsing every file in that order, and `extract` answers from what they have
// done. Finished facts are held for a bounded window only: a file the host skips (a cache
// hit) is dropped when the host asks for a later one, and one it then asks for after all is
// parsed again on the spot. What the edge pass needs is kept for every file, compactly.
//
// Built as one translation unit: `clang++ -std=c++17 -O2 -Ivendor -o {output} reader.cpp`.

#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <deque>
#include <filesystem>
#include <iostream>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "src/clang.hpp"
#include "src/config.hpp"
#include "src/edges.hpp"
#include "src/extract.hpp"
#include "src/facts.hpp"
#include "src/ids.hpp"
#include "src/json.hpp"
#include "src/rules.hpp"
#include "src/selftest.hpp"
#include "src/text.hpp"

namespace {

constexpr int PROTOCOL = 1;
// `plugin.json`'s, and the handshake refuses the language if they differ.
const char* VERSION = "2.0.0";

std::mutex out_mu;

void send(const std::string& frame) {
    std::lock_guard<std::mutex> g(out_mu);
    std::fwrite(frame.data(), 1, frame.size(), stdout);
    std::fputc('\n', stdout);
    std::fflush(stdout);
}

void note(const std::string& s) {
    std::fprintf(stderr, "%s\n", s.c_str());
    std::fflush(stderr);
}

std::string id_json(const json::Value& id) {
    if (id.kind == json::Value::Number) return std::to_string(id.i);
    if (id.is_string()) {
        std::string s;
        json::write_string(s, id.s);
        return s;
    }
    return "null";
}

std::string error_frame(const json::Value& id, const std::string& reason) {
    std::string f = "{\"t\":\"error\",\"id\":" + id_json(id) + ",\"reason\":";
    json::write_string(f, reason);
    return f + "}";
}

namespace fs = std::filesystem;

std::string generic(const std::string& p) { return fs::path(p).lexically_normal().generic_string(); }

// ---------------------------------------------------------------- the session --- //

enum State { PENDING, RUNNING, HELD, DROPPED };

struct Session {
    std::string root;
    std::vector<std::string> files;          // absolute, as the host sent them
    std::map<std::string, size_t> index;     // generic absolute path -> position
    rules::Rules rules;
    config::Session cfg;

    std::mutex mu;
    std::condition_variable cv;
    std::vector<State> state;
    std::map<size_t, extract::Result> held;  // finished and not yet asked for
    size_t next = 0;                         // the next file a worker takes
    size_t done = 0;
    size_t window = 64;
    bool edges_wanted = false;               // no more facts will be asked for
    bool stopping = false;
    std::vector<std::thread> workers;
    edges::Tree tree;                        // what every parse found for the edge pass
    std::vector<std::string> opened_notes;

    std::string rel(const std::string& abs) const {
        std::string g = generic(abs);
        if (g.size() > root.size() && g.compare(0, root.size(), root) == 0 && g[root.size()] == '/')
            return g.substr(root.size() + 1);
        return g;  // outside the root: stored as given, which the host records
    }

    void parse(CXIndex index, size_t i, extract::Result& r) {
        const std::string& abs = files[i];
        std::string t;
        if (!text::read_source(abs, t)) {
            r.failed = "could not be read";
            return;
        }
        try {
            read_one(index, abs, t, r);
        } catch (const std::exception& e) {
            r.failed = std::string("the reader failed on it: ") + e.what();
            r.facts_json.clear();
        }
    }

    // A fragment is read through the first of its includers whose parse reaches it, and alone
    // only when none does -- nothing includes it, or every includer has it under an inactive
    // `#if`. Anything else is read alone, as it always was.
    void read_one(CXIndex index, const std::string& abs, const std::string& t, extract::Result& r) {
        auto it = cfg.includers.find(abs);
        if (it != cfg.includers.end()) {
            for (const auto& via : it->second) {
                extract::Result tried;
                extract::read(index, abs, rel(abs), t, cfg.args_for(via), rules, tried, via, rel(via));
                if (tried.not_included) continue;
                r = std::move(tried);
                r.fragment = true;
                return;
            }
        }
        extract::read(index, abs, rel(abs), t, cfg.args_for(abs), rules, r);
        r.fragment = config::is_fragment(abs);
    }

    void work() {
        CXIndex index = clang::api().clang_createIndex(0, 0);
        for (;;) {
            size_t i;
            {
                std::unique_lock<std::mutex> g(mu);
                cv.wait(g, [&] { return stopping || next >= files.size() || edges_wanted || held.size() < window; });
                if (stopping || next >= files.size()) break;
                i = next++;
                state[i] = RUNNING;
            }
            extract::Result r;
            parse(index, i, r);
            {
                std::lock_guard<std::mutex> g(mu);
                tree.add(r);
                done++;
                if (edges_wanted) {
                    state[i] = DROPPED;
                } else {
                    r.sites.clear();
                    r.defs.clear();
                    r.overs.clear();
                    r.bases.clear();
                    held.emplace(i, std::move(r));
                    state[i] = HELD;
                }
            }
            cv.notify_all();
        }
        clang::api().clang_disposeIndex(index);
    }

    void start() {
        state.assign(files.size(), PENDING);
        unsigned n = std::thread::hardware_concurrency();
        if (const char* env = std::getenv("DUNNEFLOW_CPP_THREADS"); env && *env) n = static_cast<unsigned>(std::atoi(env));
        if (n == 0) n = 1;
        window = std::max<size_t>(64, 4 * n);
        for (unsigned k = 0; k < n; k++) workers.emplace_back([this] { work(); });
    }

    void stop() {
        {
            std::lock_guard<std::mutex> g(mu);
            stopping = true;
        }
        cv.notify_all();
        for (auto& w : workers)
            if (w.joinable()) w.join();
        workers.clear();
    }

    // The facts for one file, from the pool when it has them and from a parse here when it
    // dropped them. False with `why` when it could not be read at all.
    bool facts_for(size_t i, extract::Result& out) {
        {
            std::unique_lock<std::mutex> g(mu);
            // The host asks in `open` order, so every held file before this one was a file it
            // does not want (a cache hit). Dropping them is what keeps the window moving.
            for (auto it = held.begin(); it != held.end() && it->first < i;) {
                state[it->first] = DROPPED;
                it = held.erase(it);
            }
            cv.notify_all();
            cv.wait(g, [&] { return state[i] == HELD || state[i] == DROPPED || stopping; });
            auto it = held.find(i);
            if (it != held.end()) {
                out = std::move(it->second);
                held.erase(it);
                state[i] = DROPPED;
                cv.notify_all();
                return true;
            }
        }
        // Asked out of order, or after it was dropped: read again, here.
        CXIndex index = clang::api().clang_createIndex(0, 0);
        parse(index, i, out);
        clang::api().clang_disposeIndex(index);
        return true;
    }

    void wait_all() {
        std::unique_lock<std::mutex> g(mu);
        edges_wanted = true;
        held.clear();
        cv.notify_all();
        cv.wait(g, [&] { return done >= files.size() || stopping; });
    }
};

Session* session = nullptr;

std::string hello() {
    std::string f = "{\"t\":\"ready\",\"lang\":\"cpp\",\"version\":";
    json::write_string(f, VERSION);
    f += ",\"protocol\":" + std::to_string(PROTOCOL) + ",\"schema_version\":" +
         std::to_string(facts::SCHEMA_VERSION) +
         ",\"capabilities\":{\"supplies_edges\":" + std::string(edges::SUPPLIES ? "true" : "false") +
         ",\"supplies_bindings\":true,\"reports_literals\":true}";
    return f;
}

std::string open(const json::Value& f) {
    if (session) {
        session->stop();
        delete session;
    }
    session = new Session();
    Session& s = *session;
    s.root = generic(fs::absolute(fs::path(f["root"].str())).string());
    for (const auto& x : f["files"].list()) {
        if (!x.is_string()) continue;
        std::string abs = generic(fs::absolute(fs::path(x.s)).string());
        s.index[abs] = s.files.size();
        s.files.push_back(abs);
    }
    std::vector<std::string> notes;
    s.rules = rules::parse(f["rules"], notes);
    s.cfg = config::decide(s.root, s.files, s.rules);
    notes.insert(notes.end(), s.cfg.notes.begin(), s.cfg.notes.end());
    notes.push_back("libclang: " + clang::api().version + " (" + clang::api().path + ")");
    for (const auto& n : notes) note(n);
    s.tree.read_beyond = s.cfg.read_beyond;
    for (const auto& p : s.rules.presets)
        if (p.name == s.cfg.preset) s.tree.body_rules = p.bodies;
    s.start();

    std::string out = "{\"t\":\"opened\",\"files\":" + std::to_string(s.files.size()) + ",\"diagnostics\":";
    json::write(out, notes);
    return out;
}

std::string extract_reply(const json::Value& f) {
    if (!session) return "{\"t\":\"failed\",\"reason\":\"extract before open\"";
    std::string abs = generic(fs::absolute(fs::path(f["path"].str())).string());
    auto it = session->index.find(abs);
    extract::Result r;
    if (it == session->index.end()) {
        // Not one of the files `open` named: read it here, alone.
        std::string t;
        if (!text::read_source(abs, t)) return "{\"t\":\"failed\",\"reason\":\"could not be read\"";
        CXIndex index = clang::api().clang_createIndex(0, 0);
        try {
            session->read_one(index, abs, t, r);
        } catch (const std::exception& e) {
            r.failed = e.what();
            r.facts_json.clear();
        }
        clang::api().clang_disposeIndex(index);
    } else {
        session->facts_for(it->second, r);
    }
    if (r.facts_json.empty()) {
        std::string out = "{\"t\":\"failed\",\"reason\":";
        json::write_string(out, r.failed.empty() ? "no facts" : r.failed);
        return out;
    }
    std::string out = "{\"t\":\"facts\",\"hash\":";
    json::write_string(out, r.hash);
    out += ",\"facts\":" + r.facts_json;
    return out;
}

void edges_reply(const json::Value& id) {
    if (!session) {
        send("{\"t\":\"edges_done\",\"id\":" + id_json(id) + ",\"supplied\":0,\"outside\":0,\"unknown\":0}");
        return;
    }
    session->wait_all();
    edges::emit(
        session->tree,
        [&](const std::string& edge) { send("{\"t\":\"edge\",\"id\":" + id_json(id) + ",\"edge\":" + edge + "}"); },
        [&](const std::string& done) { send("{\"t\":\"edges_done\",\"id\":" + id_json(id) + "," + done + "}"); },
        [&](const std::string& b) { send("{\"t\":\"binding\",\"id\":" + id_json(id) + ",\"binding\":" + b + "}"); });
}

void handle(const std::string& line) {
    json::Value f;
    try {
        f = json::parse(line);
    } catch (const std::exception& e) {
        note(std::string("unreadable frame: ") + line.substr(0, 120));
        return;
    }
    const json::Value& id = f["id"];
    std::string t = f["t"].str();
    try {
        if (t == "close") {
            send("{\"t\":\"closed\",\"id\":" + id_json(id) + "}");
            if (session) session->stop();
            std::exit(0);
        }
        if (t == "edges") return edges_reply(id);
        std::string reply;
        if (t == "hello") reply = hello();
        else if (t == "open") reply = open(f);
        else if (t == "extract") reply = extract_reply(f);
        else {
            send(error_frame(id, "this reader does not know the frame `" + t + "`"));
            return;
        }
        // Every reply is an object missing its closing brace and its id.
        send(reply + ",\"id\":" + id_json(id) + "}");
    } catch (const std::exception& e) {
        send(error_frame(id, e.what()));
    }
}

}  // namespace

int main(int argc, char** argv) {
    // The protocol's own text: no locale, no translation of newlines.
    std::ios::sync_with_stdio(false);
    if (argc >= 3 && std::string(argv[1]) == "--self-test") return selftest::run(argv[2]);

    std::string why = clang::load();
    if (!why.empty()) {
        // Said once, here, and to every frame: a reader that cannot reach libclang reads
        // nothing, and must not look like one that read an empty tree.
        note(why);
        std::string line;
        while (std::getline(std::cin, line)) {
            if (line.empty()) continue;
            json::Value f;
            try {
                f = json::parse(line);
            } catch (...) {
                continue;
            }
            if (f["t"].str() == "close") {
                send("{\"t\":\"closed\",\"id\":" + id_json(f["id"]) + "}");
                return 0;
            }
            if (f["t"].str() == "hello") {
                std::string d = "{\"t\":\"declined\",\"id\":" + id_json(f["id"]) + ",\"reason\":";
                json::write_string(d, why);
                send(d + "}");
                continue;
            }
            send(error_frame(f["id"], why));
        }
        return 0;
    }

    std::string line;
    while (std::getline(std::cin, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.find_first_not_of(" \t") == std::string::npos) continue;
        handle(line);
    }
    if (session) session->stop();
    return 0;
}
