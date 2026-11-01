//! A program's direct dependencies, read from this machine's cargo cache where they are
//! already there — and never fetched (design rule 14).
//!
//! **What this is for: the frontier, not the map.** A call into `rusqlite` stays a call
//! outside this program; what reading rusqlite's source adds is *which* definition it
//! reaches (`rusqlite::transaction::Transaction::execute`, confirmed rather than spelt) and
//! the type that definition declares it returns, so a receiver bound from it
//! (`let stmt = conn.prepare(..)?`) has a type and its own calls can be named too.
//!
//! **Pinned by `Cargo.lock`, and only by it.** A dependency is read at the one version the
//! lock names, from `$CARGO_HOME/registry/src/*/<name>-<version>/` (`~/.cargo` when the
//! variable is not set). Two locked versions of one name, a dependency from git or a path,
//! and one the cache does not hold are each *not read*, and each is said: a frontier read
//! against the wrong version would be a confident answer about somebody else's code.
//!
//! **Direct dependencies only**, and a bound on the files read: a type a dependency takes
//! from its own dependency stays a spelt frontier, and the residue says how many crates
//! were read and which were not.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

pub struct Dep {
    /// The name the crate calls itself (`[package] name`), as code spells it.
    pub name: String,
    pub version: String,
    pub dir: PathBuf,
    /// Every name the program's manifests depend on it by (`foo = { package = "bar" }`).
    pub aliases: BTreeSet<String>,
}

#[derive(Default)]
pub struct Found {
    pub deps: Vec<Dep>,
    /// `name version` (or `name`) of each dependency that was not read, with why.
    pub missing: Vec<String>,
}

/// Every direct `[dependencies]` entry of the manifests under `packages`: local name to the
/// package's real name.
fn direct(packages: &[PathBuf]) -> BTreeMap<String, String> {
    let mut out = BTreeMap::new();
    for dir in packages {
        let Ok(text) = std::fs::read_to_string(dir.join("Cargo.toml")) else { continue };
        let mut section = String::new();
        let mut table_dep: Option<String> = None;
        for raw in text.lines() {
            let line = raw.split('#').next().unwrap_or("").trim();
            if line.starts_with('[') {
                section = line.trim_matches(|c| c == '[' || c == ']').trim().to_owned();
                // `[dependencies.foo]` names one dependency as a table of its own.
                table_dep = ["dependencies.", "workspace.dependencies."].iter()
                    .find_map(|p| section.strip_prefix(p))
                    .or_else(|| section.split_once(".dependencies.").map(|(_, d)| d))
                    .map(|d| d.trim_matches('"').to_owned());
                if let Some(d) = &table_dep {
                    out.entry(d.clone()).or_insert_with(|| d.clone());
                }
                continue;
            }
            let in_deps = section == "dependencies" || section == "workspace.dependencies"
                || (section.starts_with("target.") && section.ends_with(".dependencies"));
            let Some((k, v)) = line.split_once('=') else { continue };
            if let Some(d) = &table_dep {
                if k.trim() == "package" {
                    out.insert(d.clone(), v.trim().trim_matches('"').to_owned());
                }
                continue;
            }
            if !in_deps {
                continue;
            }
            // `foo.workspace = true` and `foo.version = "1"` are the dependency `foo`.
            let local = k.trim().split('.').next().unwrap_or("").trim_matches('"').to_owned();
            if local.is_empty() {
                continue;
            }
            let real = v.find("package").and_then(|i| {
                let rest = &v[i + "package".len()..];
                let rest = rest.trim_start().strip_prefix('=')?.trim_start().strip_prefix('"')?;
                rest.split('"').next().map(str::to_owned)
            }).unwrap_or_else(|| local.clone());
            out.insert(local, real);
        }
    }
    out
}

/// `name -> versions from a registry`, out of every `Cargo.lock` above the packages.
fn locked(root: &Path, packages: &[PathBuf]) -> BTreeMap<String, BTreeSet<String>> {
    let mut locks: BTreeSet<PathBuf> = BTreeSet::new();
    for dir in packages {
        let mut d = Some(dir.as_path());
        while let Some(x) = d {
            if x.join("Cargo.lock").is_file() {
                locks.insert(x.join("Cargo.lock"));
                break;
            }
            if x == root {
                break;
            }
            d = x.parent();
        }
    }
    let mut out: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for lock in locks {
        let Ok(text) = std::fs::read_to_string(&lock) else { continue };
        for block in text.split("[[package]]").skip(1) {
            let field = |k: &str| block.lines().find_map(|l| {
                let (a, b) = l.split_once('=')?;
                (a.trim() == k).then(|| b.trim().trim_matches('"').to_owned())
            });
            let (Some(name), Some(version)) = (field("name"), field("version")) else { continue };
            if field("source").is_some_and(|s| s.starts_with("registry+")) {
                out.entry(name).or_default().insert(version);
            }
        }
    }
    out
}

fn cargo_home() -> Option<PathBuf> {
    if let Some(h) = std::env::var_os("CARGO_HOME") {
        return Some(PathBuf::from(h));
    }
    let home = std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE"))?;
    Some(PathBuf::from(home).join(".cargo"))
}

pub fn find(root: &Path, packages: &[PathBuf]) -> Found {
    let mut found = Found::default();
    let wanted = direct(packages);
    if wanted.is_empty() {
        return found;
    }
    let lock = locked(root, packages);
    let caches: Vec<PathBuf> = cargo_home()
        .and_then(|h| std::fs::read_dir(h.join("registry").join("src")).ok())
        .map(|rd| rd.filter_map(|e| e.ok().map(|e| e.path())).filter(|p| p.is_dir()).collect())
        .unwrap_or_default();
    // Local names a workspace crate is called by are the workspace's own, not dependencies.
    let own: BTreeSet<String> = packages.iter().filter_map(|d| {
        std::fs::read_to_string(d.join("Cargo.toml")).ok().and_then(|t| {
            t.lines().skip_while(|l| l.trim() != "[package]").skip(1)
                .take_while(|l| !l.trim().starts_with('['))
                .find_map(|l| {
                    let (k, v) = l.split_once('=')?;
                    (k.trim() == "name").then(|| v.trim().trim_matches('"').to_owned())
                })
        })
    }).collect();
    let mut by_real: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for (local, real) in wanted {
        if own.contains(&real) {
            continue;
        }
        by_real.entry(real).or_default().insert(local);
    }
    for (real, aliases) in by_real {
        let versions = lock.get(&real).cloned().unwrap_or_default();
        let version = match versions.len() {
            1 => versions.into_iter().next().unwrap(),
            0 => {
                found.missing.push(format!("{real} (no registry version in Cargo.lock)"));
                continue;
            }
            _ => {
                found.missing.push(format!("{real} (locked at {} versions)", versions.len()));
                continue;
            }
        };
        let dir = caches.iter().map(|c| c.join(format!("{real}-{version}"))).find(|d| d.is_dir());
        match dir {
            Some(dir) => found.deps.push(Dep {
                name: real.replace('-', "_"),
                version,
                dir,
                aliases: aliases.into_iter().map(|a| a.replace('-', "_")).collect(),
            }),
            None => found.missing.push(format!("{real} {version} (not in this machine's cargo cache)")),
        }
    }
    found
}

/// The `.rs` files of a dependency's library, sorted, without its tests, benches and
/// examples, which no caller of it can reach.
pub fn files(dep: &Dep) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let mut stack = vec![dep.dir.join("src")];
    while let Some(d) = stack.pop() {
        let Ok(rd) = std::fs::read_dir(&d) else { continue };
        for e in rd.flatten() {
            let p = e.path();
            if p.is_dir() {
                stack.push(p);
            } else if p.extension().is_some_and(|x| x == "rs") {
                out.push(p);
            }
        }
    }
    out.sort();
    out
}
