// How each file is parsed: the arguments clang is given, decided once per session.
//
// **Tom's decisions at the chunk 0 gate (2026-11-02), on measured numbers.**
//
// 1. **The machine's own target and system headers.** A fixed reference target with no
//    system headers gives the same map everywhere and lost the C++ standard library
//    (`type_traits`); with the host's headers tmux and git resolved 99 % of their calls.
//    So the map depends on this machine and on its libclang, and the cache key carries the
//    compiler's version (rule 81), as Java's carries the JDK's.
// 2. **A tree's build configuration comes from, in order:** its `compile_commands.json`,
//    which always wins; otherwise a **preset** in `detectors/cpp.yaml`, matched by a marker
//    file, which supplies the defines the framework's own build tool would pass; otherwise
//    nothing. Unreal Core resolved 32 % of its calls with nothing, 65 % with its five
//    build-tool defines, and 88 % with those and the whole `Runtime`'s include roots.
// 3. **Include roots may be looked for above the analysed root, up to the matched preset's
//    top**, and nowhere above the root without one (rule 108: a walk up the tree does not
//    know when it has left it). What is found there is read for its declarations and is
//    never a fact; it is said in `read_beyond`.
//
// **Include directories are inferred by a unique suffix**, because none of the five corpora
// has a compilation database. Every `#include` spelling in the tree is matched against the
// tree's own files: a spelling exactly one file's path ends with adds that file's prefix as
// an include directory, and a spelling two files answer adds nothing and is counted (rule
// 1: a guess between two headers is a wrong declaration as often as a right one).

#pragma once

#include <algorithm>
#include <filesystem>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "clang.hpp"
#include "rules.hpp"
#include "text.hpp"

namespace config {

namespace fs = std::filesystem;

inline const std::set<std::string> SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".c++"};
inline const std::set<std::string> HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx", ".h++", ".inl", ".ipp"};

inline std::string suffix(const std::string& path) {
    size_t slash = path.find_last_of("/\\");
    size_t dot = path.rfind('.');
    if (dot == std::string::npos || (slash != std::string::npos && dot < slash)) return "";
    std::string s = path.substr(dot);
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return std::tolower(c); });
    return s;
}

inline bool is_c(const std::string& path) { return suffix(path) == ".c"; }
inline bool is_header(const std::string& path) { return HEADER_SUFFIXES.count(suffix(path)) > 0; }

// Every `#include` spelling in a text, as written: what is between the quotes or the
// angle brackets. Read off the text rather than parsed, because this runs before any parse.
inline void include_spellings(const std::string& t, std::set<std::string>& out) {
    size_t i = 0, n = t.size();
    while (i < n) {
        size_t eol = t.find('\n', i);
        if (eol == std::string::npos) eol = n;
        size_t j = i;
        while (j < eol && (t[j] == ' ' || t[j] == '\t')) j++;
        if (j < eol && t[j] == '#') {
            j++;
            while (j < eol && (t[j] == ' ' || t[j] == '\t')) j++;
            if (t.compare(j, 7, "include") == 0) {
                j += 7;
                while (j < eol && (t[j] == ' ' || t[j] == '\t')) j++;
                if (j < eol && (t[j] == '"' || t[j] == '<')) {
                    char close = t[j] == '"' ? '"' : '>';
                    size_t k = t.find(close, j + 1);
                    if (k != std::string::npos && k < eol && k > j + 1) out.insert(t.substr(j + 1, k - j - 1));
                }
            }
        }
        i = eol + 1;
    }
}

struct Session {
    std::string root;                      // absolute, generic separators
    std::vector<std::string> base;         // every parse gets these
    std::vector<std::string> include_dirs; // inferred, sorted
    bool tree_has_cpp = false;
    std::string preset;                    // the matched preset's name, or ""
    std::string top;                       // the preset's top, absolute, or ""
    std::map<std::string, std::vector<std::string>> database;  // file -> args, from compile_commands.json
    bool has_database = false;
    std::vector<std::string> notes;        // what the host is told in `opened`
    std::vector<std::string> read_beyond;  // include roots above the analysed root
    int ambiguous = 0;                     // spellings two or more files answer
    int unanswered = 0;                    // spellings no file in reach answers

    // The arguments for one file. The language comes first, so a database entry that names
    // another is still parsed as the file's own suffix says.
    std::vector<std::string> args_for(const std::string& path) const {
        std::vector<std::string> a;
        bool c = is_c(path) || (is_header(path) && !tree_has_cpp);
        if (is_header(path)) {
            a = {"-x", c ? "c-header" : "c++-header"};
        } else {
            a = {"-x", c ? "c" : "c++"};
        }
        auto db = database.find(path);
        if (db != database.end()) {
            a.insert(a.end(), db->second.begin(), db->second.end());
            return a;
        }
        a.push_back(c ? "-std=gnu17" : "-std=gnu++20");
        a.insert(a.end(), base.begin(), base.end());
        for (const auto& d : include_dirs) a.push_back("-I" + d);
        return a;
    }
};

inline std::string generic(const fs::path& p) { return p.lexically_normal().generic_string(); }

// The preset whose marker is found at or above the root, nearest first.
inline const rules::Preset* match_preset(const fs::path& root, const rules::Rules& r, fs::path& top) {
    for (fs::path dir = root;; dir = dir.parent_path()) {
        for (const auto& p : r.presets) {
            std::error_code ec;
            if (fs::exists(dir / p.marker, ec)) {
                top = p.top.empty() ? dir : (dir / p.top);
                return &p;
            }
        }
        if (dir == dir.parent_path() || dir.parent_path().empty()) break;
    }
    return nullptr;
}

// Arguments from a compilation database, without the compiler, the output and the input.
inline std::vector<std::string> database_args(CXCompileCommand cmd) {
    auto& c = clang::api();
    std::vector<std::string> out;
    unsigned n = c.clang_CompileCommand_getNumArgs(cmd);
    std::string dir = clang::str(c.clang_CompileCommand_getDirectory(cmd));
    for (unsigned i = 1; i < n; i++) {
        std::string a = clang::str(c.clang_CompileCommand_getArg(cmd, i));
        if (a == "-c") continue;
        if (a == "-o" || a == "-MF" || a == "-MT" || a == "-MQ") {
            i++;
            continue;
        }
        if (a.size() > 2 && (a.rfind("-I", 0) == 0) && !fs::path(a.substr(2)).is_absolute()) {
            a = "-I" + generic(fs::path(dir) / a.substr(2));
        }
        // The input file itself: the reader names its own.
        std::string suf = suffix(a);
        if (!a.empty() && a[0] != '-' && (SOURCE_SUFFIXES.count(suf) || HEADER_SUFFIXES.count(suf))) continue;
        out.push_back(a);
    }
    return out;
}

inline Session decide(const std::string& root_in, const std::vector<std::string>& files,
                      const rules::Rules& r) {
    Session s;
    fs::path root = fs::absolute(fs::path(root_in));
    s.root = generic(root);
    for (const auto& f : files)
        if (!is_c(f) && SOURCE_SUFFIXES.count(suffix(f))) s.tree_has_cpp = true;

#ifdef __APPLE__
    // libclang is not run through the `xcrun` shim the way `/usr/bin/clang++` is, so it has
    // no SDK until it is told one, and without it `<stdio.h>` is not found.
    std::string sdk = clang::first_line("xcrun --show-sdk-path 2>/dev/null");
    if (!sdk.empty()) {
        s.base.push_back("-isysroot");
        s.base.push_back(sdk);
    }
#endif

    // 1. A compilation database always wins, for the files it names.
    auto& c = clang::api();
    CXCompilationDatabase_Error err = CXCompilationDatabase_NoError;
    CXCompilationDatabase db = c.clang_CompilationDatabase_fromDirectory(s.root.c_str(), &err);
    if (db && err == CXCompilationDatabase_NoError) {
        for (const auto& f : files) {
            CXCompileCommands cmds = c.clang_CompilationDatabase_getCompileCommands(db, f.c_str());
            if (cmds && c.clang_CompileCommands_getSize(cmds) > 0) {
                s.database[f] = database_args(c.clang_CompileCommands_getCommand(cmds, 0));
            }
            if (cmds) c.clang_CompileCommands_dispose(cmds);
        }
        s.has_database = !s.database.empty();
        c.clang_CompilationDatabase_dispose(db);
        if (s.has_database) {
            s.notes.push_back("compile_commands.json gave the arguments for " + std::to_string(s.database.size()) +
                              " of " + std::to_string(files.size()) + " files; the rest are inferred");
        }
    }

    // 2. A preset, for a framework whose build tool passes defines nothing else spells.
    fs::path top;
    const rules::Preset* preset = match_preset(root, r, top);
    if (preset) {
        s.preset = preset->name;
        s.top = generic(top);
        for (const auto& d : preset->defines) s.base.push_back("-D" + d);
#if defined(__APPLE__)
        const char* plat = "darwin";
#elif defined(_WIN32)
        const char* plat = "win32";
#else
        const char* plat = "linux";
#endif
        auto pd = preset->platform_defines.find(plat);
        if (pd != preset->platform_defines.end())
            for (const auto& d : pd->second) s.base.push_back("-D" + d);
        s.notes.push_back("the " + preset->name + " preset applied (" + preset->marker +
                          " found), with the defines its build tool would pass");
    }

    // 3. Include directories by unique suffix, over the files in reach: the tree's own, and
    //    with a preset everything under its top.
    std::set<std::string> spellings;
    std::vector<std::string> reach;  // generic absolute paths of every header-like file in reach
    for (const auto& f : files) {
        std::string t;
        if (text::read_source(f, t)) include_spellings(t, spellings);
        reach.push_back(generic(fs::absolute(f)));
    }
    std::set<std::string> module_defines;
    if (!s.top.empty()) {
        std::error_code ec;
        for (auto it = fs::recursive_directory_iterator(s.top, fs::directory_options::skip_permission_denied, ec);
             it != fs::recursive_directory_iterator(); it.increment(ec)) {
            if (ec) break;
            const auto& p = it->path();
            std::string name = p.filename().string();
            if (it->is_directory(ec) && (name == ".git" || name == "Intermediate" || name == "Binaries")) {
                it.disable_recursion_pending();
                continue;
            }
            if (!it->is_regular_file(ec)) continue;
            if (preset && !preset->module_file_suffix.empty() && name.size() > preset->module_file_suffix.size() &&
                name.compare(name.size() - preset->module_file_suffix.size(), std::string::npos,
                             preset->module_file_suffix) == 0) {
                std::string stem = name.substr(0, name.size() - preset->module_file_suffix.size());
                std::transform(stem.begin(), stem.end(), stem.begin(), [](unsigned char ch) { return std::toupper(ch); });
                std::string d = preset->module_define;
                size_t at = d.find("{MODULE}");
                if (at != std::string::npos) d.replace(at, 8, stem);
                module_defines.insert(d);
            }
            if (HEADER_SUFFIXES.count(suffix(name))) {
                std::string g = generic(p);
                if (s.top != s.root && g.rfind(s.root + "/", 0) != 0) reach.push_back(g);
            }
        }
        for (const auto& d : module_defines) s.base.push_back("-D" + d);
        if (!module_defines.empty())
            s.notes.push_back("the " + s.preset + " preset defined " + std::to_string(module_defines.size()) +
                              " module macros, one per " + preset->module_file_suffix + " under its top");
    }
    std::map<std::string, std::vector<std::string>> by_base;
    for (const auto& g : reach) by_base[g.substr(g.find_last_of('/') + 1)].push_back(g);
    std::set<std::string> dirs, beyond;
    for (auto sp : spellings) {
        while (sp.rfind("./", 0) == 0) sp = sp.substr(2);
        if (sp.empty() || sp.find("..") != std::string::npos) continue;
        std::string base = sp.substr(sp.find_last_of('/') + 1);
        auto it = by_base.find(base);
        std::vector<std::string> hits;
        if (it != by_base.end())
            for (const auto& g : it->second)
                if (g.size() > sp.size() && g.compare(g.size() - sp.size(), sp.size(), sp) == 0 &&
                    g[g.size() - sp.size() - 1] == '/')
                    hits.push_back(g);
        if (hits.size() == 1) {
            std::string dir = hits[0].substr(0, hits[0].size() - sp.size() - 1);
            dirs.insert(dir);
            if (dir != s.root && dir.rfind(s.root + "/", 0) != 0) beyond.insert(dir);
        } else if (hits.size() > 1) {
            s.ambiguous++;
        } else {
            s.unanswered++;
        }
    }
    s.include_dirs.assign(dirs.begin(), dirs.end());
    s.read_beyond.assign(beyond.begin(), beyond.end());
    s.notes.push_back(std::to_string(s.include_dirs.size()) + " include directories inferred from " +
                      std::to_string(spellings.size()) + " #include spellings; " +
                      std::to_string(s.ambiguous) + " answered by more than one file and left unresolved");
    return s;
}

}  // namespace config
