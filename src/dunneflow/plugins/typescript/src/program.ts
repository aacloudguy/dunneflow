/**
 * The compilation, built in `open` — which is what `open` was always for.
 *
 * Chunk 9 held the file set and built nothing, and said so: a `ts.createProgram` over
 * `node_modules` paid for nothing would have been the easy thing to leave in. This is the
 * chunk that spends it, because **the resolved-symbol information the plugin exists to
 * provide only exists inside a program** — a per-file parse has no checker and is reduced
 * to guessing by name, which is the thing using the native toolchain is meant to stop.
 *
 * **One program per `tsconfig.json`, not one for the tree.** `PLAN-v2.md` puts the growth
 * axis at one worker per project; this is the same axis realised inside the plugin, which
 * costs the host nothing — no protocol change, `workers` still 1, the same file set. It is
 * not tidiness: a monorepo's projects disagree about compiler options in ways that decide
 * what resolves. `../DunneNote`'s `legacy/v0.1` declares `paths: { "$lib/*": ["src/lib/*"] }`
 * relative to itself, and one options object holds one `paths` map — so a single program
 * would silently fail to resolve every `$lib` import in one of the two copies of that
 * program, and report the calls as external with nothing anywhere saying why (rule 49).
 *
 * **Root names are the host's file set, never the tsconfig's `include`.** The host has
 * already decided what is program code and what is a test — 315 of DunneNote's 758 `.ts`
 * files are tests — and a program built from `include` would put every one of them back,
 * then resolve calls into them. Whatever a root file *imports* is pulled in by the
 * compiler and is a legitimate far end; whatever it does not is not in the map, and a call
 * to it is external.
 *
 * **Files under no tsconfig are a group of their own, not an error.** `packages/api-types`
 * has a `package.json` and no `tsconfig.json`, and its 206 files are real program code.
 * They get the default options, which is what `tsc` on a bare file does.
 */

import ts from "typescript";
import { dirname, join, relative, resolve, sep } from "node:path";
import { existsSync, readFileSync } from "node:fs";
import { makeSourceFile } from "./extract.js";
import { LIB_DIR, TS_LIBS } from "./libs.js";

/** `ingest.contract.SOURCE_TEXT`, applied at the one place this plugin reads a file. */
export function readSource(abs: string): string {
  return readFileSync(abs, "utf8").replace(/\r\n?/g, "\n");
}

/**
 * The cache's one spelling of a path, and it is the compiler's: forward slashes on every
 * platform, which is how the host is asked for a file (`C:/…/a.ts`) while `main.ts`
 * resolves the same file to `C:\…\a.ts`. Keyed as each side spelt it, the lookup in
 * `sourceFile` missed on Windows and handed the extractor a second, **unbound** parse of
 * the file, and the checker crashed on the first node it was asked about ("Cannot read
 * properties of undefined (reading 'members')"). Every `byPath` read and write goes
 * through this (rules 51 and 103).
 */
export function cacheKey(path: string): string {
  return path.split(sep).join("/");
}

/** The stored spelling of a path: relative to the analysed root, POSIX (rule 93). */
export function relPath(root: string, abs: string): string {
  let rel = relative(root, abs).split(sep).join("/");
  if (!rel || rel.startsWith("..")) rel = abs.split(sep).join("/");
  return rel;
}

/**
 * The compiler options a tsconfig asks for, with the ones this reader must have.
 *
 * `noEmit` because nothing is being built; `allowJs` off because a `.js` file is another
 * reader's or nobody's, and admitting one here would put facts in the map under a language
 * no manifest claims. Everything else is the project's own — `paths`, `baseUrl`,
 * `moduleResolution` and `jsx` are precisely what decides whether an import resolves.
 */
function optionsFor(configPath: string | null): ts.CompilerOptions {
  const base: ts.CompilerOptions = {
    noEmit: true,
    allowJs: false,
    // A checker that stopped at the first broken `.d.ts` in `node_modules` would refuse to
    // answer about code that compiles perfectly for its own author.
    skipLibCheck: true,
    noResolve: false,
    target: ts.ScriptTarget.Latest,
  };
  if (configPath === null) return base;
  const read = ts.readConfigFile(configPath, ts.sys.readFile);
  if (read.error !== undefined) return base;
  const parsed = ts.parseJsonConfigFileContent(
    read.config,
    ts.sys,
    dirname(configPath),
    undefined,
    configPath,
  );
  return { ...parsed.options, ...base };
}

/** The nearest `tsconfig.json` at or above this file, stopping at the analysed root. */
function projectOf(root: string, abs: string): string | null {
  let dir = dirname(abs);
  for (;;) {
    const candidate = join(dir, "tsconfig.json");
    if (existsSync(candidate)) return candidate;
    const up = dirname(dir);
    if (up === dir || dir.length <= root.length) return null;
    dir = up;
  }
}

export interface Project {
  /** The `tsconfig.json` this group was built from, or `""` for the files under none. */
  config: string;
  program: ts.Program;
  checker: ts.TypeChecker;
  /** Absolute paths, exactly as handed to `createProgram`. */
  roots: string[];
}

export class Session {
  root = ".";
  projects: Project[] = [];
  /** `cacheKey(path)` -> the source file the program parsed, so both passes share one AST. */
  private byPath = new Map<string, ts.SourceFile>();

  /**
   * Build one program per project over `files`.
   *
   * Returns a line per project for the `opened` frame's `diagnostics`, which has carried
   * the field since chunk 9 and never had anything to put in it. A reader that says how it
   * grouped a monorepo is a reader somebody can check; one that says nothing is one whose
   * resolution rate has no explanation (design rule 1).
   */
  open(root: string, files: string[]): string[] {
    this.root = root;
    this.projects = [];
    this.byPath.clear();

    const groups = new Map<string, string[]>();
    for (const f of files) {
      const abs = resolve(f);
      const config = projectOf(root, abs) ?? "";
      const bucket = groups.get(config);
      if (bucket === undefined) groups.set(config, [abs]);
      else bucket.push(abs);
    }

    const said: string[] = [];
    if (Object.keys(TS_LIBS).length === 0) {
      // **Said out loud rather than discovered from the numbers.** A program with no
      // standard library resolves, answers, and types every value through `Array`,
      // `Promise` or the DOM as `any`; the map it yields looks perfectly healthy and the
      // run cannot say why half its calls went nowhere (rule 49). It only happens to a
      // bundle built without `node_modules`, which `build.mjs` refuses — so if it is ever
      // read, something built this reader in a way nobody meant to.
      said.push("no TypeScript standard library is carried in this bundle — every value "
                + "typed through Array, Promise or the DOM will be `any`");
    }
    // Sorted, because the order programs are built in decides nothing about the answer and
    // an order the tool cannot defend is not an order (rule 66).
    for (const config of [...groups.keys()].sort()) {
      const roots = groups.get(config) ?? [];
      const options = optionsFor(config === "" ? null : config);
      const host = this.compilerHost(options);
      const program = ts.createProgram(roots, options, host);
      this.projects.push({
        config,
        program,
        checker: program.getTypeChecker(),
        roots,
      });
      said.push(
        `${config === "" ? "(no tsconfig)" : relPath(root, config)}: ` +
        `${roots.length} file${roots.length === 1 ? "" : "s"}`,
      );
    }
    return said;
  }

  /**
   * A compiler host that reads through `readSource` and parses through `makeSourceFile`.
   *
   * Both halves are load-bearing. The read is the newline normalisation the protocol
   * requires (`ingest.contract.SOURCE_TEXT`) — without it every CRLF file in the
   * compilation is a different string from the one the host hashed. The parse is
   * `extract.ts`' own, so the tree the checker reasons about and the tree the extractor
   * walks are the **same objects** and a declaration can be matched by node identity
   * rather than by re-deriving a line.
   */
  private compilerHost(options: ts.CompilerOptions): ts.CompilerHost {
    const host = ts.createCompilerHost(options, /* setParentNodes */ true);
    const cache = this.byPath;
    // **The standard library comes out of the bundle, not off the disk.** A bundled `tsc`
    // resolves `lib.es5.d.ts` beside `__dirname`, which here is the plugin's own directory
    // and holds no such file — and it does not refuse: it builds a program with no `Array`,
    // no `Promise` and no DOM, and answers anyway. `src/libs.ts` has the measurement.
    const libOf = (fileName: string): string | undefined =>
      fileName.startsWith(LIB_DIR) ? TS_LIBS[fileName.slice(LIB_DIR.length + 1)] : undefined;
    host.getDefaultLibLocation = () => LIB_DIR;
    host.getDefaultLibFileName = (o) => `${LIB_DIR}/${ts.getDefaultLibFileName(o)}`;
    host.fileExists = (fileName: string): boolean =>
      libOf(fileName) !== undefined || ts.sys.fileExists(fileName);
    host.readFile = (fileName: string): string | undefined => {
      const lib = libOf(fileName);
      if (lib !== undefined) return lib;
      try {
        return readSource(fileName);
      } catch {
        return undefined;
      }
    };
    host.getSourceFile = (fileName, _languageVersion, onError): ts.SourceFile | undefined => {
      const held = cache.get(cacheKey(fileName));
      if (held !== undefined) return held;
      let text: string;
      const lib = libOf(fileName);
      if (lib !== undefined) {
        text = lib;
      } else {
        try {
          text = readSource(fileName);
        } catch (err) {
          if (onError) onError(String(err));
          return undefined;
        }
      }
      // Named by the path the compiler asked for, because the compiler addresses it by
      // that and nothing in the extractor reads `sf.fileName` at all — a stored path is a
      // fact about a file and travels as one, in `FileFacts.path`, never on the AST.
      const sf = makeSourceFile(fileName, text);
      cache.set(cacheKey(fileName), sf);
      return sf;
    };
    return host;
  }

  /**
   * The source file for one path, **from the program when a program holds it**.
   *
   * A file the host asked about that no program holds is parsed on its own, which is what
   * happens when nothing has been opened — the shape chunk 9's tests drive. A file a
   * program holds whose text is not what the host just read is refused rather than
   * reconciled: the two passes would then be walking different trees, and every id the
   * edge pass minted for it would name a call site the map does not have.
   */
  sourceFile(abs: string, rel: string, source: string): ts.SourceFile {
    const held = this.byPath.get(cacheKey(abs));
    if (held === undefined) return makeSourceFile(rel, source);
    if (held.text !== source) {
      throw new Error(
        `${rel} was read one way for the compilation and another way for extraction. ` +
        `Both passes have to walk one tree, or the ids one mints name call sites the ` +
        `other never made.`,
      );
    }
    return held;
  }

  /**
   * The checker of the project holding one file, for the **extraction** pass.
   *
   * Chunk 10 needed a checker only in the edge sweep, which walks each project in turn and
   * has one to hand. Chunk 11c needs one per `extract` request, because a boundary can
   * now be a fact about the package a call resolves into (`pkg.ts`) and boundaries are
   * per-file facts — so the answer has to be available where the file is read.
   *
   * `undefined` where nothing has been opened, which is the shape chunk 9's tests drive
   * and is a real answer: no checker, no package rules, and the name rules decide alone.
   */
  checkerFor(abs: string): ts.TypeChecker | undefined {
    const at = resolve(abs);
    for (const project of this.projects) {
      if (project.program.getSourceFile(at) !== undefined) return project.checker;
    }
    return undefined;
  }

  close(): void {
    this.projects = [];
    this.byPath.clear();
  }
}
