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
//
// **An inferred directory is searched after the system's, never before** (`-idirafter`).
// A tree carries look-alikes of system headers for platforms it is not being built for:
// nmap's libssh2 has an OS/400 `stdio.h` and `sys/socket.h`, and git a win32 `alloca.h`.
// Each was the one file in the tree to answer its spelling, so each was inferred, and as
// `-I` it then shadowed the system's own: 300 of nmap's files went looking for OS/400's
// `qadrt.h` and 653 of git's for `malloc.h`, and both lost a quarter of their calls.
// A directory the tree's build really does put first is what `compile_commands.json` says.

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

// A fragment is text written to be pasted into another file -- the bodies a header keeps
// apart, an X-macro list -- and read alone it means nothing: `int32 UFoo::Add(...)` with no
// `UFoo` in front of it is not a routine clang can name.
inline const std::set<std::string> FRAGMENT_SUFFIXES = {".inl", ".ipp"};
inline bool is_fragment(const std::string& path) { return FRAGMENT_SUFFIXES.count(suffix(path)) > 0; }

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
    std::string cxx = "c++";  // what C++ is compiled as: a preset may say objective-c++
    std::string preset;                    // the matched preset's name, or ""
    std::string top;                       // the preset's top, absolute, or ""
    std::map<std::string, std::vector<std::string>> database;  // file -> args, from compile_commands.json
    bool has_database = false;
    std::vector<std::string> notes;        // what the host is told in `opened`
    std::vector<std::string> read_beyond;  // include roots above the analysed root
    std::vector<std::string> inputs;       // build files this decision read, or looked for
    int ambiguous = 0;                     // spellings two or more files answer
    int unanswered = 0;                    // spellings no file in reach answers
    int above = 0;                         // spellings whose directory would be above the ceiling
    // Each fragment's includers among the files read, canonical order first: the header of
    // the same stem, then by path (rule 66). A fragment nothing includes is not here.
    std::map<std::string, std::vector<std::string>> includers;
    // Spellings no file answers whose header the build generates from a template beside the
    // sources -- `pxr/pxr.h` from `pxr/pxr.h.in`, nmap's `nmap_config.h` from
    // `nmap_config.h.in` -- by spelling, with the template's path relative to the root.
    std::map<std::string, std::string> generated;

    // The arguments for one file. The language comes first, so a database entry that names
    // another is still parsed as the file's own suffix says.
    std::vector<std::string> args_for(const std::string& path) const {
        std::vector<std::string> a;
        bool c = is_c(path) || (is_header(path) && !tree_has_cpp);
        if (is_header(path)) {
            a = {"-x", c ? "c-header" : cxx + "-header"};
        } else {
            a = {"-x", c ? "c" : cxx};
        }
        // **No error limit.** clang stops a file at its twentieth error ("too many errors
        // emitted, stopping now", a fatal), and a reader that reads on past a missing header
        // meets twenty errors early: 210 of nmap's 766 files stopped there, and every call
        // after the stop had nothing to say where it went. Last, so a database's own
        // `-ferror-limit` does not put it back.
        auto db = database.find(path);
        if (db != database.end()) {
            a.insert(a.end(), db->second.begin(), db->second.end());
            a.push_back("-ferror-limit=0");
            return a;
        }
        a.push_back("-ferror-limit=0");
        a.push_back(c ? "-std=gnu17" : "-std=gnu++20");
        a.insert(a.end(), base.begin(), base.end());
        // After the system's own directories, never before them (see the header comment).
        for (const auto& d : include_dirs) a.push_back("-idirafter" + d);
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

// Which file each fragment is included by. A quoted spelling is looked for beside the file
// that writes it first, as the compiler does; then by unique suffix over the files read, the
// matcher the include directories are inferred with (one answer or none -- rule 1).
inline std::map<std::string, std::vector<std::string>> fragment_includers(
    const std::vector<std::string>& files, const std::map<std::string, std::set<std::string>>& own) {
    std::set<std::string> known(files.begin(), files.end());
    std::map<std::string, std::vector<std::string>> by_base;
    for (const auto& g : files)
        if (is_fragment(g)) by_base[g.substr(g.find_last_of('/') + 1)].push_back(g);
    std::map<std::string, std::set<std::string>> found;
    for (const auto& [file, sps] : own) {
        std::string dir = file.substr(0, file.find_last_of('/'));
        for (auto sp : sps) {
            while (sp.rfind("./", 0) == 0) sp = sp.substr(2);
            if (sp.empty()) continue;
            std::string beside = generic(fs::path(dir) / sp);
            if (known.count(beside) && is_fragment(beside)) {
                if (beside != file) found[beside].insert(file);
                continue;
            }
            if (sp.find("..") != std::string::npos) continue;
            auto it = by_base.find(sp.substr(sp.find_last_of('/') + 1));
            if (it == by_base.end()) continue;
            std::vector<std::string> hits;
            for (const auto& g : it->second)
                if (g.size() > sp.size() && g.compare(g.size() - sp.size(), sp.size(), sp) == 0 &&
                    g[g.size() - sp.size() - 1] == '/')
                    hits.push_back(g);
            if (hits.size() == 1 && hits[0] != file) found[hits[0]].insert(file);
        }
    }
    auto stem = [](const std::string& g) {
        std::string b = g.substr(g.find_last_of('/') + 1);
        return b.substr(0, b.rfind('.'));
    };
    std::map<std::string, std::vector<std::string>> out;
    for (const auto& kv : found) {
        const std::string own_stem = stem(kv.first);
        std::vector<std::string> v(kv.second.begin(), kv.second.end());  // a set: path order already
        std::stable_partition(v.begin(), v.end(), [&](const std::string& g) {
            return is_header(g) && !is_fragment(g) && stem(g) == own_stem;
        });
        out[kv.first] = std::move(v);
    }
    return out;
}

inline Session decide(const std::string& root_in, const std::vector<std::string>& files,
                      const rules::Rules& r) {
    Session s;
    fs::path root = fs::absolute(fs::path(root_in));
    s.root = generic(root);
    // **Whether a `.h` is C or C++ is a fact about the tree**, and a source file is not the
    // only thing that says it: a header only C++ writes (`.hpp`, `.inl`, ...) says it too.
    // Without that a header-only C++ tree -- Unreal's `Engine/Classes/Kismet`, every
    // header-only library -- was parsed as C: `<type_traits>` not found in all 25 files,
    // `namespace` not a keyword, and not one routine in the map.
    for (const auto& f : files) {
        std::string x = suffix(f);
        if (!is_c(f) && (SOURCE_SUFFIXES.count(x) || (HEADER_SUFFIXES.count(x) && x != ".h")))
            s.tree_has_cpp = true;
    }

#ifdef __APPLE__
    // libclang is not run through the `xcrun` shim the way `/usr/bin/clang++` is, so it has
    // no SDK until it is told one, and without it `<stdio.h>` is not found.
    std::string sdk = clang::first_line("xcrun --show-sdk-path 2>/dev/null");
    if (!sdk.empty()) {
        s.base.push_back("-isysroot");
        s.base.push_back(sdk);
    }
#endif

    // 1. A compilation database always wins, for the files it names. Named as an input whether
    // or not it is there: the day one appears is the day every file's arguments change.
    s.inputs.push_back(s.root + "/compile_commands.json");
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
        // A preset names a C++ framework (all of them do: see `cpp.yaml`), so a tree under
        // one is C++ whatever its suffixes say.
        s.tree_has_cpp = true;
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
        auto pl = preset->platform_language.find(plat);
        if (pl != preset->platform_language.end() && pl->second != s.cxx) {
            s.cxx = pl->second;
            s.notes.push_back("the " + preset->name + " preset compiles C++ as " + s.cxx + " here, as its build tool does");
        }
        s.notes.push_back("the " + preset->name + " preset applied (" + preset->marker +
                          " found), with the defines its build tool would pass");
    }

    // 3. Include directories by unique suffix, over the files in reach: the tree's own, and
    //    with a preset everything under its top.
    std::set<std::string> spellings;
    std::vector<std::string> reach;  // generic absolute paths of every header-like file in reach
    std::map<std::string, std::set<std::string>> own;  // file -> the fragment spellings it writes
    for (const auto& f : files) {
        std::string t;
        std::set<std::string> mine;
        if (text::read_source(f, t)) include_spellings(t, mine);
        for (const auto& sp : mine)
            if (is_fragment(sp)) own[generic(fs::absolute(f))].insert(sp);
        spellings.insert(mine.begin(), mine.end());
        reach.push_back(generic(fs::absolute(f)));
    }
    s.includers = fragment_includers(reach, own);
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
                s.inputs.push_back(generic(p));
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
    // **The headers a build generates, by their templates.** An unconfigured autoconf or
    // CMake tree has `config.h.in` and no `config.h`, and every file that includes it is
    // read without what it defines: 4,545 of OpenUSD's files missed `pxr/pxr.h`, and the
    // map said so as a count with no word of why or what would mend it. Looked for only in
    // the directories the read files are in -- where a template sits beside its sources --
    // so this is a listing of each, never a walk of the tree.
    std::map<std::string, std::vector<std::pair<std::string, std::string>>> templates;  // base -> (made, template)
    {
        std::set<std::string> dirs_read;
        for (const auto& f : files) dirs_read.insert(generic(fs::path(f).parent_path()));
        for (const auto& d : dirs_read) {
            std::error_code ec;
            for (const auto& e : fs::directory_iterator(d, fs::directory_options::skip_permission_denied, ec)) {
                std::string name = e.path().filename().string();
                if (name.size() < 4 || name.compare(name.size() - 3, 3, ".in") != 0) continue;
                std::string made = name.substr(0, name.size() - 3);
                if (made.size() > 6 && made.compare(made.size() - 6, 6, ".cmake") == 0) made.resize(made.size() - 6);
                if (!HEADER_SUFFIXES.count(suffix(made))) continue;
                std::string g = generic(e.path());
                std::string rel_made = generic(fs::path(d) / made);
                std::string rel_from = g.rfind(s.root + "/", 0) == 0 ? g.substr(s.root.size() + 1) : g;
                templates[made].push_back({rel_made, rel_from});
            }
        }
        for (auto& [b, v] : templates) std::sort(v.begin(), v.end());
    }
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
            // **Never above the top, nor above the root without one** (Tom's decision at the
            // gate, and rule 108). The file is in reach, but the directory a spelling makes of
            // it may not be: Core's `#include "Runtime/Launch/Resources/Version.h"` made
            // `Engine/Source` an include directory, above the preset's `Runtime`.
            const std::string& ceiling = s.top.empty() ? s.root : s.top;
            if (dir != ceiling && dir.rfind(ceiling + "/", 0) != 0) {
                s.above++;
                continue;
            }
            dirs.insert(dir);
            if (dir != s.root && dir.rfind(s.root + "/", 0) != 0) beyond.insert(dir);
        } else if (hits.size() > 1) {
            s.ambiguous++;
        } else {
            s.unanswered++;
            auto t = templates.find(base);
            if (t != templates.end())
                for (const auto& [made, from] : t->second)
                    if (made == sp || (made.size() > sp.size() && made.compare(made.size() - sp.size(), sp.size(), sp) == 0 &&
                                       made[made.size() - sp.size() - 1] == '/')) {
                        s.generated[sp] = from;
                        break;
                    }
        }
    }
    if (!s.generated.empty() && !s.has_database) {
        std::string named;
        size_t k = 0;
        for (const auto& [sp, from] : s.generated) {
            if (k++ == 4) {
                named += ", and " + std::to_string(s.generated.size() - 4) + " more";
                break;
            }
            named += (named.empty() ? "" : ", ") + sp + " (from " + from + ")";
        }
        s.notes.push_back("this tree is not configured: " + std::to_string(s.generated.size()) + " header" +
                          (s.generated.size() == 1 ? "" : "s") + " its build generates " +
                          (s.generated.size() == 1 ? "is" : "are") + " not here -- " + named +
                          ". Configure it (./configure, or cmake), or put a compile_commands.json at its root, "
                          "and the files that include them are read with what they define");
    }
    s.include_dirs.assign(dirs.begin(), dirs.end());
    s.read_beyond.assign(beyond.begin(), beyond.end());
    s.notes.push_back(std::to_string(s.include_dirs.size()) + " include directories inferred from " +
                      std::to_string(spellings.size()) + " #include spellings; " +
                      std::to_string(s.ambiguous) + " answered by more than one file and left unresolved" +
                      (s.above ? "; " + std::to_string(s.above) + " not taken, because the directory they name is above " +
                                     (s.top.empty() ? std::string("the analysed root") : "the preset's top")
                               : std::string()));
    return s;
}

}  // namespace config
