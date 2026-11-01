//! `ingest.contract.SOURCE_TEXT`: what "the text of a file" means, on both sides.
//!
//! Python reads with `errors="replace"` and universal newlines, so a CRLF file and a file
//! with stray bytes hash the same here as there, or come back *changed while it was being
//! read*. `String::from_utf8_lossy` replaces once per **maximal subpart**, which is
//! Python's rule and not Go's convenience functions' — the one thing `text.go` had to
//! write by hand — and `tests/fixtures/ids/vectors.json` is what says so rather than this
//! comment.

use std::path::Path;

pub fn decode(raw: &[u8]) -> String {
    let text = String::from_utf8_lossy(raw);
    if !text.contains('\r') {
        return text.into_owned();
    }
    text.replace("\r\n", "\n").replace('\r', "\n")
}

pub fn read_source(path: &Path) -> std::io::Result<String> {
    std::fs::read(path).map(|raw| decode(&raw))
}
