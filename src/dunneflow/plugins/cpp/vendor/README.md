# Vendored: libclang's C headers

`clang-c/*.h` are LLVM's public C API headers, copied unmodified from LLVM 22.1.0
(Homebrew's `llvm` keg, `include/clang-c`), under the Apache License v2.0 with LLVM
Exceptions (`LICENSE.TXT`, LLVM's own).

They are here because the reader is built where it runs and **libclang is loaded at run time,
never linked**: the declarations give each function its type (`decltype`), and the library a
machine has is opened with `dlopen` or `LoadLibrary` (`src/clang.hpp`). The macOS Command
Line Tools ship `libclang.dylib` without these headers, and Visual Studio's bundled LLVM
ships `libclang.dll` without them, so a reader that needed the machine's copy would not build
on either.

The C API is stable across versions (`CINDEX_VERSION_MAJOR` has been 0 since it was
introduced), and the reader binds only functions every supported libclang has. A function
an older library lacks is refused by name when the reader starts, never called.
