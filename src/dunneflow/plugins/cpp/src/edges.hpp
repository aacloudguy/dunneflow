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
    long fatal_files = 0, files = 0, skipped_lines = 0;
    std::map<std::string, long> missing;  // first missing include, per file that had one

    void add(extract::Result& r) {
        files++;
        if (r.fatal) fatal_files++;
        skipped_lines += r.skipped_lines;
        if (!r.first_missing.empty()) missing[r.first_missing]++;
        for (auto& s : r.sites) sites.push_back(std::move(s));
        for (auto& d : r.defs) defs.push_back(std::move(d));
        for (auto& o : r.overs) overs.push_back(std::move(o));
        for (auto& b : r.bases) bases.push_back(std::move(b));
    }
};

struct Where {
    std::string file, name;
    long line = 0;
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
            Where w{d.file, d.name, d.line};
            auto& v = bodies[d.usr];
            if (std::find(v.begin(), v.end(), w) == v.end()) v.push_back(w);
        }
    }
    for (auto& [u, v] : bodies) std::sort(v.begin(), v.end());

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

    long supplied = 0, outside = 0, unknown = 0, dynamic = 0, ambiguous = 0, untyped = 0, bound = 0, constructs = 0;
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
        if (s.untyped || (s.usr.empty() && !s.bound)) {
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
            if (has && found->second.size() > 1) {
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
                    std::to_string(ambiguous) + " with two definitions to choose between");
    if (constructs) notes.push_back("edges: " + std::to_string(constructs) + " constructions of this tree's classes by a constructor nobody wrote");
    if (t.fatal_files) {
        notes.push_back("edges: " + std::to_string(t.fatal_files) + " of " + std::to_string(t.files) +
                        " files hit a fatal error (most often an #include not found), and clang read on past it");
        std::vector<std::pair<long, std::string>> top;
        for (const auto& [m, n] : t.missing) top.push_back({-n, m});
        std::sort(top.begin(), top.end());
        for (size_t i = 0; i < top.size() && i < 6; i++) notes.push_back("  " + std::to_string(-top[i].first) + "x " + top[i].second);
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
