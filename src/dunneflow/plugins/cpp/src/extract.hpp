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
    std::string construct_usr;  // a construction's record
    std::string receiver_usr;   // a member call's receiver type
};

// One definition this file holds, as the edge pass names it to the host.
struct Def {
    std::string usr, file, name, qualname;
    int args = -1;
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
    std::vector<std::string> markers;  // every word of the marking macro, as `decorators` read it
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
    std::vector<Def> defs;
    std::vector<Over> overs;
    std::vector<std::pair<std::string, std::string>> bases;  // record USR -> base USR
    std::vector<Mark> marks;
    std::set<std::string> uses;  // USRs of routines named here as a value, not called
    std::string failed;          // a parse clang refused outright
    int fatal = 0, errors = 0;   // diagnostics in this file's parse
    std::string first_missing;   // the first include it could not find
    long skipped_lines = 0;      // lines in inactive #if arms of this file
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
    unsigned body_lo = 0, body_hi = 0;  // offsets of `{` and `}`
    bool macro_written = false;         // no `{` is written here: a macro wrote the whole body
};

class Reader {
public:
    Reader(Ctx& ctx) : x_(ctx) {}

    void run() {
        CXCursor root = C().clang_getTranslationUnitCursor(x_.tu);
        collect_macros(root);
        module_scope_ = make_module_scope();
        visit(root);
        // Calls and control are read from the tokens once the walk has said what each written
        // call reaches, routine by routine, in the order the routines were defined.
        for (const auto& r : routines_) {
            scan_calls(r.get());
            emit_calls(r.get());
            scan_control(r.get());
        }
        literals();
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
    facts::Routine module_scope_;
    bool module_scope_used_ = false;

    // ------------------------------------------------------------ walking --- //

    struct Frame {
        Reader* self;
    };

    static CXChildVisitResult trampoline(CXCursor c, CXCursor parent, CXClientData d) {
        static_cast<Reader*>(d)->one(c, parent);
        return CXChildVisit_Continue;
    }

    void visit(CXCursor c) { C().clang_visitChildren(c, trampoline, this); }

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
                               k == CXCursor_UnexposedDecl || is_record_kind(k)))
                visit(c);
            return;
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
            record(c, k);
            visit(c);
            return;
        }
        if (k == CXCursor_VarDecl && stack_.empty()) constant(c);
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

        if (k == CXCursor_DeclRefExpr || k == CXCursor_MemberRefExpr) value_use(c);
        if (!stack_.empty()) {
            if (k == CXCursor_CallExpr) note_call(c, parent);
            else if (k == CXCursor_CXXNewExpr) note_new(c);
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
        // refused here as having no body, and so was every such function in any tree.
        //
        // Not inside a record the macro also named, which `record` already leaves as the
        // macro's: `DECLARE_CYCLE_STAT` is a `struct FStat_X` with seven accessors, 441 times
        // over in Core alone, and none of them is anything a reader came to find.
        if (x_.in_macro(lo)) {
            CXCursor owner = C().clang_getCursorSemanticParent(c);
            unsigned ra, rb;
            if (is_record_kind(C().clang_getCursorKind(owner)) && in_main(owner)) {
                extent(owner, ra, rb);
                if (!x_.written_in_macro(ra, spelling(owner))) return false;
            }
            return !C().clang_CXXMethod_isDefaulted(c);
        }
        // `= default` is given a body by clang and has none as written: not a routine.
        size_t i = x_.tok_at(lo);
        return i < x_.toks.size() && x_.toks[i].off == lo && (x_.toks[i].text == "{" || x_.toks[i].text == "try");
    }

    Routine* routine(CXCursor c) {
        unsigned lo, hi;
        if (!body(c, lo, hi)) return nullptr;  // `= default`, `= delete`: no body, no routine
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
        r->body_lo = lo;
        r->body_hi = hi;
        size_t first = x_.tok_at(lo);
        r->macro_written = !(first < x_.toks.size() && x_.toks[first].off == lo &&
                             (x_.toks[first].text == "{" || x_.toks[first].text == "try"));
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
        d.args = C().clang_Cursor_getNumArguments(c);
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
        // Once, though the walk meets it twice: `struct { int a; } g;` is a declaration at
        // file scope and again the child of `g`'s, and was two structures.
        if (!records_read_.insert({a, b}).second) return;
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
        } else if (!x_.written_in_macro(a, name)) {
            // A record a macro names by pasting is the macro's too: Unreal's
            // `DECLARE_CYCLE_STAT(..., STAT_X, ...)` is a `struct FStat_STAT_X`, and there
            // were hundreds. One whose name the file writes is kept: `TAILQ_HEAD(joblist,
            // job)` is the `struct joblist` tmux goes on to use by that name.
            return;
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
            if (!hit) continue;
            facts::Entrypoint e;
            // **The USR is in the id**: two overloads of one name, both marked, were one
            // way in -- the second `INSERT OR REPLACE`d the first -- and 157 of Runtime's
            // Blueprint ways in were overloads. A name is not an identity (rule 106).
            std::string u = usr(c);
            e.id = ids::entrypoint_id(x_.rel, {qualname, rule.kind, u});
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
                m.markers = decs;
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
    std::set<std::pair<unsigned, unsigned>> records_read_;  // by extent, so each is read once
    std::map<unsigned, std::vector<std::pair<CXCursor, CXCursor>>> macro_calls_;  // by the macro's offset

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

    // In a routine's body, during the walk: note what clang made of each call.
    void note_call(CXCursor c, CXCursor parent) {
        unsigned a, b;
        extent(c, a, b);
        CXCursor ref = C().clang_getCursorReferenced(c);
        // In a body a macro wrote whole there is nothing to scan, so what clang resolved is all
        // there is, and each call is named by what it reaches. Constructors are left out: from
        // here an implicit one cannot be told from a written one.
        if (!stack_.empty() && stack_.back()->macro_written) {
            if (C().clang_Cursor_isNull(ref) || !is_function_kind(C().clang_getCursorKind(ref)) ||
                C().clang_getCursorKind(ref) == CXCursor_Constructor)
                return;
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
            pending_[stack_.back()].push_back(p);
            return;
        }
        // Every call a macro written here expands to, by the macro's offset: which of them
        // the written call is, is decided at `emit_calls`, and not by which came first.
        if (x_.macro_names.count(a)) macro_calls_[a].push_back({c, ref});
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

    // The ranges inside `r`'s body that belong to a routine nested in it.
    std::vector<std::pair<unsigned, unsigned>> inner(const Routine* r) {
        std::vector<std::pair<unsigned, unsigned>> out;
        for (const auto& o : routines_)
            if (o.get() != r && o->body_lo > r->body_lo && o->body_hi <= r->body_hi) out.push_back({o->body_lo, o->body_hi});
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
        if (owner->macro_written) return;  // nothing is written to scan: `note_call` has them
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
            boundaries(owner, s);

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
                    auto mc = macro_calls_.find(p.off);
                    if (mc != macro_calls_.end())
                        for (const auto& [c, r] : mc->second)
                            if (!C().clang_Cursor_isNull(r)) e.macro_usrs.push_back(usr(r));
                }
            } else if (p.resolved) {
                resolve(e, p.call, p.ref);
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

    void boundaries(Routine* owner, const facts::CallSite& s) {
        for (const auto& rule : x_.rules->boundaries) {
            if (!rule.matches(*s.callee_expr)) continue;
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
            h.evidence = *s.callee_expr;
            h.salience = rule.salience;
            x_.ff.boundaries.push_back(h);
        }
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
        if (owner->macro_written) return;
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
