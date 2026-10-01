# Third-party notices

DunneFlow itself is released under the [MIT licence](LICENSE). It also carries other people's
work, each under its own licence, and this file says which. The full text of every licence
named here is in [`licenses/`](licenses/), copied verbatim from the version that ships.

## In this repository

| Component | Version | Where it is | Licence | Copyright |
|---|---|---|---|---|
| [deck.gl](https://deck.gl) | 9.3.10 | `src/dunneflow/web/vendor/deck.gl.min.js` | MIT | Vis.gl contributors |
| [Mermaid](https://mermaid.js.org) | 11.17.2 | `src/dunneflow/web/vendor/mermaid.min.js` | MIT | 2014–2022 Knut Sveidqvist |
| [markdown-it](https://github.com/markdown-it/markdown-it) | 14.3.1 | `src/dunneflow/web/vendor/markdown-it.min.js` | MIT | 2014 Vitaly Puzrin, Alex Kocharin |
| [@hpcc-js/wasm](https://github.com/hpcc-systems/hpcc-js-wasm) | 2.35.0 | `src/dunneflow/web/vendor/graphviz.umd.js` | Apache-2.0 | HPCC Systems |
| [Graphviz](https://graphviz.org), compiled to WebAssembly inside the file above | 15.1.0 | `src/dunneflow/web/vendor/graphviz.umd.js` | EPL-1.0 | AT&T and the Graphviz contributors |
| [TypeScript](https://www.typescriptlang.org) | 5.9.3 | `src/dunneflow/plugins/typescript/main.bundle.cjs` | Apache-2.0 | Microsoft Corporation |

Mermaid's minified file includes its own dependencies. Their licence headers are kept inside
the file. Among them is DOMPurify, which is offered under Apache-2.0 or MPL-2.0, and is used
here under Apache-2.0.

TypeScript's own third-party notices are reproduced in
[`licenses/typescript-third-party-notices.txt`](licenses/typescript-third-party-notices.txt).

Graphviz is distributed here in object form only, inside `graphviz.umd.js`, as @hpcc-js/wasm
publishes it. The source is available from [graphviz.org](https://graphviz.org/download/source/)
and from the [@hpcc-js/wasm repository](https://github.com/hpcc-systems/hpcc-js-wasm), and is
offered under the terms of the Eclipse Public License 1.0. Any provisions of DunneFlow's licence
that differ from the EPL are offered by DunneFlow's author alone and not by the Graphviz
contributors.

## In the packaged applications only

The downloadable macOS, Windows and Linux builds also include the following. A checkout run
with `uv` uses your own copies instead.

| Component | Licence | Text |
|---|---|---|
| [CPython](https://www.python.org) 3.12 | PSF License Agreement | [`licenses/python.txt`](licenses/python.txt) |
| [PyYAML](https://pyyaml.org) 6.0 | MIT | [`licenses/pyyaml.txt`](licenses/pyyaml.txt) |
| [OpenSSL](https://www.openssl.org) 3, as linked by CPython | Apache-2.0 | [`licenses/openssl-apache-2.0.txt`](licenses/openssl-apache-2.0.txt) |
| [PyInstaller](https://pyinstaller.org) bootloader | GPL-2.0 with the bootloader exception, which permits distributing it with any program | [pyinstaller.org/en/stable/license.html](https://pyinstaller.org/en/stable/license.html) |

These notices are bundled inside each application next to DunneFlow's own `LICENSE`.
