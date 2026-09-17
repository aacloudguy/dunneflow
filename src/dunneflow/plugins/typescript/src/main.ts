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
 * compilation. **This chunk resolves nothing**, so it holds the set and builds no program:
 * chunk 9 is extraction only and every TypeScript call is left external by the host, which
 * names the count. Stated rather than left to be discovered — the protocol already has the
 * shape chunk 10 needs, and pretending to use it now would be a `ts.createProgram` over
 * node_modules paid for nothing.
 */

import { createInterface } from "node:readline";
import { readFileSync } from "node:fs";
import { relative } from "node:path";
import { extractFile } from "./extract.js";
import { hashSource } from "./ids.js";
import { parseRules, type RuleSet } from "./rules.js";
import { SCHEMA_VERSION, type FileFacts } from "./facts.js";

const PROTOCOL = 1;
const LANG = "typescript";
const VERSION = "1.0.0";

interface Frame {
  t?: string;
  id?: number;
  [key: string]: unknown;
}

const session: { root: string; rules: RuleSet } = {
  root: ".",
  rules: parseRules({}),
};

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
    capabilities: { supplies_edges: false, reports_literals: true },
  };
}

function onOpen(frame: Frame): Record<string, unknown> {
  const started = Date.now();
  session.root = String(frame["root"] ?? ".");
  // **The rules arrive with the session and are never baked in.** A plugin carrying its
  // own copy of `detectors/typescript.yaml` is a second answer that stops moving the
  // moment somebody edits the file, and that file is in the core extraction key precisely
  // so an edit re-reads every language (rule 51).
  session.rules = parseRules(frame["rules"]);
  const files = (frame["files"] as string[]) ?? [];
  if (session.rules.boundaries.length === 0) {
    // Not an error and not silent. A run with no rules yields a map with no boundaries,
    // no network calls and nothing to say why — which looks exactly like a program that
    // touches nothing (rule 49).
    note(
      `no boundary rules arrived with this session, so nothing in these ${files.length} ` +
      `files can be matched against one. The map will report no boundaries at all.`,
    );
  }
  return {
    t: "opened",
    files: files.length,
    program_ms: Date.now() - started,
    diagnostics: [],
  };
}

function onExtract(frame: Frame): Record<string, unknown> {
  const abs = String(frame["path"] ?? "");
  let rel = relative(session.root, abs).split("\\").join("/");
  if (!rel || rel.startsWith("..")) rel = abs.split("\\").join("/");

  let source: string;
  try {
    // **Newlines are normalised, and that is the host's contract rather than taste.**
    // The host hashes what `Path.read_text` gave it, and Python reads text files with
    // universal newlines on: `\r\n` and a lone `\r` both arrive as `\n`. `readFileSync`
    // does not, so a CRLF file hashes differently on the two sides — every one of them,
    // and the host's echo check then reports the file as having *changed while it was
    // being read*. Measured on uigen: 2 of 54 files, both generated with CRLF, both
    // reported unreadable in a map that was otherwise perfect. See
    // `ingest/contract.py:SOURCE_TEXT`.
    source = readFileSync(abs, "utf8").replace(/\r\n?/g, "\n");
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
    facts = extractFile(rel, source, session.rules);
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
      send({ t: "closed", id });
      rl.close();
      process.exit(0);
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
