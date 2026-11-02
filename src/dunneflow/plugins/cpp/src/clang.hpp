// libclang, opened at run time and never linked.
//
// **Why not linked.** The reader is built where it runs with one argv for every platform
// (`plugin.json`'s `build`), and a link line would have to name where this machine keeps
// libclang: `/Library/Developer/CommandLineTools/usr/lib`, `~/.local/llvm/lib`, or Visual
// Studio's `VC\Tools\Llvm\x64\bin`. Opened here instead, the library is found the way the
// compiler that built the reader finds its own: `clang++ -print-resource-dir` names the
// resource directory, and libclang sits two directories above it (three on Windows, where
// it is in `bin`). `DUNNEFLOW_LIBCLANG` names it outright and wins.
//
// **Every function is listed once, below**, with its type taken from the vendored
// declaration by `decltype` — an unevaluated use, so nothing is linked. A function the
// library lacks is refused by name when the reader starts, before any file is read: a
// reader that called a null pointer on the first file that needed it would be the failure
// that looks like a crash in somebody's program.

#pragma once

#include <clang-c/CXCompilationDatabase.h>
#include <clang-c/Index.h>

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <dlfcn.h>
#endif

#define DUNNEFLOW_CLANG_FUNCTIONS(X)            \
    X(clang_getClangVersion)                    \
    X(clang_createIndex)                        \
    X(clang_disposeIndex)                       \
    X(clang_parseTranslationUnit2)              \
    X(clang_disposeTranslationUnit)             \
    X(clang_getTranslationUnitCursor)           \
    X(clang_visitChildren)                      \
    X(clang_getCursorKind)                      \
    X(clang_getCursorSpelling)                  \
    X(clang_getCString)                         \
    X(clang_disposeString)                      \
    X(clang_getCursorLocation)                  \
    X(clang_getCursorExtent)                    \
    X(clang_getRangeStart)                      \
    X(clang_getRangeEnd)                        \
    X(clang_getSpellingLocation)                \
    X(clang_getExpansionLocation)               \
    X(clang_getFileLocation)                    \
    X(clang_Location_isFromMainFile)            \
    X(clang_Location_isInSystemHeader)          \
    X(clang_getCursorReferenced)                \
    X(clang_getCursorDefinition)                \
    X(clang_isCursorDefinition)                 \
    X(clang_getCanonicalCursor)                 \
    X(clang_getCursorSemanticParent)            \
    X(clang_getCursorLexicalParent)             \
    X(clang_getCursorUSR)                       \
    X(clang_Cursor_isNull)                      \
    X(clang_equalCursors)                       \
    X(clang_Cursor_isAnonymous)                 \
    X(clang_getCursorType)                      \
    X(clang_getTypeSpelling)                    \
    X(clang_getCanonicalType)                   \
    X(clang_getTypeDeclaration)                 \
    X(clang_getPointeeType)                     \
    X(clang_getCursorResultType)                \
    X(clang_Cursor_getNumArguments)             \
    X(clang_Cursor_getArgument)                 \
    X(clang_CXXMethod_isVirtual)                \
    X(clang_CXXMethod_isPureVirtual)            \
    X(clang_CXXMethod_isStatic)                 \
    X(clang_getOverriddenCursors)               \
    X(clang_disposeOverriddenCursors)           \
    X(clang_getCXXAccessSpecifier)              \
    X(clang_Cursor_getRawCommentText)           \
    X(clang_Cursor_isDynamicCall)               \
    X(clang_Cursor_hasAttrs)                    \
    X(clang_tokenize)                           \
    X(clang_disposeTokens)                      \
    X(clang_getTokenKind)                       \
    X(clang_getTokenSpelling)                   \
    X(clang_getTokenExtent)                     \
    X(clang_getTokenLocation)                   \
    X(clang_getNumDiagnostics)                  \
    X(clang_getDiagnostic)                      \
    X(clang_getDiagnosticSeverity)              \
    X(clang_getDiagnosticSpelling)              \
    X(clang_getDiagnosticLocation)              \
    X(clang_disposeDiagnostic)                  \
    X(clang_getSkippedRanges)                   \
    X(clang_disposeSourceRangeList)             \
    X(clang_getFile)                            \
    X(clang_getFileName)                        \
    X(clang_getIncludedFile)                    \
    X(clang_CompilationDatabase_fromDirectory)  \
    X(clang_CompilationDatabase_getCompileCommands) \
    X(clang_CompilationDatabase_dispose)        \
    X(clang_CompileCommands_getSize)            \
    X(clang_CompileCommands_getCommand)         \
    X(clang_CompileCommands_dispose)            \
    X(clang_CompileCommand_getDirectory)        \
    X(clang_CompileCommand_getNumArgs)          \
    X(clang_CompileCommand_getArg)

namespace clang {

struct Api {
#define DUNNEFLOW_DECLARE(name) decltype(&::name) name = nullptr;
    DUNNEFLOW_CLANG_FUNCTIONS(DUNNEFLOW_DECLARE)
#undef DUNNEFLOW_DECLARE
    std::string path;     // the library that was opened
    std::string version;  // what it says it is
};

// The one table every part of the reader calls through. Filled once, by `load`.
inline Api& api() {
    static Api a;
    return a;
}

// Run a command and return its first line of output, or "" when it could not be run.
inline std::string first_line(const std::string& command) {
#ifdef _WIN32
    FILE* p = _popen(command.c_str(), "r");
#else
    FILE* p = popen(command.c_str(), "r");
#endif
    if (!p) return "";
    char buf[4096];
    std::string out;
    if (std::fgets(buf, sizeof buf, p)) out = buf;
#ifdef _WIN32
    _pclose(p);
#else
    pclose(p);
#endif
    while (!out.empty() && (out.back() == '\n' || out.back() == '\r')) out.pop_back();
    return out;
}

// Where this machine's libclang may be, in the order they are tried.
inline std::vector<std::string> candidates() {
    std::vector<std::string> out;
    if (const char* env = std::getenv("DUNNEFLOW_LIBCLANG"); env && *env) {
        out.push_back(env);
        return out;
    }
#ifdef _WIN32
    std::string res = first_line("clang++ -print-resource-dir 2>NUL");
    if (!res.empty()) out.push_back(res + "\\..\\..\\..\\bin\\libclang.dll");
#else
    std::string res = first_line("clang++ -print-resource-dir 2>/dev/null");
    if (!res.empty()) {
        std::string lib = res + "/../..";
#ifdef __APPLE__
        out.push_back(lib + "/libclang.dylib");
#else
        out.push_back(lib + "/libclang.so");
        out.push_back(lib + "/libclang.so.1");
        // A distribution's unversioned name is a development package's; the runtime one
        // carries the major version, which is the resource directory's last component.
        std::string major = res.substr(res.find_last_of('/') + 1);
        out.push_back(lib + "/libclang-" + major + ".so.1");
        out.push_back(lib + "/libclang-" + major + ".so");
#endif
    }
#endif
    return out;
}

// Open libclang and bind every function. "" on success, otherwise the sentence the host
// shows: which paths were tried, or which functions this library lacks.
inline std::string load() {
    Api& a = api();
    std::string tried;
    void* handle = nullptr;
    for (const auto& c : candidates()) {
#ifdef _WIN32
        handle = reinterpret_cast<void*>(LoadLibraryA(c.c_str()));
#else
        handle = dlopen(c.c_str(), RTLD_NOW | RTLD_LOCAL);
#endif
        if (handle) {
            a.path = c;
            break;
        }
        tried += (tried.empty() ? "" : ", ") + c;
    }
    if (!handle) {
        return "no libclang could be opened" +
               (tried.empty() ? std::string(": `clang++ -print-resource-dir` named no resource "
                                            "directory, and DUNNEFLOW_LIBCLANG is not set")
                              : " (tried " + tried + "); set DUNNEFLOW_LIBCLANG to the library");
    }
    std::string missing;
#ifdef _WIN32
#define DUNNEFLOW_BIND(name)                                                                  \
    a.name = reinterpret_cast<decltype(a.name)>(                                              \
        reinterpret_cast<void*>(GetProcAddress(static_cast<HMODULE>(handle), #name)));        \
    if (!a.name) missing += (missing.empty() ? "" : ", ") + std::string(#name);
#else
#define DUNNEFLOW_BIND(name)                                                                  \
    a.name = reinterpret_cast<decltype(a.name)>(dlsym(handle, #name));                        \
    if (!a.name) missing += (missing.empty() ? "" : ", ") + std::string(#name);
#endif
    DUNNEFLOW_CLANG_FUNCTIONS(DUNNEFLOW_BIND)
#undef DUNNEFLOW_BIND
    if (!missing.empty()) {
        return a.path + " is too old for this reader: it has no " + missing;
    }
    CXString v = a.clang_getClangVersion();
    a.version = a.clang_getCString(v) ? a.clang_getCString(v) : "";
    a.clang_disposeString(v);
    return "";
}

// A CXString as a std::string, disposed.
inline std::string str(CXString s) {
    const char* c = api().clang_getCString(s);
    std::string out = c ? c : "";
    api().clang_disposeString(s);
    return out;
}

}  // namespace clang
