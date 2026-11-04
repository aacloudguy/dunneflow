// Every call's far end, decided once every file has been parsed.
//
// **What crosses a file is a name, never clang's identity** — Java's lesson, met first in its
// batches: each parse's cursors die with its translation unit, so every parse writes down
// what it found by USR, clang's own string identity for a declaration, and the decision is
// made here over the whole tree once every parse is done. A definition in a header is found
// by the header's own parse, so every definition is named once, by the file it is in.
//
// **Tom's dispatch rule (2026-11-01, Java's), in C++'s terms.** An edge is CERTAIN where
// nothing else can answer: a free function, a non-virtual or `final` method, a method of a
// `final` class, a constructor, a call clang says is not dynamic (`Base::f()`, or a call on
// an object rather than through a pointer or reference), or a virtual method nothing in the
// tree overrides. Otherwise the call is `dynamic`, with every body that may answer it named
// (`SuppliedEdge.answers`), and an override counts only where its class is a subtype of the
// receiver's static type — a sibling's override can never answer (Java, 233f6f7).
//
// **The stops, each said** (`calls.reason`):
//   - `outside`: the declaration has no definition in this tree; its qualified name is the
//     frontier.
//   - `untyped`: the call is written and clang kept nothing to say what it reaches — a
//     statement it could not make sense of, usually for want of a header (rule 1).
//   - `bound`: a call through a function pointer, a `std::function` or a member holding one.
//   - `unfollowed`, with the macro's name as the frontier: a function-like macro that
//     expands to no call (`N_("x")`, `OPT_BOOL(...)`), which is Rust's word for its own
//     `macro_rules!`. One that expands to a call is that call's edge.

#pragma once

#include <algorithm>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <tuple>
#include <vector>

#include "extract.hpp"
#include "facts.hpp"
#include "json.hpp"

namespace edges {

constexpr bool SUPPLIES = true;

struct Tree {
    std::vector<extract::Site> sites;
    std::vector<extract::Def> defs;
    std::vector<extract::Over> overs;
    std::vector<std::pair<std::string, std::string>> bases;
    std::vector<std::string> read_beyond;
    long fatal_files = 0, missing_files = 0, files = 0, skipped_lines = 0;
    std::map<std::string, long> missing;  // first missing include, per file that had one
    long fragments_through = 0;
    std::vector<std::string> fragments_alone;  // read alone: nothing that is read reaches them

    void add(extract::Result& r) {
        files++;
        if (r.fatal) fatal_files++;
        // Counted by what clang said, not by its severity: under `KeepGoing` an include not
        // found is an error in one file and a fatal error in the next, and a count of
        // fatals alone said nothing of nmap's 300 files missing OS/400's `qadrt.h`.
        if (!r.first_missing.empty()) missing_files++;
        skipped_lines += r.skipped_lines;
        if (!r.first_missing.empty()) missing[r.first_missing]++;
        if (r.fragment) {
            if (!r.through.empty()) fragments_through++;
            else fragments_alone.push_back(r.rel);
        }
        for (auto& s : r.sites) sites.push_back(std::move(s));
        for (auto& d : r.defs) defs.push_back(std::move(d));
        for (auto& o : r.overs) overs.push_back(std::move(o));
        for (auto& b : r.bases) bases.push_back(std::move(b));
    }
};

struct Where {
    std::string file, name;
    long line = 0;
    bool invalid = false;
    bool operator<(const Where& o) const {
        return std::tie(file, line, name) < std::tie(o.file, o.line, o.name);
    }
    bool operator==(const Where& o) const { return file == o.file && line == o.line && name == o.name; }
};

inline void emit(Tree& t, const std::function<void(const std::string&)>& edge,
                 const std::function<void(const std::string&)>& done) {
    // Definitions by USR. Two definitions of one USR in one tree is a choice nobody can make
    // from here (rule 1), and the call stays without an edge, counted.
    std::map<std::string, std::vector<Where>> bodies;
    std::map<std::string, const extract::Def*> records;
    for (const auto& d : t.defs) {
        if (d.usr.empty()) continue;
        if (d.is_record) {
            auto it = records.find(d.usr);
            if (it == records.end() || std::tie(d.file, d.line) < std::tie(it->second->file, it->second->line))
                records[d.usr] = &d;
        } else {
            Where w{d.file, d.name, d.line, d.invalid};
            auto& v = bodies[d.usr];
            if (std::find(v.begin(), v.end(), w) == v.end()) v.push_back(w);
        }
    }
    // **A definition clang refused loses a tie, and only a tie.** git's
    // `compat/precompose_utf8.c` defines what `git-compat-util.h` already defines `static
    // inline` when `PRECOMPOSE_UNICODE` is unset: the build compiles one or the other, and
    // under this configuration the file's is a redefinition. Offered beside the valid one, it
    // made every call ambiguous. But a definition alone is kept even when refused: tmux's
    // `server_start` conflicts with its own prototype only because libevent's `event.h` is
    // missing on the machine, and dropping it would send a call inside the tree outside it.
    for (auto& [u, v] : bodies) {
        std::sort(v.begin(), v.end());
        size_t valid = std::count_if(v.begin(), v.end(), [](const Where& w) { return !w.invalid; });
        if (valid > 0 && valid < v.size())
            v.erase(std::remove_if(v.begin(), v.end(), [](const Where& w) { return w.invalid; }), v.end());
    }

    // Who overrides whom, transitively, and who derives from whom.
    std::map<std::string, std::set<std::string>> overridden_by;  // method -> its overriders
    std::map<std::string, std::string> owner_of;                 // method -> its class
    for (const auto& o : t.overs) {
        overridden_by[o.overridden].insert(o.usr);
        owner_of[o.usr] = o.owner;
    }
    std::map<std::string, std::set<std::string>> supers;  // class -> direct bases
    for (const auto& [cls, base] : t.bases) supers[cls].insert(base);
    std::map<std::string, std::set<std::string>> closure_cache;
    std::function<const std::set<std::string>&(const std::string&)> ancestors =
        [&](const std::string& cls) -> const std::set<std::string>& {
        auto it = closure_cache.find(cls);
        if (it != closure_cache.end()) return it->second;
        auto& out = closure_cache[cls];
        out.insert(cls);
        for (const auto& b : supers[cls]) {
            if (out.count(b)) continue;
            const auto& up = ancestors(b);
            out.insert(up.begin(), up.end());
        }
        return out;
    };
    auto overriders = [&](const std::string& method, const std::string& receiver) {
        std::set<std::string> out, todo{method};
        while (!todo.empty()) {
            std::string m = *todo.begin();
            todo.erase(todo.begin());
            for (const auto& o : overridden_by[m]) {
                if (!out.insert(o).second) continue;
                todo.insert(o);
            }
        }
        // Only an override in a subtype of the receiver's static type can answer it.
        std::set<std::string> narrowed;
        for (const auto& o : out) {
            auto ow = owner_of.find(o);
            if (receiver.empty() || ow == owner_of.end() || ancestors(ow->second).count(receiver)) narrowed.insert(o);
        }
        return narrowed;
    };

    // In a fixed order: the edges never depend on which thread finished first (rule 66).
    std::sort(t.sites.begin(), t.sites.end(), [](const extract::Site& a, const extract::Site& b) {
        return std::tie(a.caller_id, a.site_id) < std::tie(b.caller_id, b.site_id);
    });

    long supplied = 0, outside = 0, unknown = 0, dynamic = 0, ambiguous = 0, untyped = 0, bound = 0, constructs = 0,
         macros = 0;
    for (const auto& s : t.sites) {
        facts::SuppliedEdge e;
        e.site_id = s.site_id;
        e.caller_id = s.caller_id;
        auto to = [&](const Where& w, const std::string& how) {
            e.file = w.file;
            e.line = w.line;
            e.name = w.name;
            e.how = how;
        };
        bool any_here = false;
        for (const auto& u : s.macro_usrs) any_here = any_here || bodies.count(u) > 0;
        if (!s.macro.empty() && !s.macro_usrs.empty() && !any_here) {
            // Several calls, none of them this tree's: the call leaves, as what was written.
            // macOS's `memcpy(d, s, n)` is `__builtin___memcpy_chk(d, s, n,
            // __builtin_object_size(d, 0))`, and what a reader wrote, and goes looking for, is
            // `memcpy`.
            e.reason = "outside";
            e.frontier = s.macro;
            e.how = "clang · a macro whose calls are all outside this tree";
            outside++;
        } else if (!s.macro.empty()) {
            e.reason = "unfollowed";
            e.frontier = s.macro;
            e.how = s.macro_usrs.empty() ? "clang · a macro that expands to no call"
                                         : "clang · a macro that expands to several calls";
            macros++;
            unknown++;
        } else if (s.untyped || (s.usr.empty() && !s.bound)) {
            e.reason = "untyped";
            untyped++;
            unknown++;
        } else if (s.bound) {
            e.reason = "bound";
            bound++;
            unknown++;
        } else {
            auto found = bodies.find(s.usr);
            bool has = found != bodies.end();
            // **Where several definitions share a USR, the one the caller's translation unit
            // can see is the one it gets.** A program has one definition of an external
            // function (C11 6.9p5, C++'s one-definition rule), so a file that holds one and is
            // linked links that one: tmux's `osdep-freebsd.c` calling its own `cmp_procs`,
            // which `osdep-netbsd.c` and `osdep-dragonfly.c` also define. And an inline
            // definition is the one its header gives: zlib's `contrib/iostream` and
            // `contrib/iostream3` each have a `gzfilebuf` with an inline `is_open`, and each
            // `zfstream.cpp` includes its own `zfstream.h`. A caller that sees no definition
            // has no such answer and stays without an edge (rule 1).
            const Where* own = nullptr;
            int owns = 0;
            if (has && found->second.size() > 1 && !s.seen.empty())
                for (const auto& w : found->second)
                    if (w.file == s.seen && ++owns == 1) own = &w;
            if (owns != 1) own = nullptr;
            if (own) {
                to(*own, "clang · the definition this file can see");
            } else if (has && found->second.size() > 1) {
                e.candidates = static_cast<int64_t>(found->second.size());
                e.frontier = s.qualified;
                ambiguous++;
                unknown++;
            } else if (s.is_ctor && !has) {
                // A constructor nobody wrote: the class it builds, when the class is this tree's.
                auto rec = records.find(s.construct_usr);
                if (rec != records.end()) {
                    e.constructs = rec->second->qualname;
                    e.file = rec->second->file;
                    e.line = rec->second->line;
                    e.name = rec->second->name;
                    e.how = "clang · an implicit constructor";
                    constructs++;
                } else {
                    e.reason = "outside";
                    e.frontier = s.qualified;
                    outside++;
                }
            } else {
                bool can_dispatch = s.is_method && s.is_virtual && s.is_dynamic && !s.final_;
                std::set<std::string> over = can_dispatch ? overriders(s.usr, s.receiver_usr) : std::set<std::string>{};
                std::vector<Where> answers;
                if (has) answers.push_back(found->second[0]);
                for (const auto& o : over) {
                    auto b = bodies.find(o);
                    if (b != bodies.end() && b->second.size() == 1) answers.push_back(b->second[0]);
                }
                std::sort(answers.begin(), answers.end());
                answers.erase(std::unique(answers.begin(), answers.end()), answers.end());
                // Overridden is dispatched, however many bodies answer: Tom's rule is that only
                // a method nothing overrides is CERTAIN, and one implementation in this tree is
                // not one implementation in every program this code is linked into.
                if (!over.empty() && !answers.empty()) {
                    e.reason = "dynamic";
                    e.candidates = static_cast<int64_t>(answers.size());
                    e.frontier = s.qualified;
                    for (const auto& w : answers) {
                        facts::Answer a;
                        a.file = w.file;
                        a.line = w.line;
                        a.name = w.name;
                        e.answers.push_back(a);
                    }
                    dynamic++;
                    unknown++;
                } else if (answers.size() == 1) {
                    to(answers[0], "clang");
                } else {
                    e.reason = "outside";
                    e.frontier = s.qualified;
                    outside++;
                }
            }
        }
        if (!e.file.empty()) supplied++;
        std::string out;
        e.write_json(out);
        edge(out);
    }

    std::vector<std::string> notes;
    notes.push_back("edges: " + std::to_string(t.files) + " files parsed by libclang; " +
                    std::to_string(supplied) + " calls given a definition in this tree, " + std::to_string(outside) +
                    " reaching outside it, " + std::to_string(dynamic) + " dispatched, " + std::to_string(untyped) +
                    " that clang could not resolve, " + std::to_string(bound) + " through a function value, " +
                    std::to_string(ambiguous) + " with two definitions to choose between, " + std::to_string(macros) +
                    " written as a macro that is not one call");
    if (constructs) notes.push_back("edges: " + std::to_string(constructs) + " constructions of this tree's classes by a constructor nobody wrote");
    if (t.missing_files) {
        notes.push_back("edges: " + std::to_string(t.missing_files) + " of " + std::to_string(t.files) +
                        " files have an #include that was not found, and clang read on past it");
        std::vector<std::pair<long, std::string>> top;
        for (const auto& [m, n] : t.missing) top.push_back({-n, m});
        std::sort(top.begin(), top.end());
        for (size_t i = 0; i < top.size() && i < 6; i++) notes.push_back("  " + std::to_string(-top[i].first) + "x " + top[i].second);
    }
    if (t.fatal_files)
        notes.push_back("edges: " + std::to_string(t.fatal_files) + " of " + std::to_string(t.files) +
                        " files hit a fatal error, and clang read on past it");
    if (t.fragments_through || !t.fragments_alone.empty()) {
        notes.push_back("edges: " + std::to_string(t.fragments_through) +
                        " fragments (.inl, .ipp) were read through a file that includes them; " +
                        std::to_string(t.fragments_alone.size()) +
                        " were read alone, because nothing read includes them under the defines in force" +
                        (t.fragments_alone.empty() ? "" : ":"));
        std::vector<std::string> alone = t.fragments_alone;
        std::sort(alone.begin(), alone.end());  // the pool finishes files in any order (rule 66)
        for (size_t i = 0; i < alone.size() && i < 6; i++) notes.push_back("  " + alone[i]);
        if (alone.size() > 6) notes.push_back("  … and " + std::to_string(alone.size() - 6) + " more");
    }
    if (t.skipped_lines)
        notes.push_back("edges: " + std::to_string(t.skipped_lines) +
                        " lines are in #if arms this configuration does not take, and were not read");

    std::string d = "\"supplied\":" + std::to_string(supplied) + ",\"unresolved\":" + std::to_string(outside + unknown) +
                    ",\"outside\":" + std::to_string(outside) + ",\"unknown\":" + std::to_string(unknown) + ",\"notes\":";
    json::write(d, notes);
    d += ",\"read_beyond\":";
    json::write(d, t.read_beyond);
    done(d);
}

}  // namespace edges
