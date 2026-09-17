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
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

/**
 * Carry TypeScript's own `lib*.d.ts` into the bundle, in place of `src/libs.ts`' empty map.
 *
 * A bundled `tsc` looks for its default library beside `__dirname`, which after bundling is
 * this plugin's directory — so without this the compiler builds a program with no `Array`,
 * no `Promise` and no DOM, types everything through them as `any`, **and still answers**.
 * `src/libs.ts` has the measurement; the short version is that it costs four edges and the
 * whole explanation of where the other 2,868 calls go.
 *
 * Read from `node_modules` at bundle time and never at analysis time, for the reason the
 * bundle itself is committed: `plugin.json` fingerprints these bytes, so what is stamped and
 * what runs have to be one thing (rule 12).
 */
const tsLibs = {
  name: "ts-libs",
  setup(build) {
    const target = resolve("src/libs.ts");
    const dir = resolve("node_modules/typescript/lib");
    build.onLoad({ filter: /src[\\/]libs\.ts$/ }, (args) => {
      if (resolve(args.path) !== target) return null;
      const names = readdirSync(dir).filter((f) => /^lib\..*\.d\.ts$/.test(f));
      if (names.length === 0) {
        // Refused rather than bundled empty: an empty map is exactly the state this plugin
        // exists to leave behind, and it produces a reader that works and explains nothing.
        throw new Error(`no lib*.d.ts under ${dir} — run pnpm install first`);
      }
      const entries = names
        .map((n) => `  ${JSON.stringify(n)}: ${JSON.stringify(readFileSync(join(dir, n), "utf8"))},`)
        .join("\n");
      const bytes = names.reduce((n, f) => n + readFileSync(join(dir, f)).length, 0);
      console.log(`  ${names.length} lib*.d.ts — ${(bytes / 1024 / 1024).toFixed(1)} MB`);
      return {
        loader: "ts",
        contents:
          `export const TS_LIBS: Record<string, string> = {\n${entries}\n};\n` +
          `export const LIB_DIR = "/__dunneflow_ts_libs__";\n`,
      };
    });
  },
};

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
  // `DUNNEFLOW_BUNDLE_OUT` is the freshness gate's, and nothing else uses it: it builds to
  // a scratch file and compares bytes, because every other check on this bundle — that it
  // exists, that the fingerprint names it, that `node` can run it — passes over one built
  // from last month's source (rule 37).
  outfile: process.env.DUNNEFLOW_BUNDLE_OUT ?? "main.bundle.cjs",
  legalComments: "none",

  minify: false,
  metafile: true,
  plugins: [tsLibs],
});

// Keyed by esbuild on the path *it* wrote, which is not the one that was asked for when
// that was absolute — so the one output is taken rather than looked up by name.
const [name, out] = Object.entries(result.metafile.outputs)[0];
console.log(`${name} — ${(out.bytes / 1024 / 1024).toFixed(1)} MB`);
