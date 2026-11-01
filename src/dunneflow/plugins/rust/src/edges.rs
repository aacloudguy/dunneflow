//! Every call's far end, by path, inside the program. Chunk 3 of the Rust reader; until
//! then it answers that it resolved nothing, which the host counts and says.

use crate::facts::SuppliedEdge;
use crate::rules::Rules;
use std::path::{Path, PathBuf};

#[derive(Default)]
pub struct Found {
    pub edges: Vec<SuppliedEdge>,
    pub notes: Vec<String>,
    pub outside: usize,
    pub unknown: usize,
}

pub fn collect(_root: &Path, _files: &[PathBuf], _rules: &Rules) -> Found {
    Found::default()
}
