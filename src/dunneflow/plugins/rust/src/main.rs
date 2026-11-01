//! The Rust reader, on the far side of a pipe.
//!
//! `plugins/go/main.go` is the worked example this follows, and the two agree on every
//! rule that matters:
//!
//! **stdout carries protocol and nothing else.** Every diagnostic goes to stderr, which
//! the host drains into a ring buffer and never parses. A stray `println!` here is a frame
//! the host cannot read, and it refuses the language once and loudly rather than skipping
//! six hundred files quietly — so this file is the only one that writes to stdout, and it
//! writes only through `send`.
//!
//! **Every reply echoes the request's `id`.** The host correlates on it.
//!
//! **A file that will not parse is `facts` with an error, and a file that made this reader
//! panic is `failed`**: two different facts, and only the second lets the host write the
//! record, because a reader that has just crashed on a file is not the right authority on
//! what that file is.

mod cfg;
mod comments;
mod edges;
mod extract;
mod facts;
mod ids;
mod json;
mod rules;
mod text;
mod types;

use json::{Frame, Value};
use std::io::{BufRead, Write};
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};

const PROTOCOL: i64 = 1;
const LANG: &str = "rust";
/// `plugin.json`'s, and the handshake refuses the language if they differ.
const VERSION: &str = "0.1.0";

struct Reader {
    out: std::io::BufWriter<std::io::Stdout>,
    root: PathBuf,
    files: Vec<PathBuf>,
    rules: rules::Rules,
}

/// The other channel: evidence, never a control signal.
pub fn note(msg: &str) {
    eprintln!("{msg}");
}

impl Reader {
    fn send(&mut self, frame: String) {
        // One write and one flush per frame: the host reads lines, and half a line is a
        // frame it cannot read.
        let mut line = frame;
        line.push('\n');
        if self.out.write_all(line.as_bytes()).and_then(|_| self.out.flush()).is_err() {
            std::process::exit(0); // the host has gone; there is nobody left to answer
        }
    }

    fn hello(&self) -> Frame {
        let mut f = Frame::new("ready");
        f.put("lang", LANG).put("version", VERSION).put("protocol", &PROTOCOL)
            .put("schema_version", &facts::SCHEMA_VERSION);
        let caps = Value::Obj(vec![
            ("supplies_edges".into(), Value::Bool(true)),
            ("reports_literals".into(), Value::Bool(true)),
        ]);
        f.put("capabilities", &caps);
        f
    }

    fn open(&mut self, v: &Value) -> Frame {
        let root = v.get("root").and_then(Value::as_str).unwrap_or(".");
        // Absolute, because every path this reader is asked about is made absolute before
        // it is related to the root (`main.go`'s finding, rule 60).
        self.root = std::path::absolute(root).unwrap_or_else(|_| PathBuf::from(root));
        self.files = v.get("files").map(Value::strings).unwrap_or_default()
            .into_iter().map(PathBuf::from).collect();
        self.rules = rules::Rules::parse(v.get("rules"));
        let mut diagnostics: Vec<String> = Vec::new();
        if self.rules.boundaries.is_empty() {
            // Not an error and not silent: a run with no rules is a map with no
            // boundaries, which looks exactly like a program that touches nothing (rule 49).
            note("no boundary rules arrived with this session; the map will report none");
            diagnostics.push("no boundary rules arrived with this session".into());
        }
        let mut f = Frame::new("opened");
        f.put("files", &self.files.len()).put("diagnostics", &diagnostics);
        f
    }

    /// The stored spelling of a path: relative to the analysed root, with forward slashes
    /// on every platform (rule 93).
    fn rel_path(&self, abs: &Path) -> String {
        match abs.strip_prefix(&self.root) {
            Ok(rel) if !rel.as_os_str().is_empty() => slashed(rel),
            _ => slashed(abs),
        }
    }

    fn extract(&mut self, v: &Value) -> Frame {
        let path = v.get("path").and_then(Value::as_str).unwrap_or("");
        let abs = std::path::absolute(path).unwrap_or_else(|_| PathBuf::from(path));
        let source = match text::read_source(&abs) {
            Ok(s) => s,
            Err(e) => {
                // Nothing was read badly; nothing was read. A reader may describe that.
                let mut f = Frame::new("failed");
                f.put("reason", &format!("could not be read: {e}"));
                return f;
            }
        };
        let rel = self.rel_path(&abs);
        let rules = &self.rules;
        match panic::catch_unwind(AssertUnwindSafe(|| extract::extract_file(&rel, &source, rules))) {
            Ok(facts) => {
                let mut f = Frame::new("facts");
                // Echoed rather than assumed: the hash of what was actually read.
                f.put("hash", &ids::hash_source(&source)).put("facts", &facts);
                f
            }
            Err(p) => {
                let mut f = Frame::new("failed");
                f.put("reason", &panic_text(&p));
                f
            }
        }
    }

    /// Every call's far end, one frame each: a crate's answer is tens of thousands of them,
    /// and one line holding all of them has no bound.
    fn edges(&mut self, id: &Value) {
        let found = edges::collect(&self.root, &self.files, &self.rules);
        let mut supplied = 0usize;
        for e in &found.edges {
            if !e.file.is_empty() {
                supplied += 1;
            }
            let mut f = Frame::new("edge");
            f.put("id", id).put("edge", e);
            self.send(f.finish());
        }
        for n in &found.notes {
            note(n);
        }
        let mut f = Frame::new("edges_done");
        f.put("id", id).put("supplied", &supplied)
            .put("unresolved", &(found.outside + found.unknown))
            .put("outside", &found.outside).put("unknown", &found.unknown);
        self.send(f.finish());
    }

    fn handle(&mut self, line: &str) {
        let v = match json::parse(line) {
            Ok(v) => v,
            Err(e) => {
                note(&format!("unreadable frame ({e}): {:.120}", line));
                return;
            }
        };
        let id = v.get("id").cloned().unwrap_or(Value::Null);
        let t = v.get("t").and_then(Value::as_str).unwrap_or("").to_owned();
        let reply = panic::catch_unwind(AssertUnwindSafe(|| -> Option<Frame> {
            match t.as_str() {
                "close" => None,
                "edges" => {
                    self.edges(&id);
                    None
                }
                "hello" => Some(self.hello()),
                "open" => Some(self.open(&v)),
                "extract" => Some(self.extract(&v)),
                other => {
                    let mut f = Frame::new("error");
                    f.put("reason", &format!("unknown frame {other}"));
                    Some(f)
                }
            }
        }));
        match reply {
            Ok(Some(mut f)) => {
                f.put("id", &id);
                self.send(f.finish());
            }
            Ok(None) if t == "close" => {
                let mut f = Frame::new("closed");
                f.put("id", &id);
                self.send(f.finish());
                std::process::exit(0);
            }
            Ok(None) => {}
            Err(p) => {
                let mut f = Frame::new("error");
                f.put("id", &id).put("reason", &panic_text(&p));
                self.send(f.finish());
            }
        }
    }
}

fn slashed(p: &Path) -> String {
    p.to_string_lossy().replace('\\', "/")
}

fn panic_text(p: &Box<dyn std::any::Any + Send>) -> String {
    if let Some(s) = p.downcast_ref::<&str>() {
        (*s).to_owned()
    } else if let Some(s) = p.downcast_ref::<String>() {
        s.clone()
    } else {
        "the reader panicked".into()
    }
}

fn main() {
    // A panic's default message goes to stderr, which is the right channel; it is kept,
    // and the frame that answers it is sent from `handle`.
    let mut r = Reader {
        out: std::io::BufWriter::new(std::io::stdout()),
        root: PathBuf::from("."),
        files: Vec::new(),
        rules: rules::Rules::default(),
    };
    let stdin = std::io::stdin();
    let mut input = stdin.lock();
    let mut buf = Vec::new();
    loop {
        buf.clear();
        match input.read_until(b'\n', &mut buf) {
            Ok(0) => return,
            Ok(_) => {
                let line = String::from_utf8_lossy(&buf);
                if !line.trim().is_empty() {
                    r.handle(line.trim_end());
                }
            }
            Err(e) => {
                note(&format!("stdin: {e}"));
                return;
            }
        }
    }
}
