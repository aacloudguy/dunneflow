// Rust's sixth of the probe tree: a way in, a boundary, a loop and a branch.

use std::env;
use std::fs;

const RETRIES: u32 = 3;

/// One line of a config file.
pub struct Setting {
    pub key: String,
    pub value: String,
}

/// Reads a config file, one line at a time.
fn load_config(path: &str) -> Vec<Setting> {
    let mut out = Vec::new();
    let Ok(text) = fs::read_to_string(path) else {
        return out;
    };
    for line in text.lines() {
        if let Some((key, value)) = line.split_once('=') {
            out.push(Setting { key: key.trim().to_owned(), value: value.trim().to_owned() });
        }
    }
    out
}

fn root() -> String {
    match env::var("PROBE_ROOT") {
        Ok(r) if !r.is_empty() => r,
        _ => ".".to_owned(),
    }
}

fn main() {
    let settings = load_config(&format!("{}/probe.cfg", root()));
    println!("{} settings, {} retries", settings.len(), RETRIES);
}
