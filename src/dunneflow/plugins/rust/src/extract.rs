//! One file's facts. Chunk 1 of the Rust reader: the file parses or it says why, and its
//! module scope is named the way every other reader names one. Routines, calls,
//! boundaries and the rest arrive in chunk 2.

use crate::facts::{FileFacts, Routine};
use crate::ids::{definition_id, hash_source};
use crate::rules::Rules;

pub const MODULE_SCOPE: &str = "<module>";

/// `src/net/mod.rs` -> `src.net.mod`. The file's own dotted path, as Go's `moduleName`,
/// so `probe.rs` is module `probe` beside `probe.go` and `probe.py` (`test_identity`).
pub fn module_name(rel: &str) -> String {
    let stem = rel.strip_suffix(".rs").unwrap_or(rel);
    stem.split('/').filter(|p| !p.is_empty()).collect::<Vec<_>>().join(".")
}

pub fn extract_file(rel: &str, source: &str, _rules: &Rules) -> FileFacts {
    let mut ff = FileFacts {
        path: rel.to_owned(),
        lang: crate::LANG.to_owned(),
        module: module_name(rel),
        content_hash: hash_source(source),
        ..Default::default()
    };
    match syn::parse_file(source) {
        Ok(_file) => {}
        Err(e) => {
            // A parse error is a fact about the file, never a failure of the reader: the
            // host records it and the rest of the tree is read.
            let at = e.span().start();
            ff.errors.push(format!("{}:{} {}", at.line, at.column + 1, e));
            return ff;
        }
    }
    ff.module_scope = Some(module_scope(rel, &ff.module, source));
    ff
}

/// The module scope: what a string or a call at the top of a file belongs to. Always sent,
/// claimed or not, because a string names its owner before anybody knows whether it is a
/// fact (rule 96, `extract.ts:moduleScope`).
pub fn module_scope(rel: &str, module: &str, source: &str) -> Routine {
    let qual = format!("{module}.{MODULE_SCOPE}");
    let lines = source.matches('\n').count().max(1) as i64;
    Routine {
        id: definition_id(rel, &qual, 1),
        name: MODULE_SCOPE.to_owned(),
        qualname: qual,
        module: module.to_owned(),
        file: rel.to_owned(),
        line_start: 1,
        line_end: lines,
        docstring: Some("Items at crate or module level: statics, consts and attributes.".into()),
        body_hash: hash_source(source),
        ..Default::default()
    }
}
