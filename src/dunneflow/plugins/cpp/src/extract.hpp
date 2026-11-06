// One file in, one `FileFacts` out, from one parse — and, from the same parse, what the
// edge pass will need to know about every call this file makes.
//
// **Structure from the AST, spelling from the tokens.** clang says what a thing *is*: a
// definition, a call, a construction, a loop. What the map *shows* is what the author wrote,
// so every name, header and argument is taken from the file's own tokens (rules 8 and 75),
// folded by the same algorithm the syntactic reader used (`names.py`), so `cpp.yaml` and the
// dotted contract hold unchanged. One tokenisation per file serves every question.
//
// **Only what is in this file is this file's.** A translation unit holds every header it
// includes; a cursor whose expansion is not in the main file is somebody else's fact and is
// never descended into. A header is parsed as its own main file, so its facts never depend
// on which file included it (rule 66).
//
// **What carries over from the syntactic reader, deliberately** (`extractors/cpp`, retired
// by this reader):
//   - a declaration with no body is not a routine; a routine's identity is
//     `definition_id(file, qualname, ordinal)` (rule 106);
//   - the module is not in a C++ qualname, and a namespace or a record is;
//   - lambdas are not routines, and their calls are their enclosing routine's;
//   - a macro in declaration position is a decorator, and so is each identifier argument
//     of it (`UFUNCTION(BlueprintCallable)`), because that is what the entrypoint grammar
//     can match;
//   - a ternary is not a control point, and an STL algorithm is a call, not a loop.
//
// **What changed, because a compiler now reads it:**
//   - only the active `#if` arm is read; the skipped lines are counted, not guessed at;
//   - `std::ifstream f(path);` is a construction of `std.ifstream`, because clang knows it
//     is one — the syntactic reader's documented refusal was never implemented;
//   - a call written through a macro is named by the macro as written (`UE_LOG(...)`);
//   - an overloaded operator is not a call here, as it was not before.

#pragma once

#include <algorithm>
#include <cctype>
#include <climits>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <map>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "clang.hpp"
#include "facts.hpp"
#include "ids.hpp"
#include "rules.hpp"

namespace extract {

// ------------------------------------------------------------------- tokens --- //

enum TokKind { PUNCT = CXToken_Punctuation, KEYWORD = CXToken_Keyword, IDENT = CXToken_Identifier,
               LITERAL = CXToken_Literal, COMMENT = CXToken_Comment };

struct Tok {
    int kind;
    std::string text;
    unsigned off;   // byte offset of the first character
    unsigned end;   // byte offset just past the last
    unsigned line;
};

// A name-like token: an identifier, or a keyword clang lexes as one (`this`, `operator`).
inline bool namey(const Tok& t) { return t.kind == IDENT || t.kind == KEYWORD; }

// ------------------------------------------------- what the edge pass needs --- //

// One call this file makes, as clang resolved it. Kept compact: the edge pass holds one of
// these for every call in the tree.
struct Site {
    std::string site_id, caller_id, expr;
    std::string seen;           // the file of the definition this translation unit sees, if any
    std::string usr;            // the referenced declaration's USR, or "" when clang named none
    std::string qualified;      // its qualified name, for a frontier
    std::string decl_file;      // where clang says the declaration is ("" when nowhere)
    bool is_method = false, is_virtual = false, is_dynamic = false, is_ctor = false;
    bool final_ = false;        // the method or its class is `final`
    bool construction = false;
    bool bound = false;         // a call through a function value
    bool untyped = false;       // an argument clang could not type, under an overload set
    std::string macro;          // the function-like macro written here, when it is not one call
    std::vector<std::string> macro_usrs;  // what it calls instead, when it calls several things
    bool macro_no_call = false;  // and its definition has nothing in it that could call anything
    std::string construct_usr;  // a construction's record
    std::string receiver_usr;   // a member call's receiver type
};

// One callee of the macro uses at one line, for the edge pass. Its USR is empty for a call
// clang could name nothing for: a function value, usually.
struct Reach {
    std::string file, def_id, routine_id, callee, usr, seen;
    long line = 0;
    long count = 1;
    std::vector<facts::BoundaryHit> hits;  // what it touches, if it leaves the tree
};

// One definition this file holds, as the edge pass names it to the host.
struct Def {
    std::string usr, file, name, qualname;
    int args = -1;
    std::string written;  // the parameter types as written; see `written_types`
    long line = 0;
    bool has_body = true;
    bool is_record = false;
    bool invalid = false;  // clang refused the declaration (a redefinition, conflicting types)
};

// A way in marked on a declaration whose body is not here, for the edge pass to bind by
// USR (`SuppliedBinding`).
struct Mark {
    std::string entrypoint_id, usr, name, qualname, written_at;
    int args = -1;
    std::string written;               // the parameter types as written; see `written_types`
    // The words a body rule may answer to: the macro's specifiers where the rule names one,
    // and otherwise every word of the marking macro, as `decorators` read it.
    std::vector<std::string> markers;
    bool pure = false;                 // declared `= 0`
};

// A method that overrides another, by USR, with its class.
struct Over {
    std::string usr, overridden, owner;
    bool has_body = false;
    std::string file, name;
    long line = 0;
};

struct Result {
    std::string facts_json;
    std::string hash;
    std::vector<Site> sites;
    std::vector<Reach> reaches;
    std::vector<Def> defs;
    std::vector<Over> overs;
    std::vector<std::pair<std::string, std::string>> bases;  // record USR -> base USR
    std::vector<Mark> marks;
    std::set<std::string> uses;  // USRs of routines named here as a value, not called
    std::string failed;          // a parse clang refused outright
    int fatal = 0, errors = 0;   // diagnostics in this file's parse
    std::string first_missing;   // the first include it could not find
    long skipped_lines = 0;      // lines in inactive #if arms of this file
    long misread = 0;            // functions clang read as variables, recovered from the tokens
    long asm_statements = 0;     // inline assembly, which nothing here can read
    long asm_labels = 0;         // functions and variables renamed for the linker
    long unnamed_calls = 0;      // in a body nobody wrote here, with no name clang could give
    // A fragment (`.inl`, `.ipp`) is read through a file that includes it. `through` is that
    // file, relative, once it was; `not_included` says the includer's parse never reached
    // it (an inactive guard), so the caller tries the next includer or reads it alone.
    std::string through;
    bool not_included = false;
    bool fragment = false;       // a fragment, by suffix, however it ended up being read
    std::string rel;             // the file's own path, relative, for what the edge pass says of it
    std::vector<std::string> included;  // what this parse included, absolute: see `inclusions`
};

// ------------------------------------------------------------------ folding --- //

inline const std::set<std::string> NOT_A_NAME = {
    "return", "if", "while", "for", "switch", "case", "do", "else", "throw", "sizeof",
    "alignof", "static_cast", "dynamic_cast", "const_cast", "reinterpret_cast", "typeid",
    "noexcept", "decltype", "delete", "co_await", "co_return", "co_yield", "new"};

inline const std::set<std::string> EXITS = {"return", "throw", "continue", "break", "goto", "co_return"};

struct Ctx {
    std::string rel, module, text;
    bool through = false;  // parsed as part of an includer's translation unit
    std::string root;  // the analysed root, generic separators, with a trailing '/'
    std::vector<Tok> toks;
    std::vector<unsigned> line_starts;
    CXTranslationUnit tu = nullptr;
    const rules::Rules* rules = nullptr;
    facts::FileFacts ff;
    Result* out = nullptr;
    std::vector<std::pair<unsigned, unsigned>> macro_spans;  // expansions in this file, by offset
    std::map<unsigned, std::string> macro_names;             // their names, by start offset
    // What no scan may read as code, as (first token's offset, last token's offset), sorted
    // and disjoint: every directive line with its continuations, and every inactive `#if`
    // arm. `clang_tokenize` lexes the raw text, so both are in `toks`; read as code, an
    // inactive arm's calls were recorded beside the active one's and `#if !defined(LINUX)`
    // was a control point with four calls to `defined` in it (nmap's `NmapOps.cc`).
    std::vector<std::pair<unsigned, unsigned>> pp_spans;
    bool in_pp(unsigned off) const {
        auto it = std::upper_bound(pp_spans.begin(), pp_spans.end(), std::make_pair(off, ~0u));
        return it != pp_spans.begin() && std::prev(it)->second >= off;
    }

    // The macro expansion written in this file that holds this offset, if one does.
    const std::pair<unsigned, unsigned>* macro_at(unsigned off) const {
        auto it = std::upper_bound(macro_spans.begin(), macro_spans.end(), std::make_pair(off, ~0u));
        while (it != macro_spans.begin()) {
            --it;
            if (it->second >= off) return &*it;
            if (it->first + 4096 < off) break;  // spans are short; a long scan back finds nothing
        }
        return nullptr;
    }
    bool in_macro(unsigned off) const { return macro_at(off) != nullptr; }
    // Is `name` written, as a token, inside the expansion that holds `off`?
    bool written_in_macro(unsigned off, const std::string& name) const {
        const auto* m = macro_at(off);
        if (!m) return true;
        for (size_t i = tok_at(m->first); i < toks.size() && toks[i].off <= m->second; i++)
            if (toks[i].text == name) return true;
        return false;
    }

    unsigned line_of(unsigned off) const {
        auto it = std::upper_bound(line_starts.begin(), line_starts.end(), off);
        return static_cast<unsigned>(it - line_starts.begin());
    }
    // The first token at or after `off`.
    size_t tok_at(unsigned off) const {
        auto it = std::lower_bound(toks.begin(), toks.end(), off,
                                   [](const Tok& t, unsigned o) { return t.off < o; });
        return static_cast<size_t>(it - toks.begin());
    }
    std::string slice(size_t a, size_t b) const {  // tokens a..b inclusive, as written
        if (a >= toks.size() || b >= toks.size() || b < a) return "";
        return text.substr(toks[a].off, toks[b].end - toks[a].off);
    }
};

// Step over a `<…>` argument list, or return `i` unchanged — only where it balances.
inline size_t skip_template(const std::vector<Tok>& t, size_t i) {
    if (i >= t.size() || t[i].kind != PUNCT || t[i].text != "<") return i;
    int depth = 0;
    for (size_t j = i; j < t.size(); j++) {
        if (t[j].kind != PUNCT) continue;
        const std::string& x = t[j].text;
        if (x == "<") depth++;
        else if (x == ">") {
            if (--depth == 0) return j + 1;
        } else if (x == ">>") {
            depth -= 2;
            if (depth <= 0) return j + 1;
        } else if (x == ";" || x == "{" || x == "}") return i;
    }
    return i;
}

inline long matching(const std::vector<Tok>& t, size_t i, size_t hi = SIZE_MAX) {
    if (i >= t.size()) return -1;
    std::string open = t[i].text, close = open == "(" ? ")" : open == "[" ? "]" : open == "{" ? "}" : "";
    if (close.empty()) return -1;
    int depth = 0;
    for (size_t j = i; j < t.size() && j <= hi; j++) {
        if (t[j].kind != PUNCT) continue;
        if (t[j].text == open) depth++;
        else if (t[j].text == close && --depth == 0) return static_cast<long>(j);
    }
    return -1;
}

inline bool joiner(const Tok& t) { return t.kind == PUNCT && (t.text == "::" || t.text == "." || t.text == "->"); }

// `names.fold`: the name beginning at `i`, through calls in the middle; "" when unnameable.
inline std::string fold(const std::vector<Tok>& t, size_t i, size_t& end) {
    std::vector<std::string> parts;
    bool unnameable = false;
    size_t n = t.size();
    while (i < n) {
        if (!namey(t[i]) || NOT_A_NAME.count(t[i].text)) break;
        parts.push_back(t[i].text);
        i = skip_template(t, i + 1);
        while (i < n && t[i].kind == PUNCT && (t[i].text == "(" || t[i].text == "[")) {
            long close = matching(t, i);
            if (close < 0) {
                end = i;
                return "";
            }
            if (t[i].text == "[") unnameable = true;
            i = skip_template(t, static_cast<size_t>(close) + 1);
        }
        if (i < n && joiner(t[i])) {
            i++;
            if (i < n && t[i].kind == PUNCT && (t[i].text == "*" || t[i].text == "~")) {
                if (t[i].text == "~" && i + 1 < n && namey(t[i + 1])) {
                    parts.push_back("~" + t[i + 1].text);
                    i += 2;
                    continue;
                }
                end = i + 1;
                return "";
            }
            continue;
        }
        break;
    }
    end = i;
    if (unnameable || parts.empty()) return "";
    std::string out;
    for (size_t k = 0; k < parts.size(); k++) out += (k ? "." : "") + parts[k];
    return out;
}

// `names.fold_declarator`: the same chain, stopping at the first `(`.
inline std::string fold_declarator(const std::vector<Tok>& t, size_t i, size_t& end) {
    std::vector<std::string> parts;
    size_t n = t.size();
    while (i < n) {
        if (!namey(t[i]) || NOT_A_NAME.count(t[i].text) || t[i].text == "operator") break;
        parts.push_back(t[i].text);
        i = skip_template(t, i + 1);
        if (i < n && joiner(t[i])) {
            i++;
            if (i < n && t[i].kind == PUNCT && t[i].text == "~") {
                if (i + 1 < n && namey(t[i + 1])) {
                    parts.push_back("~" + t[i + 1].text);
                    i += 2;
                    if (i < n && joiner(t[i])) {
                        i++;
                        continue;
                    }
                    break;
                }
                end = i;
                return "";
            }
            continue;
        }
        break;
    }
    end = i;
    std::string out;
    for (size_t k = 0; k < parts.size(); k++) out += (k ? "." : "") + parts[k];
    return out;
}

// A type as clang spells it, folded to a dotted name: `std::basic_string<char>` is
// `std.basic_string`, `const Foo &` is `Foo`.
inline std::string fold_type(std::string s) {
    for (const char* q : {"const ", "volatile ", "struct ", "class ", "union ", "enum "}) {
        size_t p;
        while ((p = s.find(q)) != std::string::npos) s.erase(p, std::strlen(q));
    }
    std::string out;
    int depth = 0;
    for (size_t i = 0; i < s.size(); i++) {
        char c = s[i];
        if (c == '<') depth++;
        else if (c == '>') depth--;
        else if (depth == 0) {
            if (c == ':' && i + 1 < s.size() && s[i + 1] == ':') {
                out += '.';
                i++;
            } else if (c == '*' || c == '&' || c == ' ') {
                continue;
            } else {
                out += c;
            }
        }
    }
    return out;
}

inline bool looks_macro(const std::string& w) {
    bool upper = !w.empty();
    for (char c : w)
        if (std::islower(static_cast<unsigned char>(c))) upper = false;
    return upper && ((w.size() > 1 && w.find('_') != std::string::npos) || w.size() > 2);
}

inline std::string strip_comment(const std::string& raw) {
    // `_DOXYGEN`: the leading markers of each line, then blank lines trimmed at both ends.
    std::vector<std::string> lines;
    size_t i = 0;
    while (i <= raw.size()) {
        size_t e = raw.find('\n', i);
        if (e == std::string::npos) e = raw.size();
        std::string line = raw.substr(i, e - i);
        size_t p = 0;
        while (p < line.size() && (line[p] == ' ' || line[p] == '\t')) p++;
        size_t q = p;
        if (line.compare(q, 2, "/*") == 0) {
            q += 2;
            while (q < line.size() && line[q] == '*') q++;
            if (q < line.size() && line[q] == '<') q++;
        } else if (line.compare(q, 2, "//") == 0) {
            q += 2;
            while (q < line.size() && line[q] == '/') q++;
            if (q < line.size() && (line[q] == '<' || line[q] == '!')) q++;
        } else if (q < line.size() && line[q] == '*') {
            while (q < line.size() && line[q] == '*') q++;
            if (q < line.size() && line[q] == '/') q++;
        }
        if (q > p && q < line.size() && line[q] == ' ') q++;
        line = q > p ? line.substr(q) : line;
        // A closing `*/` at the end of a line.
        size_t close = line.rfind("*/");
        if (close != std::string::npos && close + 2 == line.size()) line.erase(close);
        while (!line.empty() && (line.back() == ' ' || line.back() == '\t' || line.back() == '\r')) line.pop_back();
        lines.push_back(line);
        i = e + 1;
    }
    while (!lines.empty() && lines.front().find_first_not_of(" \t") == std::string::npos) lines.erase(lines.begin());
    while (!lines.empty() && lines.back().find_first_not_of(" \t") == std::string::npos) lines.pop_back();
    std::string out;
    for (size_t k = 0; k < lines.size(); k++) out += (k ? "\n" : "") + lines[k];
    size_t a = out.find_first_not_of(" \t\n"), b = out.find_last_not_of(" \t\n");
    return a == std::string::npos ? "" : out.substr(a, b - a + 1);
}

// ------------------------------------------------------------- clang helpers --- //

inline clang::Api& C() { return clang::api(); }

inline std::string spelling(CXCursor c) { return clang::str(C().clang_getCursorSpelling(c)); }

// A routine's name as written. clang spells a class template's constructor and destructor
// with the template's parameters, `TTransform<T>` and `~TRWScopeLock<MutexType>`, which
// nobody writes and nobody searches for.
// A constructor *template* is a FunctionTemplate cursor spelled the same way, so the rule
// is the spelling's: a name with `<` that is not an operator's is a class template's.
inline std::string routine_name(CXCursor c) {
    std::string n = spelling(c);
    size_t lt = n.find('<');
    if (lt != std::string::npos && n.compare(0, 8, "operator") != 0) n.resize(lt);
    return n;
}

// A location's offset in this file, through macro expansions to where it was written.
inline bool offset_of(CXSourceLocation loc, unsigned& off) {
    CXFile f = nullptr;
    unsigned line = 0, col = 0;
    C().clang_getFileLocation(loc, &f, &line, &col, &off);
    return f != nullptr;
}

// Is this cursor this file's, by where it was *expanded*? `clang_Location_isFromMainFile`
// asks where it was spelled, and a call a macro writes is spelled in the macro's header:
// git's `skip_prefix(s, p, &o)` is `skip_prefix_impl(...)` written in `git-compat-util.h`, and
// even `assert(f(x))`'s `f(x)` sat under a cursor that test called somebody else's. The walk
// stopped at each one, and 22,348 of git's calls had nothing to say where they went.
inline CXFile& main_file() {
    thread_local CXFile f = nullptr;
    return f;
}
inline bool in_main(CXCursor c) {
    CXFile f = nullptr;
    C().clang_getExpansionLocation(C().clang_getCursorLocation(c), &f, nullptr, nullptr, nullptr);
    return f && main_file() && C().clang_File_isEqual(f, main_file());
}

inline void extent(CXCursor c, unsigned& a, unsigned& b) {
    CXSourceRange r = C().clang_getCursorExtent(c);
    offset_of(C().clang_getRangeStart(r), a);
    offset_of(C().clang_getRangeEnd(r), b);
    if (b < a) b = a;
}

inline bool is_function_kind(CXCursorKind k) {
    return k == CXCursor_FunctionDecl || k == CXCursor_CXXMethod || k == CXCursor_Constructor ||
           k == CXCursor_Destructor || k == CXCursor_ConversionFunction || k == CXCursor_FunctionTemplate;
}
inline bool is_record_kind(CXCursorKind k) {
    return k == CXCursor_ClassDecl || k == CXCursor_StructDecl || k == CXCursor_UnionDecl ||
           k == CXCursor_ClassTemplate || k == CXCursor_ClassTemplatePartialSpecialization;
}

// What this cursor is called inside the program: namespaces and records, outermost first.
// Function scopes are passed through and reported, because a local class is nested in a
// body and the body is not part of its name (the syntactic reader's rule, kept).
inline std::vector<std::string> scope_parts(CXCursor c, bool& nested, std::string& record) {
    std::vector<std::string> parts;
    nested = false;
    record.clear();
    bool first_record = true;
    for (CXCursor p = C().clang_getCursorSemanticParent(c);
         !C().clang_Cursor_isNull(p) && C().clang_getCursorKind(p) != CXCursor_TranslationUnit;
         p = C().clang_getCursorSemanticParent(p)) {
        CXCursorKind k = C().clang_getCursorKind(p);
        if (k == CXCursor_Namespace) {
            // An inline namespace (libc++'s `std::__1`) is not part of what anybody writes.
            if (!C().clang_Cursor_isAnonymous(p) && !C().clang_Cursor_isInlineNamespace(p)) parts.push_back(spelling(p));
        } else if (is_record_kind(k) || k == CXCursor_EnumDecl) {
            std::string name = spelling(p);
            if (!name.empty() && !C().clang_Cursor_isAnonymous(p)) {
                parts.push_back(name);
                if (first_record) record = name;
            }
            first_record = false;
        } else if (is_function_kind(k)) {
            nested = true;
        }
    }
    std::reverse(parts.begin(), parts.end());
    return parts;
}

inline std::string join(const std::vector<std::string>& parts, const std::string& last) {
    std::string out;
    for (const auto& p : parts) out += p + ".";
    return out + last;
}

inline std::string usr(CXCursor c) { return clang::str(C().clang_getCursorUSR(c)); }

// `final` on a method or a class: the `final` attribute among its children.
inline bool has_final(CXCursor c) {
    if (C().clang_Cursor_isNull(c) || !C().clang_Cursor_hasAttrs(c)) return false;
    bool found = false;
    C().clang_visitChildren(
        c,
        [](CXCursor k, CXCursor, CXClientData d) {
            if (C().clang_getCursorKind(k) == CXCursor_CXXFinalAttr) {
                *static_cast<bool*>(d) = true;
                return CXChildVisit_Break;
            }
            return CXChildVisit_Continue;
        },
        &found);
    return found;
}

// ------------------------------------------------------------------- reader --- //

struct Routine {
    facts::Routine r;
    unsigned decl_lo = 0;               // where the declaration starts, header and all
    unsigned body_lo = 0, body_hi = 0;  // offsets of `{` and `}`
    bool macro_written = false;         // no `{` is written here: a macro wrote the opening
    bool half_written = false;          // and somebody wrote the rest: `BEGIN hand(); END`
    size_t ff_index = 0;                // its row in `FileFacts.routines`
};

class Reader {
public:
    Reader(Ctx& ctx) : x_(ctx) {}

    void run() {
        CXCursor root = C().clang_getTranslationUnitCursor(x_.tu);
        collect_macros(root);
        module_scope_ = make_module_scope();
        scope_.r = module_scope_;
        scope_.macro_written = true;
        visit(root);
        // Calls and control are read from the tokens once the walk has said what each written
        // call reaches, routine by routine, in the order the routines were defined.
        for (const auto& r : routines_) {
            scan_calls(r.get());
            emit_calls(r.get());
            scan_control(r.get());
        }
        // The module scope is a routine only where something belongs to it, and a call does.
        if (!pending_[&scope_].empty()) {
            emit_calls(&scope_);
            x_.ff.routines.push_back(module_scope_);
            module_scope_used_ = true;
        }
        literals();
        macro_sites();
        macro_reaches();
        if (module_scope_used_) x_.ff.module_scope = module_scope_;
    }

private:
    Ctx& x_;
    std::vector<Routine*> stack_;               // routines being read, innermost last
    std::vector<std::unique_ptr<Routine>> routines_;
    std::map<std::string, int> seen_routines_, seen_records_;
    std::map<std::pair<std::string, std::string>, int> site_ordinals_;
    std::set<std::pair<std::string, unsigned>> stream_lines_;
    std::set<unsigned> annotated_;              // declaration offsets already given an entrypoint
    std::vector<CXCursor> vars_;               // variable declarations being read, innermost last
    std::map<unsigned, std::vector<CXCursor>> walked_;  // records and enums already walked, by hash
    std::set<unsigned> macros_that_declare_;   // by the expansion's offset
    std::set<unsigned> macros_that_annotate_;  // and those written directly before a declaration
    std::vector<std::pair<unsigned, unsigned>> declaration_spans_;  // each top-level declaration's extent
    facts::Routine module_scope_;
    bool module_scope_used_ = false;
    Routine scope_;                            // the module scope, as the owner of a call
    bool in_initialiser_ = false;              // under a variable with no routine around it
    int unevaluated_ = 0;                      // under `sizeof` and its relatives

    // ------------------------------------------------------------ walking --- //

    struct Frame {
        Reader* self;
    };

    static CXChildVisitResult trampoline(CXCursor c, CXCursor parent, CXClientData d) {
        static_cast<Reader*>(d)->one(c, parent);
        return CXChildVisit_Continue;
    }

    void visit(CXCursor c) { C().clang_visitChildren(c, trampoline, this); }

    bool first_walk(CXCursor c) {
        auto& met = walked_[C().clang_hashCursor(c)];
        for (const auto& o : met)
            if (C().clang_equalCursors(o, c)) return false;
        met.push_back(c);
        return true;
    }

    void one(CXCursor c, CXCursor parent) {
        CXCursorKind k = C().clang_getCursorKind(c);
        if (!in_main(c)) {
            // Somebody else's fact, and never descended into -- except, for a fragment read
            // through its includer, the scopes the includer opened around the `#include`:
            // `namespace UE { #include "Foo.inl" }` puts the fragment's definitions inside
            // a namespace cursor that is the includer's, and a class body can hold an
            // X-macro fragment's members the same way. Nothing of the includer's is
            // recorded; its children are each asked again.
            if (x_.through && (k == CXCursor_Namespace || k == CXCursor_LinkageSpec ||
                               k == CXCursor_UnexposedDecl || is_record_kind(k)) &&
                (!is_record_kind(k) || first_walk(c)))
                visit(c);
            return;
        }

        // A macro holding the end of a declaration wrote something, so it decorates nothing
        // that comes after it: `decorators`.
        if (C().clang_isDeclaration(k)) {
            unsigned a, b;
            extent(c, a, b);
            if (const auto* m = x_.macro_at(b)) macros_that_declare_.insert(m->first);
            // A use anywhere in a top-level declaration is part of declaring it. Those do not
            // nest, or a thousand fields would be a thousand spans to walk back over.
            CXCursorKind pk = C().clang_getCursorKind(parent);
            bool container = k == CXCursor_Namespace || k == CXCursor_LinkageSpec || k == CXCursor_UnexposedDecl;
            bool top = C().clang_getCursorKind(C().clang_getCursorSemanticParent(c)) == CXCursor_TranslationUnit ||
                       pk == CXCursor_TranslationUnit || pk == CXCursor_Namespace || pk == CXCursor_LinkageSpec ||
                       pk == CXCursor_UnexposedDecl;
            if (top && !container) declaration_spans_.push_back({a, b});
        }

        if (k == CXCursor_InclusionDirective) return include(c);
        if (k == CXCursor_MacroDefinition) return define(c);
        if (k == CXCursor_MacroExpansion) return;

        if (is_function_kind(k)) {
            annotations(c);
            if (C().clang_isCursorDefinition(c)) {
                Routine* r = routine(c);
                if (r) {
                    stack_.push_back(r);
                    visit(c);
                    stack_.pop_back();
                    return;
                }
            } else {
                overrides(c, nullptr);
            }
            visit(c);
            return;
        }
        if ((is_record_kind(k) || k == CXCursor_EnumDecl) && C().clang_isCursorDefinition(c)) {
            // Once, though the walk meets it twice: `struct X { X() {} } g;` is a declaration
            // and again the child of `g`'s, which read every method in it twice. By the cursor
            // and not by extent, because a macro that writes two records gives both of them
            // the macro's own extent.
            if (!first_walk(c)) return;
            record(c, k);
            visit(c);
            return;
        }
        if (k == CXCursor_VarDecl && stack_.empty()) {
            unsigned lo, hi;
            if (misread_function(c, lo, hi) && routine(c, lo, hi)) {
                x_.out->misread++;
                return;
            }
            constant(c);
            // **A variable's initialiser runs before `main`**, and nothing about it says so:
            // `int g = connect(...);` is as much a call as one in a body. The module scope owns
            // what no function does (rule 18).
            bool outer = in_initialiser_;
            in_initialiser_ = true;
            visit(c);
            in_initialiser_ = outer;
            return;
        }
        if (k == CXCursor_EnumConstantDecl) enumerator(c);
        if (k == CXCursor_VarDecl && !stack_.empty()) {
            // Held so a construction under it can be told from a call: `Foo x{a}` reaches its
            // constructor through an initialiser list, not as the declaration's own child.
            // And its name is a declaration, so `int x(5)` is not a call to `x`.
            unsigned at;
            // Only a name written here: a variable a macro declares maps to the macro's own
            // name, and Unreal's `UE_LOG` declares `LOG_Static(Format, ...)`, so every
            // `UE_LOG(...)` read as a declaration and not a call (1,825 to 43 in Core).
            if (offset_of(C().clang_getCursorLocation(c), at) && !x_.in_macro(at)) var_names_.insert(at);
            vars_.push_back(c);
            visit(c);
            vars_.pop_back();
            return;
        }

        // `sizeof(f(x))` runs nothing, and neither does anything else under this cursor kind, which
        // is only `sizeof`, `alignof` and their relatives: `UE_ARRAY_COUNT` is not a call to its
        // helper. A hand-written one is still scanned; this is what clang is asked to attribute.
        if (k == CXCursor_UnaryExpr) {
            unevaluated_++;
            visit(c);
            unevaluated_--;
            return;
        }
        if (!stack_.empty() && stack_.back()->macro_written && !stack_.back()->half_written) {
            std::string word = k == CXCursor_ForStmt || k == CXCursor_CXXForRangeStmt ? "for"
                               : k == CXCursor_WhileStmt                              ? "while"
                               : k == CXCursor_DoStmt                                 ? "do"
                               : k == CXCursor_IfStmt                                 ? "if"
                               : k == CXCursor_SwitchStmt                             ? "switch"
                               : k == CXCursor_CXXTryStmt                             ? "try"
                                                                                      : "";
            if (!word.empty()) {
                macro_control(stack_.back(), word);
                macro_depth_++;
                visit(c);
                macro_depth_--;
                return;
            }
        }
        if (k == CXCursor_AsmStmt || k == CXCursor_MSAsmStmt) {
            x_.out->asm_statements++;
            if (!stack_.empty()) {
                auto& row = x_.ff.routines[stack_.back()->ff_index];
                row.opaque_asm = row.opaque_asm + 1;
            }
        }
        if (k == CXCursor_AsmLabelAttr) x_.out->asm_labels++;
        if (k == CXCursor_DeclRefExpr || k == CXCursor_MemberRefExpr) value_use(c);
        if (!stack_.empty()) {
            if (k == CXCursor_CallExpr) note_call(c, parent);
            else if (k == CXCursor_CXXNewExpr) note_new(c);
        } else if (in_initialiser_ && k == CXCursor_CallExpr) {
            note_call(c, parent);
        }
        visit(c);
    }

    // **A routine named and not called is a value**: `event_set(&ev, fd, EV_READ,
    // server_accept, NULL)`, `.exec = cmd_attach_session_exec`, `&UFoo::OnHit`. Told from a
    // call by what is written after the name -- a call writes `(` and a value does not --
    // and only where the name is the token written at this place, so a name a macro writes
    // is not mistaken for one the program does (`SuppliedUse`).
    void value_use(CXCursor c) {
        CXCursor ref = C().clang_getCursorReferenced(c);
        if (C().clang_Cursor_isNull(ref)) return;
        CXCursorKind rk = C().clang_getCursorKind(ref);
        if (rk != CXCursor_FunctionDecl && rk != CXCursor_CXXMethod && rk != CXCursor_FunctionTemplate) return;
        unsigned at;
        if (!offset_of(C().clang_getCursorLocation(c), at)) return;
        size_t i = x_.tok_at(at);
        if (i >= x_.toks.size() || x_.toks[i].off != at || x_.toks[i].text != spelling(ref)) return;
        if (i + 1 < x_.toks.size() && x_.toks[i + 1].text == "(") return;
        std::string u = usr(ref);
        if (!u.empty()) x_.out->uses.insert(u);
    }

    // ------------------------------------------------------- the preprocessor --- //

    void collect_macros(CXCursor root) {
        C().clang_visitChildren(
            root,
            [](CXCursor c, CXCursor, CXClientData d) {
                auto* self = static_cast<Reader*>(d);
                if (C().clang_getCursorKind(c) == CXCursor_MacroExpansion && in_main(c)) {
                    unsigned a, b;
                    extent(c, a, b);
                    self->x_.macro_spans.push_back({a, b});
                    self->x_.macro_names[a] = spelling(c);
                    self->macro_cursors_[a] = c;
                }
                return CXChildVisit_Continue;
            },
            this);
        std::sort(x_.macro_spans.begin(), x_.macro_spans.end());
    }

    void include(CXCursor c) {
        unsigned a, b;
        extent(c, a, b);
        facts::ImportRec im;
        im.module = spelling(c);
        im.name = "";
        im.alias = "";
        // Quoted or angled, off the text as written.
        size_t q = x_.text.find_first_of("\"<", a);
        im.is_from = q != std::string::npos && q < b && x_.text[q] == '"';
        im.line = x_.line_of(a);
        x_.ff.imports.push_back(im);
    }

    // An object-like macro with a value is a constant. Nothing else here is a fact.
    void define(CXCursor c) {
        unsigned a, b;
        extent(c, a, b);
        size_t i = x_.tok_at(a);
        if (i >= x_.toks.size() || !namey(x_.toks[i])) return;
        size_t j = i + 1;
        // A function-like macro has its `(` touching the name.
        if (j < x_.toks.size() && x_.toks[j].off < b && x_.toks[j].text == "(" && x_.toks[j].off == x_.toks[i].end) return;
        if (j >= x_.toks.size() || x_.toks[j].off >= b) return;  // `#define GUARD_H`: no value
        size_t last = j;
        while (last + 1 < x_.toks.size() && x_.toks[last + 1].off < b) last++;
        facts::Constant k;
        k.name = x_.toks[i].text;
        k.value = x_.slice(j, last);
        k.line = x_.line_of(a);
        k.is_final = true;
        x_.ff.constants.push_back(k);
    }

    // The macros written immediately before a declaration, each with its identifier arguments:
    // `UFUNCTION(BlueprintCallable, Category="Combat")` -> UFUNCTION, BlueprintCallable, Category.
    std::vector<std::string> decorators(unsigned decl_start, unsigned& first) {
        std::vector<std::string> out;
        first = decl_start;
        std::vector<std::pair<unsigned, unsigned>> found;
        unsigned at = decl_start;
        while (true) {
            size_t p = at;
            while (p > 0 && std::isspace(static_cast<unsigned char>(x_.text[p - 1]))) p--;
            auto it = std::find_if(x_.macro_spans.begin(), x_.macro_spans.end(),
                                   [&](const std::pair<unsigned, unsigned>& s) { return s.second == p; });
            if (it == x_.macro_spans.end() || it->first >= at) break;
            // A macro that wrote a declaration is that declaration, not this one's decorator:
            // `WHOLE(a)` then `void b() {}` had `b` starting on `WHOLE`'s line.
            if (macros_that_declare_.count(it->first)) break;
            macros_that_annotate_.insert(it->first);
            // `#include UE_INLINE_GENERATED_CPP_BY_NAME(X)` touches what follows it and is not
            // written on it: a directive decorates nothing.
            size_t line = x_.line_starts[x_.line_of(it->first) - 1];
            while (line < it->first && std::isspace(static_cast<unsigned char>(x_.text[line]))) line++;
            if (x_.text[line] == '#') break;
            found.push_back(*it);
            at = it->first;
        }
        std::reverse(found.begin(), found.end());
        for (const auto& [a, b] : found) {
            const std::string& name = x_.macro_names[a];
            if (!looks_macro(name)) continue;
            first = std::min(first, a);
            out.push_back(name);
            size_t i = x_.tok_at(a) + 1;
            for (; i < x_.toks.size() && x_.toks[i].off < b; i++)
                if (x_.toks[i].kind == IDENT && std::find(out.begin(), out.end(), x_.toks[i].text) == out.end())
                    out.push_back(x_.toks[i].text);
        }
        return out;
    }

    // `UFUNCTION(reliable, Category=Client, meta=(exec))` -> reliable: the identifiers directly
    // in the macro's own parentheses, and not what a `=` gives one of them.
    std::vector<std::string> specifiers(unsigned decl_start, const std::string& macro) {
        std::vector<std::string> out;
        unsigned at = decl_start;
        while (true) {
            size_t p = at;
            while (p > 0 && std::isspace(static_cast<unsigned char>(x_.text[p - 1]))) p--;
            auto it = std::find_if(x_.macro_spans.begin(), x_.macro_spans.end(),
                                   [&](const std::pair<unsigned, unsigned>& s) { return s.second == p; });
            if (it == x_.macro_spans.end() || it->first >= at || macros_that_declare_.count(it->first)) return out;
            at = it->first;
            if (x_.macro_names[at] != macro) continue;
            int depth = 0;
            bool value = false;
            for (size_t i = x_.tok_at(at) + 1; i < x_.toks.size() && x_.toks[i].off < it->second; i++) {
                const std::string& t = x_.toks[i].text;
                if (t == "(") depth++;
                else if (t == ")") depth--;
                else if (depth == 1 && t == ",") value = false;
                else if (depth == 1 && t == "=") value = true;
                else if (depth == 1 && !value && x_.toks[i].kind == IDENT) out.push_back(t);
            }
            return out;
        }
    }

    // **The parameter types as written**, one string per declaration of a function, so that a
    // declaration and its definition can be compared when their USRs cannot: parameter names,
    // defaults, `class`/`struct`/`enum`/`typename` and a leading annotation macro
    // (`UPARAM(ref)`) are what the two may differ by and still be one function. Empty when the
    // name is not written here, which a macro-written function or an operator may not be: then
    // nothing is compared. `const T` unnamed loses its `T` as a name would, and so does not
    // match: a miss leaves a way in visibly unbound, and never binds the wrong overload.
    std::string written_types(const std::string& name, unsigned from, unsigned to) const {
        size_t i = x_.tok_at(from);
        for (; i + 1 < x_.toks.size() && x_.toks[i].off < to; i++)
            if (x_.toks[i].text == name && x_.toks[i + 1].text == "(") break;
        if (i + 1 >= x_.toks.size() || x_.toks[i].off >= to || x_.toks[i].text != name) return "";
        std::string out = "(";
        std::vector<const Tok*> param;
        auto flush = [&]() {
            size_t from_ = 0, depth_ = 0;
            if (param.size() > 1 && param[0]->kind == IDENT && looks_macro(param[0]->text) && param[1]->text == "(") {
                for (size_t k = 1; k < param.size(); k++) {
                    if (param[k]->text == "(") depth_++;
                    else if (param[k]->text == ")" && --depth_ == 0) {
                        from_ = k + 1;
                        break;
                    }
                }
            }
            std::vector<std::string> kept;
            bool named = false;
            for (size_t k = from_; k < param.size() && param[k]->text != "="; k++) {
                const std::string& t = param[k]->text;
                named = param[k]->kind == IDENT;
                if (t != "class" && t != "struct" && t != "enum" && t != "typename") kept.push_back(t);
            }
            if (kept.size() > 1 && named) kept.pop_back();
            for (const auto& t : kept) out += t + " ";
            out += ",";
            param.clear();
        };
        int depth = 0, angle = 0;
        for (size_t k = i + 2; k < x_.toks.size(); k++) {
            const Tok& t = x_.toks[k];
            if (t.kind == COMMENT) continue;
            if (t.text == "(" || t.text == "[" || t.text == "{") depth++;
            else if (t.text == ")" && depth == 0) {
                if (!param.empty()) flush();
                return out + ")";
            } else if (t.text == ")" || t.text == "]" || t.text == "}") depth--;
            else if (t.text == "<") angle++;
            else if (t.text == ">") angle--;
            else if (t.text == ">>") angle -= 2;
            else if (t.text == "," && depth == 0 && angle <= 0) {
                flush();
                continue;
            }
            param.push_back(&t);
        }
        return "";
    }

    // The comment block that touches a declaration, stripped of its markers.
    std::optional<std::string> leading_comment(unsigned header_start) {
        size_t i = x_.tok_at(header_start);
        if (i == 0) return std::nullopt;
        size_t j = i;
        unsigned want = x_.line_of(header_start);
        std::vector<size_t> block;
        while (j > 0) {
            const Tok& t = x_.toks[j - 1];
            if (t.kind != COMMENT) break;
            unsigned end_line = x_.line_of(t.end > 0 ? t.end - 1 : t.end);
            if (end_line + 1 < want) break;   // a blank line: about something else
            // A comment that shares a line with code before it is that code's.
            if (j >= 2 && x_.toks[j - 2].kind != COMMENT && x_.toks[j - 2].line == t.line) break;
            block.push_back(j - 1);
            want = t.line;
            j--;
        }
        if (block.empty()) return std::nullopt;
        std::reverse(block.begin(), block.end());
        std::string raw;
        for (size_t k : block) raw += (raw.empty() ? "" : "\n") + x_.toks[k].text;
        std::string s = strip_comment(raw);
        if (s.empty()) return std::nullopt;
        return s;
    }

    // ------------------------------------------------------------ routines --- //

    facts::Routine make_module_scope() {
        facts::Routine r;
        std::string q = x_.module.empty() ? "<module>" : x_.module + ".<module>";
        r.id = ids::definition_id(x_.rel, q, 1);
        r.name = "<module>";
        r.qualname = q;
        r.module = x_.module;
        r.file = x_.rel;
        r.line_start = 1;
        r.line_end = std::max<int64_t>(1, static_cast<int64_t>(x_.line_starts.size()));
        return r;
    }

    // The body of a definition: its compound statement (or a function-try-block).
    bool body(CXCursor c, unsigned& lo, unsigned& hi) {
        struct B {
            CXCursor found;
            bool ok = false;
        } b;
        C().clang_visitChildren(
            c,
            [](CXCursor k, CXCursor, CXClientData d) {
                auto* b = static_cast<B*>(d);
                CXCursorKind kk = C().clang_getCursorKind(k);
                if (kk == CXCursor_CompoundStmt || kk == CXCursor_CXXTryStmt) {
                    b->found = k;
                    b->ok = true;
                }
                return CXChildVisit_Continue;
            },
            &b);
        if (!b.ok) return false;
        extent(b.found, lo, hi);
        // A function a macro writes whole has its body at the macro's own offset, where no
        // `{` is written: `void U::Set##Name(T v) { ... }`. Unreal's 67 pasted setters were
        // refused here as having no body, and so was every such function in any tree. All of
        // them are routines, marked `body_by`: leaving out what a macro wrote leaves out the
        // places a macro can hide something, and folding is the map's decision to make.
        if (x_.in_macro(lo)) return !C().clang_CXXMethod_isDefaulted(c);
        // `= default` is given a body by clang and has none as written: not a routine.
        size_t i = x_.tok_at(lo);
        return i < x_.toks.size() && x_.toks[i].off == lo && (x_.toks[i].text == "{" || x_.toks[i].text == "try");
    }

    // **A function clang read as a variable.** Where a parameter's type is a name clang knows as
    // something else, or a header that would have said otherwise is missing, `void U::F(X* p)`
    // is a legal variable `F` initialised with `X * p`, and the `{` after it a syntax error
    // clang recovers from by skipping the whole body. No function cursor exists, and no error
    // reaches this file's facts: AugmentedReality's `StartARSession` was simply not in its map.
    // A variable followed by `{` is not a variable, so the body is taken from the tokens. clang
    // kept nothing inside it, so its calls are named as written and counted as unresolved.
    bool misread_function(CXCursor c, unsigned& lo, unsigned& hi) {
        unsigned a, b;
        extent(c, a, b);
        // Its extent ends at its name, since clang has no type for it to initialise.
        size_t open = x_.tok_at(b);
        if (open >= x_.toks.size() || x_.toks[open].text != "(") return false;
        long shut = matching(x_.toks, open);
        if (shut < 0 || static_cast<size_t>(shut) + 1 >= x_.toks.size()) return false;
        size_t i = static_cast<size_t>(shut) + 1;
        if (x_.toks[i].text != "{") return false;
        if (x_.in_macro(a) || x_.in_macro(x_.toks[i].off)) return false;
        long close = matching(x_.toks, i);
        if (close < 0) return false;
        lo = x_.toks[i].off;
        hi = x_.toks[static_cast<size_t>(close)].off + 1;
        return true;
    }

    // Arguments as written between the `(` that ends at `end` and it: a misread function has no
    // cursor to ask. Commas inside `<...>` and `(...)` are not separators.
    int written_args(size_t end) const {
        int depth = 0, angle = 0, commas = 0;
        bool any = false;
        for (size_t i = end; i-- > 0;) {
            const std::string& t = x_.toks[i].text;
            if (t == ")" || t == "]") depth++;
            else if (t == "(" || t == "[") {
                if (depth == 0) return any ? commas + 1 : 0;
                depth--;
            } else if (t == ">") angle++;
            else if (t == "<") angle--;
            else if (t == ">>") angle += 2;
            else if (t == "," && depth == 0 && angle == 0) commas++;
            any = true;
        }
        return 0;
    }

    Routine* routine(CXCursor c) {
        unsigned lo, hi;
        if (!body(c, lo, hi)) return nullptr;  // `= default`, `= delete`: no body, no routine
        return routine(c, lo, hi);
    }

    Routine* routine(CXCursor c, unsigned lo, unsigned hi) {
        unsigned a, b;
        extent(c, a, b);
        bool nested;
        std::string record;
        auto parts = scope_parts(c, nested, record);
        std::string name = routine_name(c);
        if (name.find("type-parameter-") != std::string::npos) {
            // `operator T&()` is spelled `operator type-parameter-0-0 &`, clang's name for a
            // template parameter; the name is what is written, up to its `(`.
            unsigned at;
            if (offset_of(C().clang_getCursorLocation(c), at)) {
                std::string w;
                for (size_t i = x_.tok_at(at); i < x_.toks.size() && x_.toks[i].text != "("; i++) {
                    if (!w.empty() && namey(x_.toks[i]) && (std::isalnum(static_cast<unsigned char>(w.back())) || w.back() == '_'))
                        w += ' ';
                    w += x_.toks[i].text;
                    if (w.size() > 200) break;
                }
                if (w.compare(0, 8, "operator") == 0) name = w;
            }
        }
        if (name.rfind("__builtin", 0) == 0) {
            // **A program cannot define a builtin**, so a definition clang names
            // `__builtin___strlcat_chk` was renamed by a macro: macOS's `<string.h>`, under
            // `_FORTIFY_SOURCE`, has `#define strlcat(...) __builtin___strlcat_chk(...)`, and
            // tmux's `compat/strlcat.c` defines `strlcat` through it. The name is the one
            // written where the definition is.
            unsigned at;
            if (offset_of(C().clang_getCursorLocation(c), at)) {
                size_t i = x_.tok_at(at);
                if (i < x_.toks.size() && x_.toks[i].off == at && x_.toks[i].kind == IDENT) name = x_.toks[i].text;
            }
        }
        std::string qualname = join(parts, name);
        int n = ++seen_routines_[qualname];

        auto r = std::make_unique<Routine>();
        r->decl_lo = a;
        r->body_lo = lo;
        r->body_hi = hi;
        size_t first = x_.tok_at(lo);
        r->macro_written = !(first < x_.toks.size() && x_.toks[first].off == lo &&
                             (x_.toks[first].text == "{" || x_.toks[first].text == "try"));
        if (r->macro_written)
            for (size_t i = first; i < x_.toks.size() && x_.toks[i].off < hi && !r->half_written; i++)
                r->half_written = !x_.in_macro(x_.toks[i].off) && !x_.in_pp(x_.toks[i].off);
        facts::Routine& f = r->r;
        f.id = ids::definition_id(x_.rel, qualname, n);
        f.name = name;
        f.qualname = qualname;
        f.module = x_.module;
        f.file = x_.rel;
        unsigned header = a;
        f.decorators = decorators(a, header);
        f.line_start = x_.line_of(header);
        f.line_end = x_.line_of(hi > 0 ? hi - 1 : hi);
        f.name_by = written_by(C().clang_getCursorLocation(c));
        if (r->macro_written && x_.in_macro(lo)) f.body_by = def_of(x_.macro_at(lo)->first);
        CXCursorKind k = C().clang_getCursorKind(c);
        f.params = params(c, a, lo);
        if (k != CXCursor_Constructor && k != CXCursor_Destructor) {
            std::string ret = clang::str(C().clang_getTypeSpelling(C().clang_getCursorResultType(c)));
            if (!ret.empty()) f.returns = ret;
        }
        f.docstring = leading_comment(header);
        f.comments = body_comments(lo, hi);
        f.is_async = body_has(lo, hi, {"co_await", "co_return", "co_yield"});
        f.is_method = !record.empty();
        if (!record.empty()) f.class_name = record;
        f.is_nested = nested;
        CX_CXXAccessSpecifier acc = C().clang_getCXXAccessSpecifier(c);
        f.visibility = (acc == CX_CXXPrivate || acc == CX_CXXProtected) ? "private" : "public";
        f.body_hash = ids::hash_source(x_.text.substr(lo, hi - lo));
        r->ff_index = x_.ff.routines.size();
        x_.ff.routines.push_back(f);

        if (x_.rules->entry_names.count(name) && record.empty()) {
            facts::Entrypoint e;
            e.id = ids::entrypoint_id(x_.rel, {qualname, "main"});
            e.kind = facts::EntrypointKind::MAIN;
            e.name = name;
            e.routine_id = f.id;
            e.module = x_.module;
            e.evidence = name + "() at " + x_.rel + ":" + std::to_string(f.line_start);
            x_.ff.entrypoints.push_back(e);
        }

        Def d;
        d.usr = usr(c);
        d.file = x_.rel;
        d.line = f.line_start;
        d.name = name;
        d.qualname = qualname;
        d.args = C().clang_getCursorKind(c) == CXCursor_VarDecl
                     ? written_args(x_.tok_at(lo) > 0 ? x_.tok_at(lo) - 1 : 0)
                     : C().clang_Cursor_getNumArguments(c);
        // A function clang read as a variable keeps the count alone: that is what `written_args`
        // above is for, and such a definition is not held to what its declaration writes.
        if (C().clang_getCursorKind(c) != CXCursor_VarDecl) d.written = written_types(name, a, lo);
        // Said, not decided here: an invalid definition only loses a tie (`edges.hpp`).
        d.invalid = C().clang_isInvalidDeclaration(c) != 0;
        x_.out->defs.push_back(d);
        overrides(c, &f);

        routines_.push_back(std::move(r));
        return routines_.back().get();
    }

    // Every method this one overrides, by USR, for the dispatch rule.
    void overrides(CXCursor c, const facts::Routine* f) {
        if (C().clang_getCursorKind(c) != CXCursor_CXXMethod) return;
        CXCursor* over = nullptr;
        unsigned n = 0;
        C().clang_getOverriddenCursors(c, &over, &n);
        std::string me = usr(c);
        CXCursor owner = C().clang_getCursorSemanticParent(c);
        for (unsigned i = 0; i < n; i++) {
            Over o;
            o.usr = me;
            o.overridden = usr(over[i]);
            o.owner = usr(owner);
            o.has_body = f != nullptr;
            if (f) {
                o.file = *f->file;
                o.line = f->line_start;
                o.name = *f->name;
            }
            x_.out->overs.push_back(o);
        }
        if (over) C().clang_disposeOverriddenCursors(over);
    }

    std::vector<facts::Param> params(CXCursor c, unsigned decl_start, unsigned body_lo) {
        std::vector<facts::Param> out;
        int n = C().clang_Cursor_getNumArguments(c);
        for (int i = 0; i < n; i++) {
            CXCursor p = C().clang_Cursor_getArgument(c, static_cast<unsigned>(i));
            facts::Param q;
            q.name = spelling(p);
            std::string t = clang::str(C().clang_getTypeSpelling(C().clang_getCursorType(p)));
            if (!t.empty()) q.type = t;
            unsigned a, b;
            extent(p, a, b);
            size_t ti = x_.tok_at(a);
            for (size_t k = ti; k < x_.toks.size() && x_.toks[k].off < b; k++) {
                if (x_.toks[k].kind == PUNCT && x_.toks[k].text == "=") {
                    size_t last = k + 1;
                    while (last + 1 < x_.toks.size() && x_.toks[last + 1].off < b) last++;
                    if (last > k) q.default_ = x_.slice(k + 1, last);
                    break;
                }
            }
            q.kind = "positional";
            out.push_back(q);
        }
        // A C-style `...` is a parameter, and a signature missing one is about another routine.
        size_t i = x_.tok_at(decl_start);
        long open = -1;
        for (; i < x_.toks.size() && x_.toks[i].off < body_lo; i++)
            if (x_.toks[i].text == "(") {
                open = static_cast<long>(i);
                break;
            }
        if (open >= 0) {
            long close = matching(x_.toks, static_cast<size_t>(open));
            if (close > 0 && x_.toks[static_cast<size_t>(close) - 1].text == "...") {
                facts::Param v;
                v.name = "";
                v.kind = "vararg";
                out.push_back(v);
            }
        }
        return out;
    }

    std::vector<facts::Comment> body_comments(unsigned lo, unsigned hi) {
        std::vector<facts::Comment> out;
        for (size_t i = x_.tok_at(lo); i < x_.toks.size() && x_.toks[i].off < hi; i++) {
            const Tok& t = x_.toks[i];
            if (t.kind != COMMENT) continue;
            std::string s = strip_comment(t.text);
            if (s.empty()) continue;
            facts::Comment c;
            c.text = s;
            c.line = t.line;
            size_t line_start = x_.line_starts[t.line - 1];
            bool leading = true;
            for (size_t p = line_start; p < t.off; p++)
                if (!std::isspace(static_cast<unsigned char>(x_.text[p]))) leading = false;
            c.leading = leading;
            out.push_back(c);
        }
        return out;
    }

    bool body_has(unsigned lo, unsigned hi, std::initializer_list<const char*> words) {
        for (size_t i = x_.tok_at(lo); i < x_.toks.size() && x_.toks[i].off < hi; i++)
            for (const char* w : words)
                if (x_.toks[i].text == w) return true;
        return false;
    }

    // ------------------------------------------------- records and constants --- //

    void record(CXCursor c, CXCursorKind k) {
        unsigned a, b;
        extent(c, a, b);
        bool nested;
        std::string outer;
        auto parts = scope_parts(c, nested, outer);
        std::string name = spelling(c);
        if (name.empty() || C().clang_Cursor_isAnonymous(c)) {
            // A nameless record a macro wrote is the macro's, not this file's: every
            // `TAILQ_ENTRY(window) entry;` is a `struct { ... }`, and reading where they were
            // expanded rather than spelled gave tmux 190 structures called `<anonymous>`.
            // One written here by hand is still read, as it always was. Told apart by this
            // file's own expansion spans: libclang's spelling location of a macro body is
            // its expansion location, so it cannot say.
            if (x_.in_macro(a)) return;
            name = "<anonymous>";
        }
        std::string qualname = join(parts, name);
        int n = ++seen_records_[qualname];
        facts::DataStructure s;
        s.id = ids::definition_id(x_.rel, qualname, n);
        s.name = name;
        s.kind = k == CXCursor_EnumDecl ? facts::StructureKind::ENUM : facts::StructureKind::CLASS;
        s.module = x_.module;
        s.file = x_.rel;
        unsigned header = a;
        decorators(a, header);
        s.line = x_.line_of(header);
        s.docstring = leading_comment(header);
        s.name_by = written_by(C().clang_getCursorLocation(c));

        struct Walk {
            Reader* self;
            facts::DataStructure* s;
            std::string usr;
        } w{this, &s, usr(c)};
        C().clang_visitChildren(
            c,
            [](CXCursor k, CXCursor, CXClientData d) {
                auto* w = static_cast<Walk*>(d);
                CXCursorKind kk = C().clang_getCursorKind(k);
                if (kk == CXCursor_CXXBaseSpecifier) {
                    CXType t = C().clang_getCursorType(k);
                    std::string base = fold_type(clang::str(C().clang_getTypeSpelling(t)));
                    if (!base.empty()) w->s->bases.push_back(base);
                    CXCursor decl = C().clang_getTypeDeclaration(t);
                    if (!C().clang_Cursor_isNull(decl))
                        w->self->x_.out->bases.push_back({w->usr, extract::usr(decl)});
                } else if (kk == CXCursor_FieldDecl) {
                    facts::Field_ f;
                    f.name = spelling(k);
                    std::string t = clang::str(C().clang_getTypeSpelling(C().clang_getCursorType(k)));
                    if (!t.empty()) f.type = t;
                    f.default_ = w->self->initializer(k);
                    w->s->fields.push_back(f);
                }
                return CXChildVisit_Continue;
            },
            &w);
        x_.ff.structures.push_back(s);
        if (s.kind == facts::StructureKind::CLASS) {
            facts::ClassDef_ cd;
            cd.name = name;
            cd.qualname = qualname;
            cd.module = x_.module;
            cd.file = x_.rel;
            cd.line = s.line;
            cd.bases = s.bases;
            x_.ff.classes.push_back(cd);
        }
        Def d;
        d.usr = w.usr;
        d.file = x_.rel;
        d.line = s.line;
        d.name = name;
        d.qualname = qualname;
        d.is_record = true;
        x_.out->defs.push_back(d);
    }

    // What follows a top-level `=` in a declaration, as written.
    std::optional<std::string> initializer(CXCursor c) {
        unsigned a, b;
        extent(c, a, b);
        int depth = 0;
        for (size_t i = x_.tok_at(a); i < x_.toks.size() && x_.toks[i].off < b; i++) {
            const Tok& t = x_.toks[i];
            if (t.kind != PUNCT) continue;
            if (t.text == "(" || t.text == "[" || t.text == "{" || t.text == "<") depth++;
            else if (t.text == ")" || t.text == "]" || t.text == "}" || t.text == ">") depth--;
            else if (t.text == "=" && depth == 0) {
                size_t last = i + 1;
                if (last >= x_.toks.size() || x_.toks[last].off >= b) return std::nullopt;
                while (last + 1 < x_.toks.size() && x_.toks[last + 1].off < b) last++;
                return x_.slice(i + 1, last);
            }
        }
        return std::nullopt;
    }

    // `constexpr`/`const` at namespace, file or class scope, with a value. A local constant is
    // the internal computation this tool exists not to report.
    void constant(CXCursor c) {
        unsigned a, b;
        extent(c, a, b);
        bool constish = false;
        size_t i = x_.tok_at(a);
        for (size_t k = i; k < x_.toks.size() && k < i + 3 && x_.toks[k].off < b; k++)
            if (x_.toks[k].text == "constexpr" || x_.toks[k].text == "const" || x_.toks[k].text == "constinit")
                constish = true;
        if (!constish) return;
        auto value = initializer(c);
        if (!value) return;
        facts::Constant k;
        k.name = spelling(c);
        k.value = *value;
        k.line = x_.line_of(a);
        std::string t = clang::str(C().clang_getTypeSpelling(C().clang_getCursorType(c)));
        if (!t.empty()) k.type = t;
        k.is_final = true;
        k.private_ = !k.name->empty() && (*k.name)[0] == '_';
        x_.ff.constants.push_back(k);
    }

    void enumerator(CXCursor c) {
        unsigned a, b;
        extent(c, a, b);
        facts::Constant k;
        k.name = spelling(c);
        k.value = initializer(c).value_or("");
        k.line = x_.line_of(a);
        k.is_final = true;
        x_.ff.constants.push_back(k);
    }

    // Ways in a rule recognises by a decorator, read off declarations as well as definitions:
    // `UFUNCTION(BlueprintCallable) void Fire(int);` declares a way in from Blueprint, and the
    // body is usually in another file.
    void annotations(CXCursor c) {
        unsigned a, b;
        extent(c, a, b);
        if (!annotated_.insert(a).second) return;
        unsigned header;
        auto decs = decorators(a, header);
        if (decs.empty()) return;
        bool nested;
        std::string record;
        std::string qualname = join(scope_parts(c, nested, record), spelling(c));
        for (const auto& rule : x_.rules->entrypoints) {
            bool hit = false;
            for (const auto& d : decs) hit = hit || rule.matches(d);
            std::vector<std::string> specs;
            if (!rule.specifiers_of.empty()) specs = specifiers(a, rule.specifiers_of);
            for (const auto& s : specs) hit = hit || rule.matches_specifier(s);
            if (!hit) continue;
            facts::Entrypoint e;
            // **The USR is in the id**: two overloads of one name, both marked, were one
            // way in -- the second `INSERT OR REPLACE`d the first -- and 157 of Runtime's
            // Blueprint ways in were overloads. A name is not an identity (rule 106). **And
            // the USR is only as good as the parse**: two overloads whose types are both
            // missing have one, so what they write is in the id as well.
            std::string u = usr(c);
            std::string types = written_types(spelling(c), a, b);
            e.id = ids::entrypoint_id(x_.rel, {qualname, rule.kind, u, types});
            e.kind = rule.kind;
            e.name = spelling(c);
            if (C().clang_isCursorDefinition(c)) {
                // The routine is minted after this, with the next ordinal of its name.
                int n = seen_routines_.count(qualname) ? seen_routines_[qualname] + 1 : 1;
                e.routine_id = ids::definition_id(x_.rel, qualname, n);
            } else if (!u.empty()) {
                // The body is elsewhere -- a `.cpp`, a fragment, or nowhere in C++ at all --
                // and only the whole tree knows which: the edge pass binds it.
                Mark m;
                m.entrypoint_id = *e.id;
                m.usr = u;
                m.name = e.name ? *e.name : spelling(c);
                m.qualname = qualname;
                m.written_at = x_.rel + ":" + std::to_string(x_.line_of(a));
                m.args = C().clang_Cursor_getNumArguments(c);
                m.written = types;
                m.markers = rule.specifiers_of.empty() ? decs : specs;
                m.pure = C().clang_CXXMethod_isPureVirtual(c) != 0;
                x_.out->marks.push_back(std::move(m));
            }
            e.module = x_.module;
            std::string ev = rule.evidence;
            if (ev.empty())
                for (size_t k = 0; k < decs.size(); k++) ev += (k ? ", " : "") + decs[k];
            e.evidence = ev;
            e.target_expr = qualname;
            x_.ff.entrypoints.push_back(e);
            break;
        }
    }

    // ------------------------------------------------------------------ calls --- //

    // A call as written, before its ordinal: everything a site needs, found either by the
    // token scan or, for a construction written as a declaration, by the AST.
    struct Pending {
        unsigned off;           // where it is written: the key its resolution is found by
        unsigned line;
        std::string expr;
        size_t open = 0, close = 0;
        bool construction = false;
        CXCursor call, ref;     // what clang made of it; null when clang made nothing
        bool resolved = false;
        bool macro_written = false;  // from clang, in a body a macro wrote: not a call written here
    };

    // What clang made of every call it kept, by the offset the call is written at. The
    // outermost wins, which is the one a chain folds to (`a.b(c).d(e)` is `.d`'s).
    std::map<unsigned, std::pair<CXCursor, CXCursor>> resolved_;
    std::set<unsigned> constructions_;  // offsets where what is written constructs a type
    std::set<unsigned> var_names_;      // offsets of declared names: `int x(5)` is not a call
    std::map<unsigned, std::vector<std::pair<CXCursor, CXCursor>>> macro_calls_;  // by the macro's offset
    std::map<unsigned, Routine*> macro_owners_;   // the routine each such macro is written in
    std::map<unsigned, CXCursor> macro_cursors_;  // each expansion in this file, by its offset
    std::set<std::tuple<std::string, long, std::string>> written_hits_;  // routine, line, kind
    int macro_depth_ = 0;                      // control nested in a macro-written body
    std::set<std::string> defs_recorded_;  // definitions this file has already reported
    std::map<unsigned, std::vector<std::pair<CXCursor, bool>>> macro_bodies_;  // `writes_no_call`, by hash

    // **Which call a macro written as a call is.** One that calls a function of its own name
    // is that call: git's `error(...)` is `(error(...), const_error())`. Otherwise one with a
    // single callee is that callee: `skip_prefix(...)` is `skip_prefix_impl(...)`. A macro
    // that expands to several is none of them, and says it is a macro (rule 1): taking the
    // first made every Unreal `UE_LOG` the construction of a static variable it declares.
    bool macro_call(unsigned off, const std::string& name, CXCursor& call, CXCursor& ref) {
        auto it = macro_calls_.find(off);
        if (it == macro_calls_.end()) return false;
        for (const auto& [c, r] : it->second)
            if (!C().clang_Cursor_isNull(r) && spelling(r) == name) {
                call = c;
                ref = r;
                return true;
            }
        std::set<std::string> callees;
        for (const auto& [c, r] : it->second) callees.insert(C().clang_Cursor_isNull(r) ? "" : usr(r));
        if (callees.size() != 1) return false;
        call = it->second.front().first;
        ref = it->second.front().second;
        return true;
    }
    std::map<const Routine*, std::vector<Pending>> pending_;

    // ---------------------------------------------------------- macros as facts --- //

    // The definition an expansion here uses: its id, recorded the first time it is met. Blank
    // only where clang kept no expansion at that offset, which a span never is.
    std::string def_of(unsigned off) {
        auto at = macro_cursors_.find(off);
        if (at == macro_cursors_.end()) return "";
        CXCursor def = C().clang_getCursorReferenced(at->second);
        std::string name = spelling(at->second);
        std::string file, origin = "builtin";
        unsigned line = 0;
        if (!C().clang_Cursor_isNull(def)) {
            CXSourceLocation loc = C().clang_getCursorLocation(def);
            CXFile f = nullptr;
            unsigned col = 0, o = 0;
            C().clang_getFileLocation(loc, &f, &line, &col, &o);
            if (f) {
                // By path and never by `clang_Location_isInSystemHeader`: an Unreal module's
                // own headers read as system headers, because they arrive by `-idirafter`.
                std::string g = std::filesystem::path(clang::str(C().clang_getFileName(f))).lexically_normal().generic_string();
                if (!x_.root.empty() && g.rfind(x_.root, 0) == 0) {
                    file = g.substr(x_.root.size());
                    origin = "tree";
                } else {
                    size_t last = g.find_last_of('/');
                    size_t before = last == std::string::npos || last == 0 ? std::string::npos : g.find_last_of('/', last - 1);
                    file = before == std::string::npos ? g : g.substr(before + 1);
                    origin = "outside";
                }
            } else {
                CXString presumed;
                C().clang_getPresumedLocation(loc, &presumed, nullptr, nullptr);
                std::string where = clang::str(presumed);
                if (where.find("command line") != std::string::npos) origin = "command_line";
            }
        }
        std::string id = ids::definition_id(file.empty() ? origin : file, name, static_cast<int>(line));
        if (defs_recorded_.insert(id).second) {
            facts::MacroDef d;
            d.id = id;
            d.name = name;
            d.file = file;
            d.line = line;
            d.origin = origin == "tree"           ? facts::MacroOrigin::TREE
                       : origin == "outside"      ? facts::MacroOrigin::OUTSIDE
                       : origin == "command_line" ? facts::MacroOrigin::COMMAND_LINE
                                                  : facts::MacroOrigin::BUILTIN;
            x_.ff.macro_defs.push_back(std::move(d));
        }
        return id;
    }

    // The macro that wrote what is at this location, if a macro's span holds it.
    std::string written_by(CXSourceLocation loc) {
        unsigned at;
        if (!offset_of(loc, at)) return "";
        const auto* m = x_.macro_at(at);
        return m ? def_of(m->first) : "";
    }

    // Every use of a macro, once the walk has said what is where. Swept in order: both the
    // uses and the routines are sorted by offset, and a file can hold thousands of each.
    void macro_sites() {
        std::vector<const Routine*> by_start;
        for (const auto& r : routines_) by_start.push_back(r.get());
        std::sort(by_start.begin(), by_start.end(), [](const Routine* a, const Routine* b) {
            return a->body_lo != b->body_lo ? a->body_lo < b->body_lo : a->body_hi > b->body_hi;
        });
        std::sort(declaration_spans_.begin(), declaration_spans_.end());
        std::vector<const Routine*> open;
        size_t next = 0;
        for (const auto& [off, name] : x_.macro_names) {
            if (x_.in_pp(off)) {
                x_.ff.macro_directive_uses = x_.ff.macro_directive_uses + 1;
                continue;
            }
            // Strictly after the opening: `WHOLE(a)` holds `a`'s body at its own offset, and
            // is not a use inside `a`.
            while (next < by_start.size() && by_start[next]->body_lo < off) open.push_back(by_start[next++]);
            while (!open.empty() && open.back()->body_hi <= off) open.pop_back();
            facts::MacroSite s;
            s.def_id = def_of(off);
            s.name = name;
            s.line = x_.line_of(off);
            s.shadows = shadowed_kind(off, name);
            if (!open.empty()) {
                s.position = facts::MacroPosition::STATEMENT;
                s.routine_id = open.back()->r.id;
            } else if (macros_that_declare_.count(off) || macros_that_annotate_.count(off) || in_declaration(off)) {
                s.position = facts::MacroPosition::DECLARATION;
            } else {
                s.position = facts::MacroPosition::FILE_SCOPE;
            }
            x_.ff.macro_sites.push_back(std::move(s));
        }
    }

    // **A macro named like a boundary that goes somewhere else**: `#define unlink(x) helper(x)`
    // touches no file, so the rule's word for it is false. Only where the expansion is
    // plainly the tree's own, under another name: `open` becoming `open64`, or `stat` becoming
    // `__xstat`, is a platform's spelling of the same act, and a library's function could be
    // anything, so neither is called a shadow (rule 1).
    std::string shadowed_kind(unsigned off, const std::string& name) {
        auto mc = macro_calls_.find(off);
        if (mc == macro_calls_.end()) return "";
        std::string kind;
        for (const auto& rule : x_.rules->boundaries)
            if (rule.matches(name)) {
                if (rule.names_macro) return "";
                kind = rule.kind;
                break;
            }
        if (kind.empty()) return "";
        bool any = false;
        for (const auto& [c, r] : mc->second) {
            if (C().clang_Cursor_isNull(r) || !is_function_kind(C().clang_getCursorKind(r))) continue;
            std::string callee = spelling(r);
            if (callee.rfind("__builtin", 0) == 0 || callee.rfind("operator", 0) == 0) continue;
            if (C().clang_getCursorKind(r) == CXCursor_Constructor) continue;
            if (outside_tree(r) || callee.find(name) != std::string::npos) return "";
            any = true;
        }
        return any ? kind : "";
    }

    // **Where each macro use's expansion goes**, for the edge pass to finish. A row per callee
    // per line: a thousand identical `check`s on a thousand lines stay a thousand places, and
    // the same callee twice on one line is a count.
    void macro_reaches() {
        std::map<std::tuple<long, std::string, std::string, std::string>, Reach> rows;
        for (const auto& [off, calls] : macro_calls_) {
            auto who = macro_owners_.find(off);
            if (who == macro_owners_.end() || x_.in_pp(off)) continue;
            std::string def = def_of(off);
            const std::string& owner = *who->second->r.id;
            long line = x_.line_of(off);
            for (const auto& [c, r] : calls) {
                bool named = !C().clang_Cursor_isNull(r) && is_function_kind(C().clang_getCursorKind(r));
                if (named && C().clang_getCursorKind(r) == CXCursor_Constructor) continue;
                std::string name = named ? spelling(r) : "";
                if (name.rfind("__builtin", 0) == 0 || name.rfind("operator", 0) == 0) continue;
                std::string callee;
                if (named) {
                    bool nested;
                    std::string rec;
                    callee = join(scope_parts(r, nested, rec), routine_name(r));
                }
                auto key = std::make_tuple(line, def, owner, callee);
                auto at = rows.find(key);
                if (at != rows.end()) {
                    at->second.count++;
                    continue;
                }
                Reach m;
                m.file = x_.rel;
                m.line = line;
                m.def_id = def;
                m.routine_id = owner;
                m.callee = callee;
                if (named) {
                    m.usr = usr(r);
                    CXCursor d = C().clang_getCursorDefinition(r);
                    if (!C().clang_Cursor_isNull(d)) {
                        CXFile f = nullptr;
                        C().clang_getExpansionLocation(C().clang_getCursorLocation(d), &f, nullptr, nullptr, nullptr);
                        if (f) {
                            std::string g = std::filesystem::path(clang::str(C().clang_getFileName(f))).lexically_normal().generic_string();
                            if (!x_.root.empty() && g.rfind(x_.root, 0) == 0) m.seen = g.substr(x_.root.size());
                        }
                    }
                    for (const auto& rule : x_.rules->boundaries) {
                        if (!rule.matches(callee)) continue;
                        // Written and expanded on one line are one act: `UE_LOG` is STDIO by
                        // its own name, whatever it calls to do it.
                        if (written_hits_.count({owner, line, rule.kind})) continue;
                        facts::BoundaryHit h;
                        h.routine_id = owner;
                        h.kind = rule.kind;
                        h.direction = rule.direction;
                        h.target = rule.target_arg && *rule.target_arg >= 0 ? expanded_arg(c, *rule.target_arg, off) : "";
                        h.line = line;
                        h.evidence = callee;
                        h.salience = rule.salience;
                        m.hits.push_back(h);
                    }
                }
                rows.emplace(key, std::move(m));
            }
        }
        for (auto& [k, m] : rows) x_.out->reaches.push_back(std::move(m));
    }

    // An argument of a call a macro made, where somebody wrote it in the macro's arguments:
    // `WRAP(fd)` names `fd`. Blank where it is in the macro's body, which is nothing anybody at
    // this line wrote, and the map says "unnamed" for it.
    std::string expanded_arg(CXCursor call, int idx, unsigned off) {
        const auto* span = x_.macro_at(off);
        if (!span || idx >= C().clang_Cursor_getNumArguments(call)) return "";
        unsigned a, b;
        extent(C().clang_Cursor_getArgument(call, static_cast<unsigned>(idx)), a, b);
        if (a <= span->first || b > span->second || b <= a) return "";
        size_t i = x_.tok_at(a);
        if (i >= x_.toks.size() || x_.toks[i].off != a) return "";
        size_t j = i;
        while (j + 1 < x_.toks.size() && x_.toks[j + 1].off < b) j++;
        return x_.slice(i, j);
    }

    bool in_declaration(unsigned off) const {
        auto it = std::upper_bound(declaration_spans_.begin(), declaration_spans_.end(), std::make_pair(off, ~0u));
        // `struct X { } v;` is two declarations that overlap, and nothing nests deeper.
        for (int walked = 0; it != declaration_spans_.begin() && walked < 4; walked++) {
            --it;
            if (it->second > off) return true;
        }
        return false;
    }

    // **A loop in a body a macro wrote**, from clang, since nothing is written to scan: a loop
    // that issues a call per item is a rate whoever typed it. Its header is the macro's use,
    // which is the only text at that line. Only here: in a body somebody wrote, `check(x)`
    // expands to an `if`, and that is not control anybody wrote.
    void macro_control(Routine* owner, const std::string& word) {
        const auto* span = x_.macro_at(owner->body_lo);
        if (!span) return;
        size_t i = x_.tok_at(span->first), j = i;
        while (j + 1 < x_.toks.size() && x_.toks[j + 1].off < span->second) j++;
        std::string header = x_.slice(i, j);
        if (header.size() > 200) header.resize(200);
        unsigned line = x_.line_of(span->first);
        facts::ControlPoint p;
        p.point_id = ids::make_id({*owner->r.id, std::to_string(line), word, std::to_string(x_.ff.control.size())});
        p.routine_id = owner->r.id;
        p.kind = word == "if" || word == "switch" ? facts::ControlKind::DECISION
                 : word == "try"                  ? facts::ControlKind::HANDLER
                                                  : facts::ControlKind::LOOP;
        p.line_start = line;
        p.line_end = line;
        p.depth = macro_depth_ + 1;
        p.header = header;
        p.arms = 1;
        p.word = word;
        x_.ff.control.push_back(p);
    }

    // Would the token scan name a call starting at this offset?
    bool written_call_at(unsigned off) const {
        size_t i = x_.tok_at(off);
        if (i >= x_.toks.size() || x_.toks[i].off != off) return false;
        size_t j;
        std::string expr = fold_declarator(x_.toks, i, j);
        return !expr.empty() && j < x_.toks.size() && x_.toks[j].text == "(";
    }

    // **Does this macro's definition have nothing in it that could call anything?** Every word
    // in its body is a parameter or a keyword: `#define rename(a, b) 0`, `#define N_(s) (s)`,
    // `#define RETRY(e) do { e; } while (0)`. Asked of the definition because clang's silence
    // cannot answer it: a statement clang could not type, which at Unreal's scale is common,
    // leaves no call under a macro that plainly has one. A word that is anything else may be
    // a function or another macro, so it is a no.
    bool writes_no_call(unsigned off) {
        auto at = macro_cursors_.find(off);
        if (at == macro_cursors_.end()) return false;
        CXCursor def = C().clang_getCursorReferenced(at->second);
        if (C().clang_Cursor_isNull(def)) return false;
        auto& met = macro_bodies_[C().clang_hashCursor(def)];
        for (const auto& [o, answer] : met)
            if (C().clang_equalCursors(o, def)) return answer;
        CXToken* toks = nullptr;
        unsigned n = 0;
        C().clang_tokenize(x_.tu, C().clang_getCursorExtent(def), &toks, &n);
        bool none = n > 0;
        std::set<std::string> params;
        unsigned i = 1;  // the macro's own name is first
        if (C().clang_Cursor_isMacroFunctionLike(def))
            for (i = 2; i < n; i++) {
                std::string t = clang::str(C().clang_getTokenSpelling(x_.tu, toks[i]));
                if (t == ")") {
                    i++;
                    break;
                }
                if (C().clang_getTokenKind(toks[i]) == CXToken_Identifier) params.insert(t);
            }
        for (; none && i < n; i++) {
            if (C().clang_getTokenKind(toks[i]) != CXToken_Identifier) continue;
            std::string t = clang::str(C().clang_getTokenSpelling(x_.tu, toks[i]));
            if (t != "__VA_ARGS__" && !params.count(t)) none = false;
        }
        if (toks) C().clang_disposeTokens(x_.tu, toks, n);
        met.push_back({def, none});
        return none;
    }

    // In a routine's body, during the walk: note what clang made of each call.
    void note_call(CXCursor c, CXCursor parent) {
        unsigned a, b;
        extent(c, a, b);
        CXCursor ref = C().clang_getCursorReferenced(c);
        // In a body a macro wrote whole, or a file-scope initialiser, nothing is scanned, so what
        // clang resolved is all there is, and each call is named by what it reaches. Constructors
        // are left out: from here an implicit one cannot be told from a written one. A call clang
        // could not name has nothing to be recorded under, so it is counted. Where somebody wrote
        // part of the body, a call they wrote is read as any other.
        Routine* owner = stack_.empty() ? &scope_ : stack_.back();
        if (owner->macro_written && !(owner->half_written && (!x_.in_macro(a) || written_call_at(a)))) {
            if (unevaluated_) return;
            if (C().clang_Cursor_isNull(ref) || !is_function_kind(C().clang_getCursorKind(ref))) {
                x_.out->unnamed_calls++;
                return;
            }
            // Nor an operator, which is not a call anywhere in this reader.
            if (C().clang_getCursorKind(ref) == CXCursor_Constructor || spelling(ref).rfind("operator", 0) == 0) return;
            bool nested;
            std::string rec;
            Pending p;
            p.off = a;
            p.line = x_.line_of(a);
            p.expr = join(scope_parts(ref, nested, rec), routine_name(ref));
            p.call = c;
            p.ref = ref;
            p.resolved = true;
            p.macro_written = true;
            pending_[owner].push_back(p);
            return;
        }
        // Every call a macro written here expands to, by the macro's offset: which of them
        // the written call is, is decided at `emit_calls`, and not by which came first.
        if (unevaluated_) {
            // Nothing happens here, so nothing is the macro's or the file scope's.
        } else if (x_.macro_names.count(a)) {
            macro_calls_[a].push_back({c, ref});
            macro_owners_[a] = owner;
        } else if (const auto* m = x_.macro_at(a)) {
            // Inside the macro's arguments, which is not the same thing as written in them.
            // `RETRY(connect(fd))` writes the call and the scan will name it. `CALL(connect, fd)`
            // writes a name, and the call is the macro's, starting at that name. An operator or
            // a constructor at such a place is what its arguments are made of, and says nothing
            // about the macro.
            bool quiet = !C().clang_Cursor_isNull(ref) &&
                         (C().clang_getCursorKind(ref) == CXCursor_Constructor ||
                          spelling(ref).rfind("operator", 0) == 0);
            if (!quiet && !written_call_at(a)) {
                macro_calls_[m->first].push_back({c, ref});
                macro_owners_[m->first] = owner;
            }
        }
        bool ctor = !C().clang_Cursor_isNull(ref) && C().clang_getCursorKind(ref) == CXCursor_Constructor;
        if (ctor && C().clang_getCursorKind(parent) == CXCursor_CXXNewExpr) return;  // the `new` names it
        if (ctor) {
            size_t i = x_.tok_at(a);
            if (i >= x_.toks.size() || x_.toks[i].off != a) return;  // nothing written: implicit
            CXCursor var = vars_.empty() ? parent : vars_.back();
            if (!vars_.empty() && namey(x_.toks[i]) && spelling(var) == x_.toks[i].text && i + 1 < x_.toks.size() &&
                (x_.toks[i + 1].text == "(" || x_.toks[i + 1].text == "{")) {
                // `std::ifstream f(path);` — the type is the declaration's, as written. The
                // tokens cannot say this; the declaration can.
                long close = matching(x_.toks, i + 1);
                std::string expr = fold_type(clang::str(C().clang_getTypeSpelling(C().clang_getCursorType(var))));
                if (close < 0 || expr.empty()) return;
                Pending p;
                p.off = a;
                p.line = x_.line_of(a);
                p.expr = expr;
                p.open = i + 1;
                p.close = static_cast<size_t>(close);
                p.construction = true;
                p.call = c;
                p.ref = ref;
                p.resolved = true;
                pending_[stack_.back()].push_back(p);
                return;
            }
            // `Foo(a)`, `Foo{a}`: the token scan names it. Never a macro's name: Unreal's
            // `UE_LOG` declares a static variable, and every `UE_LOG` was a construction.
            if (!x_.macro_names.count(a)) constructions_.insert(a);
        }
        resolved_.emplace(a, std::make_pair(c, ref));
    }

    void note_new(CXCursor c) {
        unsigned a, b;
        extent(c, a, b);
        struct F {
            CXCursor found;
            bool ok = false;
        } f;
        C().clang_visitChildren(
            c,
            [](CXCursor k, CXCursor, CXClientData d) {
                CXCursor r = C().clang_getCursorReferenced(k);
                if (!C().clang_Cursor_isNull(r) && C().clang_getCursorKind(r) == CXCursor_Constructor) {
                    static_cast<F*>(d)->found = k;
                    static_cast<F*>(d)->ok = true;
                    return CXChildVisit_Break;
                }
                return CXChildVisit_Continue;
            },
            &f);
        if (f.ok) resolved_.emplace(a, std::make_pair(f.found, C().clang_getCursorReferenced(f.found)));
    }

    std::vector<facts::CallArg> args_between(size_t open, size_t close) {
        std::vector<facts::CallArg> out;
        int depth = 0;
        size_t start = open + 1;
        int idx = 0;
        auto flush = [&](size_t end) {  // tokens start..end-1
            if (end > start) {
                size_t last = end - 1;
                bool splat = x_.toks[last].text == "...";
                if (splat && last > start) last--;
                if (!(splat && last == start && x_.toks[last].text == "...")) {
                    facts::CallArg a;
                    a.idx = idx;
                    a.expr = x_.slice(start, last);
                    a.splat = splat;
                    out.push_back(a);
                }
            }
            idx++;
        };
        for (size_t i = open + 1; i < close; i++) {
            const Tok& t = x_.toks[i];
            if (t.kind != PUNCT) continue;
            if (t.text == "(" || t.text == "[" || t.text == "{") depth++;
            else if (t.text == ")" || t.text == "]" || t.text == "}") depth--;
            else if (t.text == "," && depth == 0) {
                flush(i);
                start = i + 1;
            }
        }
        if (close > open + 1) flush(close);
        return out;
    }

    // The last `(`…`)` pair opening at depth zero between `i` and `end`.
    bool last_top_call(size_t i, size_t end, size_t& open, size_t& close) {
        int depth = 0;
        long opened = -1;
        bool found = false;
        for (size_t k = i; k < end && k < x_.toks.size(); k++) {
            const Tok& t = x_.toks[k];
            if (t.kind != PUNCT) continue;
            if (t.text == "(") {
                if (depth == 0) opened = static_cast<long>(k);
                depth++;
            } else if (t.text == ")") {
                if (--depth == 0 && opened >= 0) {
                    open = static_cast<size_t>(opened);
                    close = k;
                    found = true;
                }
            }
        }
        return found;
    }

    // Words followed by `(` that are not calls.
    static const std::set<std::string>& not_calls() {
        static const std::set<std::string> s = {
            "if", "for", "while", "switch", "catch", "do", "else", "return", "sizeof", "alignof",
            "alignas", "decltype", "typeid", "noexcept", "static_assert", "throw", "new", "delete",
            "and", "or", "not", "requires", "static_cast", "dynamic_cast", "const_cast",
            "reinterpret_cast", "case", "default", "goto", "try", "co_await", "co_return", "co_yield",
            "operator", "template", "typename", "using", "_Static_assert", "__attribute__", "__declspec"};
        return s;
    }

    // `_one`: the call written at token `i`, or nothing. `at` is where it is keyed (the
    // `new` of a construction, otherwise the name).
    bool one_call(size_t i, size_t hi, size_t at, bool construction, Pending& p, size_t& next) {
        const auto& t = x_.toks;
        if (i >= hi) return false;
        if (!(t[i].kind == IDENT || t[i].text == "this")) return false;
        size_t j;
        std::string expr = fold_declarator(t, i, j);
        if (expr.empty() || j >= hi || t[j].text != "(") return false;
        long close = matching(t, j, hi);
        if (close < 0) return false;
        size_t open = j, cl = static_cast<size_t>(close);
        size_t end;
        std::string full = fold(t, i, end);
        if (!full.empty() && end > cl + 1) {
            size_t o2, c2;
            if (last_top_call(i, std::min(end, hi), o2, c2)) {
                expr = full;
                open = o2;
                cl = c2;
            }
        }
        p.off = t[at].off;
        p.line = t[i].line;
        p.expr = expr;
        p.open = open;
        p.close = cl;
        p.construction = construction || constructions_.count(t[i].off) > 0;
        auto r = resolved_.find(p.off);
        if (r != resolved_.end()) {
            p.call = r->second.first;
            p.ref = r->second.second;
            p.resolved = true;
        }
        // On from the first argument list, not past the last: a call written inside another
        // call's arguments is a call (`printf("%d", count(path))`). The syntactic reader
        // stepped over them, and every one was missing from its maps. The rest of the chain
        // cannot be recorded twice, because a name after `.` is never a chain's root.
        next = j + 1;
        return true;
    }

    // Is token `i` a name partway along a chain? Then the chain's root decides, and a root
    // that could not be named (`handlers[0].run()`) names nothing at all (clause 3) — the
    // scan must not start again at `run`. A leading `::` is the global scope, not a chain.
    bool mid_chain(size_t i) const {
        if (i == 0) return false;
        const Tok& prev = x_.toks[i - 1];
        if (!joiner(prev)) return false;
        if (prev.text != "::" || i < 2) return true;
        const Tok& before = x_.toks[i - 2];
        return namey(before) || before.text == ">" || before.text == ")" || before.text == "]";
    }

    // A named cast is not identity (clause 5): `static_cast<T*>(x)->run()` is `x.run`, as
    // `((Runnable) x).run()` is in Java. Only where what is cast is a name.
    bool cast_call(size_t i, size_t hi, Pending& p, size_t& next) {
        const auto& t = x_.toks;
        size_t j = skip_template(t, i + 1);
        if (j >= hi || j == i + 1 || t[j].text != "(") return false;
        long close = matching(t, j, hi);
        if (close < 0) return false;
        size_t inner_end;
        std::string inner = fold(t, j + 1, inner_end);
        if (inner.empty() || inner_end != static_cast<size_t>(close)) return false;
        size_t k = static_cast<size_t>(close) + 1;
        if (k >= hi || !joiner(t[k])) return false;
        Pending rest;
        size_t after;
        if (!one_call(k + 1, hi, k + 1, false, rest, after)) return false;
        p = rest;
        p.off = t[i].off;
        p.line = t[i].line;
        p.expr = inner + "." + rest.expr;
        auto r = resolved_.find(t[i].off);
        p.resolved = false;
        // What clang made of it is keyed where the whole call starts, at the cast.
        if (r != resolved_.end()) {
            p.call = r->second.first;
            p.ref = r->second.second;
            p.resolved = true;
        }
        next = after;
        return true;
    }

    // The ranges inside `r`'s body that belong to a routine nested in it, from where its
    // declaration starts: the header of a local class's constructor is not a call to it.
    std::vector<std::pair<unsigned, unsigned>> inner(const Routine* r) {
        std::vector<std::pair<unsigned, unsigned>> out;
        for (const auto& o : routines_)
            if (o.get() != r && o->body_lo > r->body_lo && o->body_hi <= r->body_hi)
                out.push_back({o->decl_lo > r->body_lo ? o->decl_lo : o->body_lo, o->body_hi});
        // Directives and inactive arms are stepped over as a nested routine is. A span's
        // second offset is its *last token's*, which is what the scans' jump expects.
        for (const auto& [a, b] : x_.pp_spans)
            if (b > r->body_lo && a < r->body_hi && a < b) out.push_back({a, b});
        std::sort(out.begin(), out.end());
        return out;
    }

    // Every call written in one routine's body, as the syntactic reader found them: by the
    // tokens, so a statement clang could not make sense of still has its calls.
    void scan_calls(Routine* owner) {
        if (owner->macro_written && !owner->half_written) return;  // nothing is written: `note_call` has them
        auto skip = inner(owner);
        size_t lo = x_.tok_at(owner->body_lo) + 1, hi = x_.tok_at(owner->body_hi);
        std::vector<Pending>& out = pending_[owner];
        std::set<unsigned> have;
        for (const auto& p : out) have.insert(p.off);
        size_t i = lo;
        while (i < hi) {
            const Tok& t = x_.toks[i];
            bool jumped = false;
            for (const auto& [a, b] : skip)
                if (t.off >= a && t.off < b) {
                    i = x_.tok_at(b) + 1;
                    jumped = true;
                    break;
                }
            if (jumped) continue;
            if (!namey(t)) {
                i++;
                continue;
            }
            if (t.text == "new") {
                Pending p;
                size_t next;
                if (one_call(i + 1, hi, i, true, p, next) && have.insert(p.off).second) {
                    out.push_back(p);
                    i = next;
                    continue;
                }
                i++;
                continue;
            }
            if (t.text == "static_cast" || t.text == "dynamic_cast" || t.text == "const_cast" ||
                t.text == "reinterpret_cast") {
                Pending p;
                size_t next;
                if (cast_call(i, hi, p, next) && have.insert(p.off).second) {
                    out.push_back(p);
                    i = next;
                    continue;
                }
                i++;
                continue;
            }
            if (not_calls().count(t.text) || var_names_.count(t.off) || have.count(t.off) || mid_chain(i)) {
                i++;
                continue;
            }
            Pending p;
            size_t next;
            if (one_call(i, hi, i, false, p, next)) {
                have.insert(p.off);
                out.push_back(p);
                i = next;
                continue;
            }
            i++;
        }
        streams(owner, lo, hi, skip);
    }

    // Each routine's calls in source order, with their ordinals, their facts and their edges.
    void emit_calls(Routine* owner) {
        auto& ps = pending_[owner];
        std::stable_sort(ps.begin(), ps.end(), [](const Pending& a, const Pending& b) { return a.off < b.off; });
        for (const auto& p : ps) {
            facts::CallSite s;
            s.caller_id = owner->r.id;
            s.callee_expr = p.expr;
            s.line = p.line;
            int& n = site_ordinals_[{*owner->r.id, p.expr}];
            s.site_id = ids::call_site_id(*owner->r.id, p.expr, n);
            n++;
            if (p.close > p.open) s.args = args_between(p.open, p.close);
            s.is_construction = p.construction;
            x_.ff.calls.push_back(s);
            // A macro that can call nothing is not the function it is named after, and a rule
            // that names the function has not met it: `#define rename(a, b) 0` touches no file.
            auto named = x_.macro_names.find(p.off);
            bool no_call = named != x_.macro_names.end() && named->second == p.expr && !p.construction &&
                           !p.macro_written && !macro_calls_.count(p.off) && writes_no_call(p.off);
            bool shadowed = named != x_.macro_names.end() && named->second == p.expr && !p.construction &&
                            !p.macro_written && !shadowed_kind(p.off, p.expr).empty();
            // A call in a body a macro wrote is one nobody wrote here.
            std::string through;
            if (p.macro_written) {
                if (const auto* m = x_.macro_at(p.off)) through = def_of(m->first);
            }
            bool touched = !no_call && !shadowed && boundaries(owner, s, *s.callee_expr, through);

            Site e;
            e.site_id = s.site_id;
            e.caller_id = *owner->r.id;
            e.expr = p.expr;
            e.construction = p.construction;
            // A call written as a macro is the call `macro_call` says it is, where it says one:
            // git's `skip_prefix(...)` reaches `skip_prefix_impl`, which is what runs. Where
            // it expands to no call at all, or to several, (`N_("...")`, `OPT_BOOL(...)`, a struct literal)
            // it is a macro and says so, not a call clang failed to resolve (rule 32).
            // The two are different counts, and only one is a gap in what clang could read.
            auto mac = x_.macro_names.find(p.off);
            if (mac != x_.macro_names.end() && !p.construction && !p.macro_written) {
                CXCursor call, ref;
                if (macro_call(p.off, mac->second, call, ref)) {
                    resolve(e, call, ref);
                } else {
                    e.macro = mac->second;
                    e.macro_no_call = no_call;
                    auto mc = macro_calls_.find(p.off);
                    if (mc != macro_calls_.end())
                        for (const auto& [c, r] : mc->second)
                            if (!C().clang_Cursor_isNull(r)) e.macro_usrs.push_back(usr(r));
                    std::sort(e.macro_usrs.begin(), e.macro_usrs.end());
                    e.macro_usrs.erase(std::unique(e.macro_usrs.begin(), e.macro_usrs.end()), e.macro_usrs.end());
                }
            } else if (p.resolved) {
                resolve(e, p.call, p.ref);
                // **What it reaches is a name too, where the written one says nothing.**
                // `Hasher.Update(...)` is `FSHA1.Update`, and no rule can read a variable's name.
                // Only for what leaves this tree: an internal call that became a boundary would
                // lose its edge (rule 2), and inside Core `FSHA1.Update` is Core's own. The written
                // name still comes first, since clang's loses what a rule needs:
                // `IFileManager::Get().Delete(...)` is only `IFileManager.Delete` to it.
                if (!touched && !p.macro_written && !e.is_ctor && !e.qualified.empty() && outside_tree(p.ref))
                    boundaries(owner, s, e.qualified, "");
            } else {
                e.untyped = true;  // written, and clang kept nothing to say what it reaches
            }
            x_.out->sites.push_back(std::move(e));
        }
    }

    // What clang says this call reaches, kept for the edge pass.
    void resolve(Site& e, CXCursor call, CXCursor ref) {
        if (C().clang_Cursor_isNull(ref)) {
            // A call clang named nothing for: through a function value, or under an argument
            // it could not type.
            e.bound = callee_is_value(call);
            e.untyped = !e.bound;
            return;
        }
        CXCursorKind rk = C().clang_getCursorKind(ref);
        if (!is_function_kind(rk)) {
            // A variable, a field or a parameter holding something callable.
            e.bound = true;
            return;
        }
        e.usr = usr(ref);
        bool nested;
        std::string rec;
        e.qualified = join(scope_parts(ref, nested, rec), routine_name(ref));
        e.is_ctor = rk == CXCursor_Constructor;
        e.is_method = rk == CXCursor_CXXMethod || rk == CXCursor_Destructor || rk == CXCursor_ConversionFunction;
        if (e.is_method) {
            e.is_virtual = C().clang_CXXMethod_isVirtual(ref) != 0;
            e.is_dynamic = C().clang_Cursor_isDynamicCall(call) != 0;
            e.final_ = has_final(ref) || has_final(C().clang_getCursorSemanticParent(ref));
            // The receiver's static type: only an override in a subtype of it can answer.
            CXType rt = C().clang_Cursor_getReceiverType(call);
            if (rt.kind == CXType_Pointer || rt.kind == CXType_LValueReference || rt.kind == CXType_RValueReference)
                rt = C().clang_getPointeeType(rt);
            CXCursor rd = C().clang_getTypeDeclaration(rt);
            if (!C().clang_Cursor_isNull(rd)) e.receiver_usr = usr(rd);
            if (e.receiver_usr.empty()) e.receiver_usr = usr(C().clang_getCursorSemanticParent(ref));
        }
        if (e.is_ctor) e.construct_usr = usr(C().clang_getCursorSemanticParent(ref));
        // The definition this translation unit can see, where it sees one: the one that is
        // linked when several share a USR (`edges.hpp`).
        CXCursor def = C().clang_getCursorDefinition(ref);
        if (!C().clang_Cursor_isNull(def)) {
            CXFile f = nullptr;
            C().clang_getExpansionLocation(C().clang_getCursorLocation(def), &f, nullptr, nullptr, nullptr);
            if (f) {
                std::string g =
                    std::filesystem::path(clang::str(C().clang_getFileName(f))).lexically_normal().generic_string();
                if (!x_.root.empty() && g.rfind(x_.root, 0) == 0) e.seen = g.substr(x_.root.size());
            }
        }
    }

    static bool callee_is_value(CXCursor call) {
        bool value = false;
        C().clang_visitChildren(
            call,
            [](CXCursor k, CXCursor, CXClientData d) {
                CXCursor r = C().clang_getCursorReferenced(k);
                if (!C().clang_Cursor_isNull(r)) {
                    CXCursorKind rk = C().clang_getCursorKind(r);
                    if (rk == CXCursor_VarDecl || rk == CXCursor_ParmDecl || rk == CXCursor_FieldDecl)
                        *static_cast<bool*>(d) = true;
                }
                return CXChildVisit_Break;  // the callee is the first child
            },
            &value);
        return value;
    }

    // `std::cout << x` and its siblings: a boundary with no call shape, once per statement
    // line. Matched on shape, because nothing in the rule grammar can reach an operator.
    void streams(Routine* owner, size_t lo, size_t hi, const std::vector<std::pair<unsigned, unsigned>>& skip) {
        static const std::map<std::string, std::string> STREAMS = {
            {"std.cout", "OUT"}, {"std.cerr", "OUT"}, {"std.clog", "OUT"}, {"std.wcout", "OUT"},
            {"std.wcerr", "OUT"}, {"std.cin", "IN"}, {"std.wcin", "IN"}};
        long seen_line = -1;
        size_t i = lo;
        while (i < hi) {
            bool inside = false;
            for (const auto& [a, b] : skip)
                if (x_.toks[i].off >= a && x_.toks[i].off < b) inside = true;
            size_t j;
            std::string expr = inside ? "" : fold_declarator(x_.toks, i, j);
            auto it = STREAMS.find(expr);
            if (it != STREAMS.end() && j < hi && (x_.toks[j].text == "<<" || x_.toks[j].text == ">>")) {
                unsigned line = x_.toks[i].line;
                if (static_cast<long>(line) != seen_line) {
                    seen_line = line;
                    facts::BoundaryHit h;
                    h.routine_id = owner->r.id;
                    h.kind = facts::BoundaryKind::STDIO;
                    h.direction = it->second;
                    h.target = "";
                    h.line = line;
                    h.evidence = expr;
                    h.salience = "low";
                    x_.ff.boundaries.push_back(h);
                }
                i = j + 1;
                continue;
            }
            i = expr.empty() ? i + 1 : std::max(j, i + 1);
        }
    }

    bool outside_tree(CXCursor ref) const {
        CXFile f = nullptr;
        C().clang_getExpansionLocation(C().clang_getCursorLocation(ref), &f, nullptr, nullptr, nullptr);
        if (!f || x_.root.empty()) return false;
        std::string g = std::filesystem::path(clang::str(C().clang_getFileName(f))).lexically_normal().generic_string();
        return g.rfind(x_.root, 0) != 0;
    }

    bool boundaries(Routine* owner, const facts::CallSite& s, const std::string& name, const std::string& through) {
        bool any = false;
        for (const auto& rule : x_.rules->boundaries) {
            if (!rule.matches(name)) continue;
            any = true;
            facts::BoundaryHit h;
            h.routine_id = owner->r.id;
            h.kind = rule.kind;
            h.direction = rule.direction;
            std::string target;
            if (rule.target_arg && *rule.target_arg >= 0) {
                for (const auto& arg : s.args)
                    if (arg.idx == *rule.target_arg) target = *arg.expr;
            }
            h.target = target;
            h.line = s.line;
            h.evidence = name;
            h.salience = rule.salience;
            h.through_macro = through;
            written_hits_.insert({*owner->r.id, static_cast<long>(s.line), rule.kind});
            x_.ff.boundaries.push_back(h);
        }
        return any;
    }

    // ---------------------------------------------------------------- control --- //

    // `_statement_span`: where a statement starting at token `i` ends, and its body.
    void statement_span(size_t i, size_t& end, size_t& body_lo, size_t& body_hi) {
        const auto& t = x_.toks;
        size_t n = t.size(), j = i + 1;
        if (j < n && t[j].text == "(") {
            long close = matching(t, j);
            if (close < 0) {
                end = i;
                body_lo = body_hi = i + 1;
                return;
            }
            j = static_cast<size_t>(close) + 1;
        }
        if (j < n && t[j].text == "{") {
            long close = matching(t, j);
            if (close < 0) {
                end = n - 1;
                body_lo = j + 1;
                body_hi = n;
                return;
            }
            end = static_cast<size_t>(close);
            body_lo = j + 1;
            body_hi = end;
            return;
        }
        int depth = 0;
        for (size_t k = j; k < n; k++) {
            if (t[k].kind != PUNCT) continue;
            const std::string& x = t[k].text;
            if (x == "(" || x == "[" || x == "{") depth++;
            else if (x == ")" || x == "]" || x == "}") depth--;
            else if (x == ";" && depth == 0) {
                end = k;
                body_lo = j;
                body_hi = k;
                return;
            }
        }
        end = j;
        body_lo = body_hi = j;
    }

    std::string header_text(size_t i) {
        if (i + 1 < x_.toks.size() && x_.toks[i + 1].text == "(") {
            long close = matching(x_.toks, i + 1);
            if (close > 0) return x_.slice(i, static_cast<size_t>(close));
        }
        return x_.toks[i].text;
    }

    std::string exits(size_t lo, size_t hi) {
        std::vector<std::string> found;
        for (size_t k = lo; k < hi && k < x_.toks.size(); k++)
            if (EXITS.count(x_.toks[k].text) &&
                std::find(found.begin(), found.end(), x_.toks[k].text) == found.end())
                found.push_back(x_.toks[k].text);
        std::string out;
        for (size_t k = 0; k < found.size(); k++) out += (k ? "," : "") + found[k];
        return out;
    }

    struct Arm {
        std::string kind;
        size_t lo, hi;
        std::string header;
    };

    // Control as written, by the tokens: a statement clang dropped still has its loop, and a
    // macro that expands to an `if` (`check(x)`) is not control anybody wrote.
    void scan_control(Routine* owner) {
        // Control is read from what is written, so a macro-written body shows none. Its calls
        // are in the map and its loops and guards are not.
        if (owner->macro_written && !owner->half_written) return;
        auto skip = inner(owner);
        size_t lo = x_.tok_at(owner->body_lo) + 1, hi = x_.tok_at(owner->body_hi);
        control_range(owner, lo, hi, 1, skip);
    }

    void control_range(Routine* owner, size_t lo, size_t hi, int depth,
                       const std::vector<std::pair<unsigned, unsigned>>& skip) {
        size_t i = lo;
        while (i < hi && i < x_.toks.size()) {
            const Tok& t = x_.toks[i];
            bool jumped = false;
            for (const auto& [a, b] : skip)
                if (t.off >= a && t.off < b) {
                    i = x_.tok_at(b) + 1;
                    jumped = true;
                    break;
                }
            if (jumped) continue;
            if (t.kind != KEYWORD) {
                i++;
                continue;
            }
            const std::string& w = t.text;
            if (w != "for" && w != "while" && w != "do" && w != "if" && w != "switch" && w != "try") {
                i++;
                continue;
            }
            i = point(owner, i, hi, depth, skip) + 1;
        }
    }

    // One control point at token `i`; returns its last token.
    size_t point(Routine* owner, size_t i, size_t hi, int depth,
                 const std::vector<std::pair<unsigned, unsigned>>& skip) {
        const std::string word = x_.toks[i].text;
        size_t end, blo, bhi;
        statement_span(i, end, blo, bhi);
        std::string kind = facts::ControlKind::LOOP;
        std::vector<Arm> arms;
        if (word == "if") {
            kind = facts::ControlKind::DECISION;
            arms = if_arms(i);
        } else if (word == "switch") {
            kind = facts::ControlKind::DECISION;
            arms = switch_arms(i);
        } else if (word == "try") {
            kind = facts::ControlKind::HANDLER;
            arms = try_arms(i);
        }
        if (word == "if" && arms.size() <= 1 && guard(blo, bhi)) kind = facts::ControlKind::GUARD;
        size_t last = end;
        if (!arms.empty()) last = std::max(last, arms.back().hi);
        if (word == "do") {
            // `do { } while (c);` — the trailing `while` is this loop's, not a second one.
            size_t w = end + 1;
            if (w < hi && x_.toks[w].text == "while") {
                size_t e2, l2, h2;
                statement_span(w, e2, l2, h2);
                last = e2;
            }
        }
        last = std::min(last, hi > 0 ? hi - 1 : 0);

        facts::ControlPoint p;
        unsigned line = x_.toks[i].line;
        size_t ordinal = x_.ff.control.size();
        p.point_id = ids::make_id({*owner->r.id, std::to_string(line), word, std::to_string(ordinal)});
        p.routine_id = owner->r.id;
        p.kind = kind;
        p.line_start = line;
        p.line_end = x_.toks[last].line;
        p.depth = depth;
        p.header = header_text(i);
        p.arms = std::max<int64_t>(1, static_cast<int64_t>(arms.size()));
        p.exits = exits(blo, bhi);
        p.word = word;
        if (word == "for") once(i, p);
        x_.ff.control.push_back(p);
        for (size_t n = 0; n < arms.size(); n++) {
            facts::ControlArm arm;
            arm.point_id = p.point_id;
            arm.routine_id = owner->r.id;
            arm.idx = static_cast<int64_t>(n);
            arm.kind = arms[n].kind;
            arm.line_start = x_.toks[arms[n].lo].line;
            arm.line_end = x_.toks[std::min(arms[n].hi, x_.toks.size() - 1)].line;
            arm.header = arms[n].header;
            x_.ff.control_arms.push_back(arm);
        }
        // What is inside, one deeper: every arm's body, not only the first.
        if (arms.empty()) {
            if (blo < bhi) control_range(owner, blo, std::min(bhi, hi), depth + 1, skip);
        } else {
            for (const auto& a : arms) {
                size_t e, l, h;
                size_t at = a.lo;
                if (a.kind == facts::ArmKind::ELSE_IF) at = a.lo;  // the `if` of `else if`
                if (a.kind == facts::ArmKind::CASE || a.kind == facts::ArmKind::DEFAULT) {
                    size_t colon = at;
                    while (colon < a.hi && x_.toks[colon].text != ":") colon++;
                    control_range(owner, colon + 1, std::min(a.hi + 1, hi), depth + 1, skip);
                    continue;
                }
                statement_span(at, e, l, h);
                if (l < h) control_range(owner, l, std::min(h, hi), depth + 1, skip);
            }
        }
        return last;
    }

    bool guard(size_t lo, size_t hi) {
        if (lo >= hi) return false;
        int statements = 0;
        bool leaves = false;
        for (size_t k = lo; k < hi && k < x_.toks.size(); k++) {
            if (x_.toks[k].text == ";") statements++;
            if (EXITS.count(x_.toks[k].text)) leaves = true;
        }
        return statements <= 2 && leaves;
    }

    void once(size_t i, facts::ControlPoint& p) {
        if (i + 1 >= x_.toks.size() || x_.toks[i + 1].text != "(") return;
        long close = matching(x_.toks, i + 1);
        if (close < 0) return;
        int depth = 0;
        for (size_t k = i + 2; k < static_cast<size_t>(close); k++) {
            const std::string& t = x_.toks[k].text;
            if (t == "(" || t == "[" || t == "{") depth++;
            else if (t == ")" || t == "]" || t == "}") depth--;
            else if (t == ":" && depth == 0) {
                p.once_start = x_.toks[k + 1].line;
                p.once_end = x_.toks[static_cast<size_t>(close) - 1].line;
                return;
            }
        }
    }

    std::vector<Arm> if_arms(size_t i) {
        std::vector<Arm> out;
        size_t cur = i;
        std::string kind = facts::ArmKind::IF;
        while (cur < x_.toks.size()) {
            size_t end, blo, bhi;
            statement_span(cur, end, blo, bhi);
            out.push_back({kind, cur, end, header_text(cur)});
            size_t nxt = end + 1;
            while (nxt < x_.toks.size() && x_.toks[nxt].text == ";") nxt++;
            if (nxt < x_.toks.size() && x_.toks[nxt].text == "else") {
                size_t after = nxt + 1;
                if (after < x_.toks.size() && x_.toks[after].text == "if") {
                    kind = facts::ArmKind::ELSE_IF;
                    cur = after;
                    continue;
                }
                size_t e_end, e_lo, e_hi;
                statement_span(nxt, e_end, e_lo, e_hi);
                out.push_back({facts::ArmKind::ELSE, nxt, e_end, "else"});
            }
            break;
        }
        if (out.size() <= 1) out.clear();
        return out;
    }

    std::vector<Arm> switch_arms(size_t i) {
        size_t end, blo, bhi;
        statement_span(i, end, blo, bhi);
        std::vector<std::pair<std::string, size_t>> marks;
        int depth = 0;
        for (size_t j = blo; j < bhi; j++) {
            const Tok& t = x_.toks[j];
            if (t.kind == PUNCT) {
                if (t.text == "{") depth++;
                else if (t.text == "}") depth--;
                continue;
            }
            if (depth != 0) continue;
            if (t.text == "case") marks.push_back({facts::ArmKind::CASE, j});
            else if (t.text == "default") marks.push_back({facts::ArmKind::DEFAULT, j});
        }
        std::vector<Arm> out;
        for (size_t n = 0; n < marks.size(); n++) {
            size_t start = marks[n].second;
            size_t stop = n + 1 < marks.size() ? marks[n + 1].second - 1 : (bhi > 0 ? bhi - 1 : bhi);
            out.push_back({marks[n].first, start, std::max(start, stop), header_text(start)});
        }
        return out;
    }

    std::vector<Arm> try_arms(size_t i) {
        size_t end, blo, bhi;
        statement_span(i, end, blo, bhi);
        std::vector<Arm> out{{facts::ArmKind::TRY, i, end, "try"}};
        size_t cur = end + 1;
        while (cur < x_.toks.size() && x_.toks[cur].text == "catch") {
            size_t c_end, c_lo, c_hi;
            statement_span(cur, c_end, c_lo, c_hi);
            out.push_back({facts::ArmKind::CATCH, cur, c_end, header_text(cur)});
            cur = c_end + 1;
        }
        return out;
    }

    // --------------------------------------------------------------- literals --- //

    // Every string of three characters or more, attributed to the innermost routine whose
    // body holds it, and otherwise to the module scope, prepared and claimed only if used.
    // A directive's string (`#include "x.h"`) is a fact about the file, not a literal.
    void literals() {
        std::vector<const Routine*> by_width;
        for (const auto& r : routines_) by_width.push_back(r.get());
        std::sort(by_width.begin(), by_width.end(), [](const Routine* p, const Routine* q) {
            return (p->body_hi - p->body_lo) > (q->body_hi - q->body_lo);
        });
        for (size_t i = 0; i < x_.toks.size(); i++) {
            const Tok& t = x_.toks[i];
            if (t.kind != LITERAL || x_.in_pp(t.off)) continue;
            size_t q = t.text.find('"');
            if (q == std::string::npos) continue;  // a number or a character
            std::string body;
            if (q > 0 && t.text[q - 1] == 'R') {
                size_t open = t.text.find('(', q), close = t.text.rfind(')');
                body = (open != std::string::npos && close != std::string::npos && open < close)
                           ? t.text.substr(open + 1, close - open - 1) : t.text;
            } else {
                body = t.text.substr(q);
                if (body.size() >= 2 && body.back() == '"') body = body.substr(1, body.size() - 2);
                else if (!body.empty() && body.front() == '"') body = body.substr(1);
            }
            if (body.size() < 3) {
                x_.ff.literals_dropped++;
                continue;
            }
            const facts::Routine* owner = nullptr;
            for (const Routine* r : by_width)
                if (r->body_lo <= t.off && t.off <= r->body_hi) owner = &r->r;
            if (!owner) {
                owner = &module_scope_;
                module_scope_used_ = true;
            }
            facts::StringLiteral s;
            s.routine_id = owner->id;
            s.line = t.line;
            s.text = body;
            s.kind = facts::LiteralKind::PLAIN;
            x_.ff.literals.push_back(s);
        }
    }
};

// --------------------------------------------------------------------- entry --- //

inline std::string module_of(const std::string& rel) {
    size_t slash = rel.find_last_of('/');
    size_t dot = rel.rfind('.');
    std::string stem = (dot != std::string::npos && (slash == std::string::npos || dot > slash)) ? rel.substr(0, dot) : rel;
    std::replace(stem.begin(), stem.end(), '/', '.');
    return stem;
}

// Did this translation unit include `f`? `clang_getFile` cannot say: it answers for any file
// on disk, included or not, so a fragment under an includer's inactive `#if` would be read
// as an empty file rather than tried through the next includer.
inline bool includes(CXTranslationUnit tu, CXFile f) {
    struct Seen {
        CXFile f;
        bool hit;
    } seen{f, false};
    C().clang_getInclusions(
        tu,
        [](CXFile g, CXSourceLocation*, unsigned depth, CXClientData d) {
            auto* s = static_cast<Seen*>(d);
            if (depth > 0 && C().clang_File_isEqual(g, s->f)) s->hit = true;
        },
        &seen);
    return seen.hit;
}

// Every file this parse included, for `edges_done.inputs`. Each thread reports a spelling
// once, because the answer is a union over the tree and Runtime asks 18,263 times.
inline void inclusions(CXTranslationUnit tu, std::vector<std::string>& out) {
    C().clang_getInclusions(
        tu,
        [](CXFile g, CXSourceLocation*, unsigned depth, CXClientData d) {
            if (depth == 0) return;
            thread_local std::set<std::string> reported;
            std::string name = clang::str(C().clang_getFileName(g));
            if (name.empty() || !reported.insert(name).second) return;
            static_cast<std::vector<std::string>*>(d)->push_back(
                std::filesystem::path(name).lexically_normal().generic_string());
        },
        &out);
}

// Parse one file and read everything this reader reports about it. With `via`, the file is a
// fragment and the translation unit parsed is `via`'s, a file that includes it, with `args`
// being `via`'s arguments: only what is expanded in the fragment is kept, so its routines
// keep its own path, and what it means -- `UKismetMathLibrary::Add_IntInt`, the class whose
// body it is -- comes from the declarations the includer put in front of it.
inline void read(CXIndex index, const std::string& abs, const std::string& rel, const std::string& text,
                 const std::vector<std::string>& args, const rules::Rules& rules, Result& out,
                 const std::string& via = "", const std::string& via_rel = "") {
    out.hash = ids::hash_source(text);
    out.rel = rel;
    Ctx x;
    x.rel = rel;
    x.through = !via.empty();
    {
        std::string g = std::filesystem::path(abs).lexically_normal().generic_string();
        if (g.size() >= rel.size()) x.root = g.substr(0, g.size() - rel.size());
    }
    x.module = module_of(rel);
    x.text = text;
    x.rules = &rules;
    x.out = &out;
    x.line_starts.push_back(0);
    for (unsigned i = 0; i < text.size(); i++)
        if (text[i] == '\n') x.line_starts.push_back(i + 1);

    x.ff.path = rel;
    x.ff.lang = "cpp";
    x.ff.module = x.module;
    x.ff.content_hash = out.hash;

    std::vector<const char*> argv;
    for (const auto& a : args) argv.push_back(a.c_str());
    CXUnsavedFile unsaved{abs.c_str(), text.c_str(), static_cast<unsigned long>(text.size())};
    unsigned options = CXTranslationUnit_KeepGoing | CXTranslationUnit_DetailedPreprocessingRecord |
                       CXTranslationUnit_RetainExcludedConditionalBlocks * 0;
    const std::string& unit = via.empty() ? abs : via;
    CXErrorCode err = C().clang_parseTranslationUnit2(index, unit.c_str(), argv.data(), static_cast<int>(argv.size()),
                                                      &unsaved, 1, options, &x.tu);
    if (err != CXError_Success || !x.tu) {
        out.failed = "libclang could not parse it (error " + std::to_string(static_cast<int>(err)) + ")";
        x.ff.errors.push_back(out.failed);
        std::string j;
        x.ff.write_json(j);
        out.facts_json = std::move(j);
        return;
    }

    inclusions(x.tu, out.included);
    main_file() = C().clang_getFile(x.tu, abs.c_str());
    if (x.through) {
        if (!main_file() || !includes(x.tu, main_file())) {
            out.not_included = true;
            C().clang_disposeTranslationUnit(x.tu);
            return;
        }
        out.through = via_rel;
        x.ff.read_through = via_rel;
    }

    unsigned nd = C().clang_getNumDiagnostics(x.tu);
    for (unsigned i = 0; i < nd; i++) {
        CXDiagnostic d = C().clang_getDiagnostic(x.tu, i);
        CXDiagnosticSeverity s = C().clang_getDiagnosticSeverity(d);
        if (s == CXDiagnostic_Fatal) out.fatal++;
        if (s >= CXDiagnostic_Error) out.errors++;
        if (out.first_missing.empty()) {
            std::string m = clang::str(C().clang_getDiagnosticSpelling(d));
            if (m.find("file not found") != std::string::npos) out.first_missing = m;
        }
        C().clang_disposeDiagnostic(d);
    }

    // One tokenisation of the whole file, comments included.
    CXCursor root = C().clang_getTranslationUnitCursor(x.tu);
    CXToken* toks = nullptr;
    unsigned nt = 0;
    // Through an includer the unit's extent is the includer's text, so the fragment's own is
    // named: the whole of it, by offset.
    // The end is the last character, not one past it: an offset at the end of the file is
    // not a location in it, and a range ending nowhere tokenises to nothing.
    unsigned last = text.empty() ? 0 : static_cast<unsigned>(text.size() - 1);
    CXSourceRange whole = x.through
        ? C().clang_getRange(C().clang_getLocationForOffset(x.tu, main_file(), 0),
                             C().clang_getLocationForOffset(x.tu, main_file(), last))
        : C().clang_getCursorExtent(root);
    C().clang_tokenize(x.tu, whole, &toks, &nt);
    x.toks.reserve(nt);
    for (unsigned i = 0; i < nt; i++) {
        Tok t;
        t.kind = C().clang_getTokenKind(toks[i]);
        t.text = clang::str(C().clang_getTokenSpelling(x.tu, toks[i]));
        CXSourceRange r = C().clang_getTokenExtent(x.tu, toks[i]);
        unsigned a = 0, b = 0;
        offset_of(C().clang_getRangeStart(r), a);
        offset_of(C().clang_getRangeEnd(r), b);
        t.off = a;
        t.end = b;
        t.line = x.line_of(a);
        x.toks.push_back(std::move(t));
    }
    if (toks) C().clang_disposeTokens(x.tu, toks, nt);
    std::stable_sort(x.toks.begin(), x.toks.end(), [](const Tok& p, const Tok& q) { return p.off < q.off; });

    CXFile main = C().clang_getFile(x.tu, abs.c_str());
    if (main) {
        CXSourceRangeList* sk = C().clang_getSkippedRanges(x.tu, main);
        if (sk) {
            for (unsigned i = 0; i < sk->count; i++) {
                unsigned a = 0, b = 0;
                offset_of(C().clang_getRangeStart(sk->ranges[i]), a);
                offset_of(C().clang_getRangeEnd(sk->ranges[i]), b);
                out.skipped_lines += static_cast<long>(x.line_of(b)) - static_cast<long>(x.line_of(a)) + 1;
                size_t first = x.tok_at(a), last = x.tok_at(b + 1);
                if (last > first) x.pp_spans.push_back({x.toks[first].off, x.toks[last - 1].off});
            }
            C().clang_disposeSourceRangeList(sk);
        }
    }
    // Every directive line, through its backslash continuations.
    for (size_t i = 0; i < x.toks.size(); i++) {
        if (x.toks[i].text != "#" || (i > 0 && x.toks[i - 1].line == x.toks[i].line)) continue;
        unsigned line = x.toks[i].line;
        for (;;) {  // does this line end with a backslash?
            size_t eol = line < x.line_starts.size() ? x.line_starts[line] : x.text.size();
            size_t k = eol;
            while (k > 0 && (x.text[k - 1] == '\n' || x.text[k - 1] == '\r' || x.text[k - 1] == ' ' || x.text[k - 1] == '\t')) k--;
            if (k > 0 && x.text[k - 1] == '\\' && eol < x.text.size()) line++;
            else break;
        }
        size_t j = i;
        while (j + 1 < x.toks.size() && x.toks[j + 1].line <= line) j++;
        x.pp_spans.push_back({x.toks[i].off, x.toks[j].off});
        i = j;
    }
    std::sort(x.pp_spans.begin(), x.pp_spans.end());
    {  // disjoint, so a lookup needs only its predecessor
        std::vector<std::pair<unsigned, unsigned>> merged;
        for (const auto& sp : x.pp_spans) {
            if (!merged.empty() && sp.first <= merged.back().second) merged.back().second = std::max(merged.back().second, sp.second);
            else merged.push_back(sp);
        }
        x.pp_spans.swap(merged);
    }

    Reader(x).run();
    C().clang_disposeTranslationUnit(x.tu);

    std::string j;
    x.ff.write_json(j);
    out.facts_json = std::move(j);
}

}  // namespace extract
