// The language's rules, as `detectors/cpp.yaml` declares them and the host sends them.
//
// They arrive with the session and are never baked in: a reader carrying its own copy of
// the YAML is a second answer that stops moving the moment somebody edits the file, and
// that file is in this language's extraction stamp so an edit re-reads every file
// (rule 51). The matching is `BoundaryRule.matches_call` and
// `EntrypointRule.matches_decorator`, transcribed, as `plugins/go/rules.go` transcribes them.

#pragma once

#include <cctype>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "json.hpp"

namespace rules {

inline std::string folded(std::string s) {
    for (auto& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}

// One entry under `boundaries:`, matched against a call's dotted form.
struct Boundary {
    std::string kind, direction = "BOTH", salience = "normal";
    std::vector<std::string> exact, prefix, method, contains;
    std::optional<int64_t> target_arg;
    bool names_macro = false;  // about the macro itself: what it reaches cannot contradict it
    // `detectors.ArgCondition` (`when_arg`): the rule applies only for some values of one
    // argument, read as written (`AF_UNIX` is named, never evaluated).
    std::optional<int64_t> when_index;
    std::set<std::string> when_in, when_not_in;
    std::string undecided;  // said on whatever rule matches instead, when the condition cannot decide
    std::string note;       // a fixed phrase after the evidence

    // `ArgCondition.decide`: 1 yes, 0 no, -1 undecided. An absent argument, a literal or a
    // `not_in` entry decides no; anything else not in `in` -- a variable, a call -- is
    // undecided and never matches (rule 49).
    int decide(const std::vector<std::string>& args) const {
        if (!when_index || *when_index < 0 || *when_index >= static_cast<int64_t>(args.size())) return 0;
        std::string v = args[static_cast<size_t>(*when_index)];
        bool literal = !v.empty() && (v[0] == '"' || v[0] == '\'' || std::isdigit(static_cast<unsigned char>(v[0])));
        if (v.size() >= 2 && v.front() == '"' && v.back() == '"') v = v.substr(1, v.size() - 2);
        if (when_in.count(v)) return 1;
        if (literal || when_not_in.count(v)) return 0;
        return -1;
    }

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
    // A framework may read its macro's specifiers in any case (`detectors/cpp.yaml` says which
    // macro, and why). Only the specifiers: a value in it, or a word in another macro, is not one.
    std::string specifiers_of;

    // `EntrypointRule.matches_decorator`: the last segment of the dotted decorator.
    bool matches(const std::string& dotted) const {
        if (dotted.empty()) return false;
        size_t dot = dotted.rfind('.');
        std::string tail = dot == std::string::npos ? dotted : dotted.substr(dot + 1);
        for (const auto& m : decorator_method)
            if (tail == m) return true;
        return false;
    }
    bool matches_specifier(const std::string& word) const {
        for (const auto& m : decorator_method)
            if (folded(word) == folded(m)) return true;
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
    // The language its build tool compiles C++ as, per platform, where that is not C++:
    // Unreal's Apple toolchain compiles every `.cpp` as Objective-C++.
    std::map<std::string, std::string> platform_language;
    // A framework's modules each get a define of their own, named by a file each module has:
    // Unreal's `Core.Build.cs` is why `CORE_API` is defined. `{MODULE}` is the stem, upper-cased.
    std::string module_file_suffix;
    std::string module_define;
    // **Where a marked declaration's body is, when it is not the declaration's own** -- by
    // the marker word on it. A framework's code generator decides this, so the preset says
    // it and no line of the reader does: Unreal's `BlueprintNativeEvent` is defined as
    // `<Name>_Implementation`, and a `BlueprintImplementableEvent` has no C++ body at all.
    struct Body {
        std::string suffix;  // the body is the method of this name plus the suffix
        std::string why;     // there is no body here, and this is why
        std::string prefix;  // the body is the method of this prefix plus the name, whatever its
                             // parameters, and what runs even when the name has a body too
    };
    std::map<std::string, Body> bodies;  // by the marker, folded: see `specifiers_of`
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
        x.names_macro = b["names_macro"].boolean();
        if (!b["when_arg"].is_null()) {
            const auto& w = b["when_arg"];
            // A condition with no position decides nothing: refused as never, and said.
            x.when_index = w["index"].is_null() ? -1 : w["index"].integer();
            for (const auto& v : w["in"].strings()) x.when_in.insert(v);
            for (const auto& v : w["not_in"].strings()) x.when_not_in.insert(v);
        }
        x.undecided = b["undecided"].str();
        x.note = b["note"].str();
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
        x.specifiers_of = e["specifiers_of"].str();
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
        for (const auto& [plat, l] : p["platform_language"].map()) {
            std::string lang = l.str();
            if (lang == "c++" || lang == "objective-c++") x.platform_language[plat] = lang;
            else  // refused, not defaulted: a language nobody reads is every file misread (rule 49)
                notes.push_back("the " + x.name + " preset names " + lang + " for " + plat +
                                "; this reader knows c++ and objective-c++, and reads it as c++");
        }
        x.module_file_suffix = p["module_defines"]["file_suffix"].str();
        x.module_define = p["module_defines"]["define"].str();
        for (const auto& [marker, b] : p["bodies"].map()) x.bodies[folded(marker)] = {b["suffix"].str(), b["why"].str(), b["prefix"].str()};
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
