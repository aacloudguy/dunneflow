/**
 * The TypeScript reader, on the far side of a pipe.
 *
 * `tests/plugins/python-oop/worker.py` is the worked example this follows, and the two
 * agree on every rule that matters:
 *
 * **stdout carries protocol and nothing else.** Every diagnostic goes to stderr, which the
 * host drains into a ring buffer and never parses — `runtime._desktop_session`'s lesson,
 * one process over: text a healthy program also writes cannot be a control channel. A
 * single stray `console.log` here is a frame the host cannot read, and it refuses the
 * language once and loudly rather than skipping six hundred files quietly.
 *
 * **Every reply echoes the request's `id`.** The host correlates on it and refuses an
 * answer to something else arriving as this one.
 *
 * **A file that will not parse is `facts` with an error, and a file that made this
 * reader throw is `failed`** — two different facts, and only the second lets the host
 * write the record. A reader that has just crashed on a file is not the right authority
 * on what that file is.
 *
 * `open` takes the whole file set because a reader that resolves symbols needs the whole
 * compilation, and that is now what it is for: one `ts.Program` per `tsconfig.json`, built
 * there and held for the session (`program.ts`).
 *
 * **`edges` is the one frame that streams**, and the id discipline does not relax for it:
 * every `edge` carries the request's id and so does the `edges_done` that ends the run.
 * One frame per edge rather than one array, because a monorepo's answer is tens of
 * thousands of them and a single JSON line holding all of them is a payload with no bound.
 */

import { createInterface } from "node:readline";
import { resolve as resolvePath } from "node:path";
import { extractFile } from "./extract.js";
import { collectEdges } from "./edges.js";
import { hashSource } from "./ids.js";
import { Session, readSource, relPath } from "./program.js";
import { parseRules, type RuleSet } from "./rules.js";
import { SCHEMA_VERSION, type FileFacts } from "./facts.js";

const PROTOCOL = 1;
const LANG = "typescript";
const VERSION = "1.1.0";

interface Frame {
  t?: string;
  id?: number;
  [key: string]: unknown;
}

const session = new Session();
let rules: RuleSet = parseRules({});

function send(frame: Record<string, unknown>): void {
  process.stdout.write(JSON.stringify(frame) + "\n");
}

/** The other channel. Evidence, and never a control signal. */
function note(text: string): void {
  process.stderr.write(text + "\n");
}

function onHello(): Record<string, unknown> {
  return {
    t: "ready",
    lang: LANG,
    version: VERSION,
    protocol: PROTOCOL,
    schema_version: SCHEMA_VERSION,
    capabilities: { supplies_edges: true, reports_literals: true },
  };
}

function onOpen(frame: Frame): Record<string, unknown> {
  const started = Date.now();
  session.root = String(frame["root"] ?? ".");
  // **The rules arrive with the session and are never baked in.** A plugin carrying its
  // own copy of `detectors/typescript.yaml` is a second answer that stops moving the
  // moment somebody edits the file, and that file is in this language's extraction stamp
  // precisely so an edit re-reads every TypeScript file (rule 51).
  rules = parseRules(frame["rules"]);
  const files = (frame["files"] as string[]) ?? [];
  const diagnostics: string[] = [];
  if (rules.boundaries.length === 0) {
    // Not an error and not silent. A run with no rules yields a map with no boundaries,
    // no network calls and nothing to say why — which looks exactly like a program that
    // touches nothing (rule 49).
    note(
      `no boundary rules arrived with this session, so nothing in these ${files.length} ` +
      `files can be matched against one. The map will report no boundaries at all.`,
    );
    diagnostics.push("no boundary rules arrived with this session");
  }
  // **The compilation, built here because here is the only place it can be.** A checker
  // over a subset answers wrongly rather than partially, which is why `open` is handed
  // every file of this language whether or not it changed.
  diagnostics.push(...session.open(session.root, files));
  return {
    t: "opened",
    files: files.length,
    program_ms: Date.now() - started,
    diagnostics,
  };
}

function onExtract(frame: Frame): Record<string, unknown> {
  const abs = resolvePath(String(frame["path"] ?? ""));
  const rel = relPath(session.root, abs);

  let source: string;
  try {
    // **Newlines are normalised, and that is the host's contract rather than taste.**
    // The host hashes what `Path.read_text` gave it, and Python reads text files with
    // universal newlines on: `\r\n` and a lone `\r` both arrive as `\n`. `readFileSync`
    // does not, so a CRLF file hashes differently on the two sides — every one of them,
    // and the host's echo check then reports the file as having *changed while it was
    // being read*. Measured on uigen: 2 of 54 files, both generated with CRLF, both
    // reported unreadable in a map that was otherwise perfect. `program.readSource` is
    // the one place it is done, because the compilation must read the same bytes. See
    // `ingest/contract.py:SOURCE_TEXT`.
    source = readSource(abs);
  } catch (err) {
    // The host hashes what *it* read and compares; a file this reader cannot open at all
    // is a failure it may describe, because nothing was read badly — nothing was read.
    return { t: "failed", reason: `could not be read: ${String(err)}` };
  }

  // **Echoed rather than assumed.** The host's hash travels with the request and this
  // returns the hash of what was actually read; a mismatch means the file changed under
  // the run, and its facts describe neither version for certain.
  const echoed = hashSource(source);

  let facts: FileFacts;
  try {
    // The compilation's own source file where there is one, so the extraction walk and
    // the edge pass are one traversal of one tree (`program.Session.sourceFile`).
    facts = extractFile(rel, source, rules, session.sourceFile(abs, rel, source),
                        session.checkerFor(abs));
  } catch (err) {
    return {
      t: "failed",
      reason: err instanceof Error ? `${err.message}\n${err.stack ?? ""}`.trim() : String(err),
    };
  }

  // A file the parser could not make sense of comes back as facts carrying the error, the
  // same shape the in-process Python reader produces — so it is cached and not retried,
  // and `WalkStats` counts it the way it counts every other unreadable file.
  return { t: "facts", hash: echoed, facts };
}

/**
 * Every call's far end, streamed.
 *
 * Asked once per session, after the files and before `close`. It answers about the **whole
 * compilation** and not about what changed, because a checker's answer for one file is
 * built out of all of them — which is why the host replaces its stored set whole rather
 * than merging into it.
 *
 * A file the walk threw on is **named on stderr**, not folded into the tally: the tally is
 * a claim the host checks against what arrived, and a count that quietly absorbed a failure
 * would make that check pass over a reader that had lost a file (rule 37).
 */
function onEdges(id: number | undefined): void {
  const harvest = collectEdges(session, rules);
  for (const edge of harvest.edges) send({ t: "edge", id, edge });
  if (harvest.failed.length) {
    note(`the edge pass could not walk ${harvest.failed.length} file(s): ` +
         harvest.failed.slice(0, 20).join(", "));
  }
  send({
    t: "edges_done",
    id,
    supplied: harvest.edges.filter((e) => e.file !== undefined && e.file !== "").length,
    // Two reasons, two numbers. `outside` is a call whose far end the checker named and
    // this map does not hold — a library, a `.d.ts`, a declaration with no body — and a
    // map full of them is a correct map of a program that leans on its dependencies.
    // `unknown` is a call the checker could not resolve at all. Summed into `unresolved`
    // for the protocol's own arithmetic, and sent apart as well, because the sum is the
    // one thing neither of them says (rule 32).
    unresolved: harvest.outside + harvest.unknown,
    outside: harvest.outside,
    unknown: harvest.unknown,
  });
}

const HANDLERS: Record<string, (frame: Frame) => Record<string, unknown>> = {
  hello: onHello,
  open: onOpen,
  extract: onExtract,
};

function main(): void {
  const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    let frame: Frame;
    try {
      frame = JSON.parse(trimmed) as Frame;
    } catch {
      note(`unreadable frame: ${trimmed.slice(0, 120)}`);
      return;
    }
    const id = frame.id;
    if (frame.t === "close") {
      session.close();
      send({ t: "closed", id });
      rl.close();
      process.exit(0);
    }
    // Outside `HANDLERS` because a handler there returns one frame and this returns a run
    // of them. Kept a special case rather than widening every handler's type, on `close`'s
    // precedent: two frames of five are not the shape, and a signature that admitted a
    // stream everywhere would say every frame might be one.
    if (frame.t === "edges") {
      try {
        onEdges(id);
      } catch (err) {
        send({
          t: "error",
          id,
          reason: err instanceof Error
            ? `${err.message}\n${err.stack ?? ""}`.trim()
            : String(err),
        });
      }
      return;
    }
    const handler = HANDLERS[String(frame.t)];
    if (handler === undefined) {
      send({ t: "error", id, reason: `unknown frame ${String(frame.t)}` });
      return;
    }
    try {
      send({ ...handler(frame), id });
    } catch (err) {
      send({
        t: "error",
        id,
        reason: err instanceof Error ? `${err.message}\n${err.stack ?? ""}`.trim() : String(err),
      });
    }
  });
}

main();
