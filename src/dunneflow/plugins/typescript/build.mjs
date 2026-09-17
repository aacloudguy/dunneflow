// The bundle, and the reason it is committed rather than built at analysis time.
//
// `plugin.json` fingerprints two named files — this script's output and the manifest —
// and `runtime.resource_root()` makes a checkout and a frozen application agree on what
// those two files are. So the checkout must run **the same bytes the application ships**,
// or rule 12's per-language stamp is a claim about a build nobody performed. A
// `pnpm install` at analysis time would also put the reader's identity in the hands of a
// lockfile resolution that happens on the reader's machine, months later.
//
// The TypeScript compiler is inlined, which is most of the 8 MB. That is the trade the
// plan took deliberately: the compiler is the only thing that can say what a TypeScript
// import refers to once `paths`, `bundler` resolution and `exports` maps are in play.
import { build } from "esbuild";

const result = await build({
  entryPoints: ["src/main.ts"],
  bundle: true,
  // **CommonJS, and the extension says so.** The TypeScript compiler is CJS: it calls
  // `require("fs")` at load and reads `__filename` to decide whether this filesystem is
  // case-sensitive. An ESM bundle has neither, and shimming all three from
  // `import.meta.url` is three chances to get a global subtly wrong for no benefit — this
  // reader is a program Node starts, not a module anybody imports. A `.cjs` file is
  // CommonJS whatever `package.json` says, so the extension is what makes it work in a
  // package marked `"type": "module"`.
  format: "cjs",
  platform: "node",
  target: "node20",
  outfile: "main.bundle.cjs",
  legalComments: "none",

  minify: false,
  metafile: true,
});

const out = result.metafile.outputs["main.bundle.cjs"];
console.log(`main.bundle.cjs — ${(out.bytes / 1024 / 1024).toFixed(1)} MB`);
