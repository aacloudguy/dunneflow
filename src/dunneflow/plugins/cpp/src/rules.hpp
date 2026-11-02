// The language's rules, as `detectors/cpp.yaml` declares them and the host sends them.
//
// They arrive with the session and are never baked in: a reader carrying its own copy of
// the YAML is a second answer that stops moving the moment somebody edits the file, and
// that file is in this language's extraction stamp so an edit re-reads every file
// (rule 51). The matching is `BoundaryRule.matches_call` and
// `EntrypointRule.matches_decorator`, transcribed, as `plugins/go/rules.go` transcribes them.

#pragma once

#include <map>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "json.hpp"

namespace rules {

// One entry under `boundaries:`, matched against a call's dotted form.
struct Boundary {
    std::string kind, direction = "BOTH", salience = "normal";
    std::vector<std::string> exact, prefix, method, contains;
    std::optional<int64_t> target_arg;

    // `BoundaryRule.matches_call`: the four tests and nothing else.
    bool matches(const std::string& dotted) const {
        if (dotted.empty()) return false;
        for (const auto& e : exact)
            if (dotted == e) return true;
        for (const auto& p : prefix)
            if (dotted.compare(0, p.size(), p) == 0) return true;
        for (const auto& c : contains)
            if (dotted.find(c) != std::string::npos) return true;
        if (!method.empty()) {
            // A bare name is a plain function call, not a method on something.
            size_t dot = dotted.rfind('.');
            if (dot != std::string::npos) {
                std::string tail = dotted.substr(dot + 1);
                for (const auto& m : method)
                    if (tail == m) return true;
            }
        }
        return false;
    }
};

// One entry under `entrypoints:` that a decorator recognises.
struct Entrypoint {
    std::string kind, evidence;
    std::vector<std::string> decorator_method;

    // `EntrypointRule.matches_decorator`: the last segment of the dotted decorator.
    bool matches(const std::string& dotted) const {
        if (dotted.empty()) return false;
        size_t dot = dotted.rfind('.');
        std::string tail = dot == std::string::npos ? dotted : dotted.substr(dot + 1);
        for (const auto& m : decorator_method)
            if (tail == m) return true;
        return false;
    }
};

// A framework's build configuration, for a tree that has no compilation database
// (Tom, 2026-11-02): matched by a marker file, it supplies the defines the framework's
// own build tool would have passed, and it bounds how far above the analysed root include
// directories may be looked for.
struct Preset {
    std::string name;
    std::string marker;             // a path that, found at or above the root, names the framework
    std::string top;                // the marker's directory, relative: the highest include root
    std::vector<std::string> defines;
    std::map<std::string, std::vector<std::string>> platform_defines;  // darwin, linux, win32
    // A framework's modules each get a define of their own, named by a file each module has:
    // Unreal's `Core.Build.cs` is why `CORE_API` is defined. `{MODULE}` is the stem, upper-cased.
    std::string module_file_suffix;
    std::string module_define;
};

struct Rules {
    std::vector<Boundary> boundaries;
    std::vector<Entrypoint> entrypoints;
    std::set<std::string> entry_names;
    std::vector<Preset> presets;

    const Boundary* match_call(const std::string& dotted) const {
        for (const auto& b : boundaries)
            if (b.matches(dotted)) return &b;
        return nullptr;
    }
};

inline Rules parse(const json::Value& raw, std::vector<std::string>& notes) {
    Rules r;
    for (const auto& b : raw["boundaries"].list()) {
        Boundary x;
        x.kind = b["kind"].str();
        x.direction = b["direction"].str("BOTH");
        x.salience = b["salience"].str("normal");
        x.exact = b["exact"].strings();
        x.prefix = b["prefix"].strings();
        x.method = b["method"].strings();
        x.contains = b["contains"].strings();
        if (!b["target_arg"].is_null()) x.target_arg = b["target_arg"].integer();
        std::string target = b["target"].str();
        if (!target.empty() && target != "arg") {
            // Refused rather than defaulted: a strategy nobody reads is a boundary row naming
            // the wrong thing every time (rule 49).
            notes.push_back("detectors/cpp.yaml declares target: " + target +
                            "; this reader reads arg, and reads the rule as arg");
        }
        r.boundaries.push_back(std::move(x));
    }
    for (const auto& e : raw["entrypoints"].list()) {
        if (e["decorator_method"].list().empty()) continue;
        Entrypoint x;
        x.kind = e["kind"].str();
        x.evidence = e["evidence"].str();
        x.decorator_method = e["decorator_method"].strings();
        r.entrypoints.push_back(std::move(x));
    }
    for (const auto& n : raw["entry_names"].strings()) r.entry_names.insert(n);
    for (const auto& p : raw["presets"].list()) {
        Preset x;
        x.name = p["name"].str();
        x.marker = p["marker"].str();
        x.top = p["top"].str();
        x.defines = p["defines"].strings();
        for (const auto& [plat, ds] : p["platform_defines"].map()) x.platform_defines[plat] = ds.strings();
        x.module_file_suffix = p["module_defines"]["file_suffix"].str();
        x.module_define = p["module_defines"]["define"].str();
        if (x.name.empty() || x.marker.empty()) {
            notes.push_back("a preset in detectors/cpp.yaml has no name or no marker, and is not used");
            continue;
        }
        r.presets.push_back(std::move(x));
    }
    if (r.boundaries.empty()) {
        // Not an error and not silent: a run with no rules is a map with no boundaries,
        // which looks exactly like a program that touches nothing (rule 49).
        notes.push_back("no boundary rules arrived with this session; the map will report none");
    }
    return r;
}

}  // namespace rules
