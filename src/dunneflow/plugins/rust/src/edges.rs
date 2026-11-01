//! Every call's far end, by path, inside the program.
//!
//! **This is not a type checker and does not pretend to be one.** Go's reader asks
//! `go/types`; nothing comparable ships with Rust (rust-analyzer needs every dependency
//! downloaded and its build scripts run, and was declined for that). What a path can say
//! without types is said here, and what it cannot is counted and never guessed (rule 1):
//!
//! | the call | the answer |
//! |---|---|
//! | `f()`, `a::b::f()`, `crate::`/`self::`/`super::` paths, a `use` (renamed, globbed, re-exported) | the `fn` that path names |
//! | `Type::f()`, `Self::f()` | `Type`'s method of that name — inherent first, else the one trait impl that has it |
//! | `self.m()` in an `impl` | the same, for the `impl`'s own type |
//! | `self.m()` in a trait's default body, or a trait method with several impls | **ambiguous**: `candidates` is how many could answer |
//! | `x.m()` on any other value | **unknown** where the program defines a method `m`, **outside** where it defines none |
//! | `std::`, `core::`, another crate, a macro | **outside** |
//!
//! **One reference target, as Go's.** A definition per platform is drawn to its
//! linux/x86_64 one (Tom's decision for Go, 2026-11-01): a `mod` or a `use` whose `#[cfg]`
//! is false there is not followed, and a function defined once per platform in one module
//! resolves to the variant that is true there. An unknown predicate — a `feature`, say —
//! keeps its item, and two kept items are ambiguous rather than a coin toss.
//!
//! **The walk is the extractor's** (`extract::extract`), so a call has the same `site_id`
//! here as in its facts and the two passes cannot disagree about which call is which.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::{Path, PathBuf};

use crate::cfg::Tri;
use crate::extract::{self, Def, Extracted, SiteKind};
use crate::facts::SuppliedEdge;
use crate::rules::Rules;
use crate::text;

#[derive(Default)]
pub struct Found {
    pub edges: Vec<SuppliedEdge>,
    pub notes: Vec<String>,
    pub outside: usize,
    pub unknown: usize,
}

const HOW: &str = "rust path";

struct FileUnit {
    rel: String,
    abs: PathBuf,
    ex: Extracted,
    /// `(crate, module path)` once placed in a crate's tree.
    at: Option<(usize, Vec<String>)>,
}

struct Crate {
    /// The package directory the crate's root is in, if it is in one.
    #[allow(dead_code)]
    package: Option<PathBuf>,
}

/// A definition, by file and index into that file's `defs`.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct DefRef(usize, usize);

#[derive(Clone)]
enum Res {
    Fns(Vec<DefRef>),
    Module(usize, Vec<String>),
    Type(usize, String),
    Outside,
    Unknown,
}

struct Program {
    files: Vec<FileUnit>,
    crates: Vec<Crate>,
    /// crate name (with `-` read as `_`) -> its library crate.
    by_name: HashMap<String, usize>,
    /// `(crate, module)` -> the files and inline modules it is made of.
    modules: HashSet<(usize, Vec<String>)>,
    /// Modules a `#[cfg]` false on the reference target leaves out.
    excluded: HashSet<(usize, Vec<String>)>,
    /// `(crate, module, name)` -> free functions.
    fns: HashMap<(usize, Vec<String>, String), Vec<DefRef>>,
    /// `(crate, type, method)` -> methods.
    methods: HashMap<(usize, String, String), Vec<DefRef>>,
    /// `(crate, type)` names that carry a method or are declared.
    types: HashSet<(usize, String)>,
    traits: HashSet<(usize, String)>,
    /// `(crate, module, local)` -> `(module the use is in, target)`.
    uses: HashMap<(usize, Vec<String>, String), Vec<Vec<String>>>,
    globs: HashMap<(usize, Vec<String>), Vec<Vec<String>>>,
    /// Method names the program defines anywhere.
    method_names: HashSet<String>,
    fn_names: HashSet<String>,
}

pub fn collect(root: &Path, files: &[PathBuf], rules: &Rules) -> Found {
    let mut found = Found::default();
    let mut units = Vec::new();
    for abs in files {
        let abs = std::path::absolute(abs).unwrap_or_else(|_| abs.clone());
        let Ok(src) = text::read_source(&abs) else { continue };
        let rel = match abs.strip_prefix(root) {
            Ok(r) => r.to_string_lossy().replace('\\', "/"),
            Err(_) => abs.to_string_lossy().replace('\\', "/"),
        };
        let ex = extract::extract(&rel, &src, rules);
        units.push(FileUnit { rel, abs, ex, at: None });
    }
    let mut prog = Program::build(root, units, &mut found);
    prog.resolve_all(&mut found);
    found
}

// ------------------------------------------------------------------ crates --- //

/// `[package] name`, `[lib] path` and every `[[bin]] path`, read by a line scanner rather
/// than a TOML parser, which would be a vendored crate for three keys. What it does not
/// read: a name or path written as an inline table, or continued over lines.
struct Manifest {
    name: Option<String>,
    lib: Option<String>,
    bins: Vec<String>,
}

fn read_manifest(path: &Path) -> Option<Manifest> {
    let text = std::fs::read_to_string(path).ok()?;
    let mut m = Manifest { name: None, lib: None, bins: Vec::new() };
    let mut section = String::new();
    for raw in text.lines() {
        let line = raw.split('#').next().unwrap_or("").trim();
        if line.starts_with('[') {
            section = line.trim_matches(|c| c == '[' || c == ']').trim().to_owned();
            continue;
        }
        let Some((k, v)) = line.split_once('=') else { continue };
        let v = v.trim();
        if !(v.starts_with('"') && v.ends_with('"') && v.len() >= 2) {
            continue;
        }
        let v = v[1..v.len() - 1].to_owned();
        match (section.as_str(), k.trim()) {
            ("package", "name") => m.name = Some(v),
            ("lib", "path") => m.lib = Some(v),
            ("bin", "path") => m.bins.push(v),
            _ => {}
        }
    }
    m.name.as_ref()?;
    Some(m)
}

impl Program {
    fn build(root: &Path, files: Vec<FileUnit>, found: &mut Found) -> Program {
        let mut prog = Program {
            files,
            crates: Vec::new(),
            by_name: HashMap::new(),
            modules: HashSet::new(),
            excluded: HashSet::new(),
            fns: HashMap::new(),
            methods: HashMap::new(),
            types: HashSet::new(),
            traits: HashSet::new(),
            uses: HashMap::new(),
            globs: HashMap::new(),
            method_names: HashSet::new(),
            fn_names: HashSet::new(),
        };
        let by_abs: HashMap<PathBuf, usize> =
            prog.files.iter().enumerate().map(|(i, f)| (f.abs.clone(), i)).collect();

        // Every package a file belongs to, and its crate roots.
        let mut packages: BTreeMap<PathBuf, Manifest> = BTreeMap::new();
        for f in &prog.files {
            let mut dir = f.abs.parent();
            while let Some(d) = dir {
                if !d.starts_with(root) {
                    break;
                }
                if packages.contains_key(d) {
                    break;
                }
                if let Some(m) = read_manifest(&d.join("Cargo.toml")) {
                    packages.insert(d.to_path_buf(), m);
                    break;
                }
                dir = d.parent();
            }
        }
        let mut roots: Vec<(usize, Option<PathBuf>, bool)> = Vec::new(); // file, package, is lib
        for (dir, m) in &packages {
            let lib = dir.join(m.lib.as_deref().unwrap_or("src/lib.rs"));
            if let Some(&i) = by_abs.get(&lib) {
                roots.push((i, Some(dir.clone()), true));
            }
            let mut bins: Vec<PathBuf> = m.bins.iter().map(|b| dir.join(b)).collect();
            bins.push(dir.join("src/main.rs"));
            bins.push(dir.join("build.rs"));
            // Cargo's own target conventions: each of these files is a crate root.
            for f in &prog.files {
                let Ok(rel) = f.abs.strip_prefix(dir) else { continue };
                let parts: Vec<String> = rel.iter().map(|p| p.to_string_lossy().into_owned()).collect();
                let p: Vec<&str> = parts.iter().map(String::as_str).collect();
                let conventional = matches!(p.as_slice(), ["examples" | "tests" | "benches", _])
                    || matches!(p.as_slice(), ["src", "bin", _])
                    || matches!(p.as_slice(), ["src", "bin", _, "main.rs"]);
                if conventional {
                    bins.push(f.abs.clone());
                }
            }
            for b in bins {
                if let Some(&i) = by_abs.get(&b) {
                    if !roots.iter().any(|(r, _, _)| *r == i) {
                        roots.push((i, Some(dir.clone()), false));
                    }
                }
            }
        }

        // Each root's module tree, through `mod x;`.
        let mut declared: HashSet<usize> = HashSet::new();
        for (file, pkg, is_lib) in roots.clone() {
            if prog.files[file].at.is_some() {
                continue;
            }
            let c = prog.crates.len();
            prog.crates.push(Crate { package: pkg.clone() });
            if is_lib {
                if let Some(m) = pkg.as_ref().and_then(|p| packages.get(p)) {
                    if let Some(n) = &m.name {
                        prog.by_name.insert(n.replace('-', "_"), c);
                    }
                }
            }
            prog.place(file, c, Vec::new(), true, &by_abs, &mut declared);
        }
        // A file nobody declares is a crate of its own. One a `cfg` leaves out is not.
        let mut orphans = 0;
        for i in 0..prog.files.len() {
            if prog.files[i].at.is_none() && !declared.contains(&i) {
                let pkg = packages.keys().filter(|d| prog.files[i].abs.starts_with(d)).max_by_key(|d| d.as_os_str().len()).cloned();
                let c = prog.crates.len();
                prog.crates.push(Crate { package: pkg });
                prog.place(i, c, Vec::new(), true, &by_abs, &mut declared);
                orphans += 1;
            }
        }
        if orphans > 0 {
            found.notes.push(format!(
                "{orphans} .rs file(s) are no crate's module and are read as crates of their own"
            ));
        }
        prog.index();
        prog
    }

    /// Put a file in its crate at `module`, and everything it declares under it.
    fn place(&mut self, file: usize, c: usize, module: Vec<String>, is_root: bool,
             by_abs: &HashMap<PathBuf, usize>, declared: &mut HashSet<usize>) {
        if self.files[file].at.is_some() {
            return;
        }
        self.files[file].at = Some((c, module.clone()));
        self.modules.insert((c, module.clone()));
        let abs = self.files[file].abs.clone();
        let parent = abs.parent().map(Path::to_path_buf).unwrap_or_default();
        let stem = abs.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
        let mod_rs = is_root || matches!(stem.as_str(), "mod" | "lib" | "main");
        let base = if mod_rs { parent.clone() } else { parent.join(&stem) };
        let mods = self.files[file].ex.mods.clone();
        for m in mods {
            let mut full = module.clone();
            full.extend(m.mod_path.iter().cloned());
            full.push(m.name.clone());
            self.modules.insert((c, full.clone()));
            if m.reference == Tri::False {
                self.excluded.insert((c, full.clone()));
            }
            if m.inline {
                continue;
            }
            let mut dir = base.clone();
            for seg in &m.mod_path {
                dir.push(seg);
            }
            let candidates = match &m.path_attr {
                Some(p) => vec![if m.mod_path.is_empty() { parent.join(p) } else { dir.join(p) }],
                None => vec![dir.join(format!("{}.rs", m.name)), dir.join(&m.name).join("mod.rs")],
            };
            for cand in candidates {
                let cand = normalise(&cand);
                if let Some(&child) = by_abs.get(&cand) {
                    declared.insert(child);
                    self.place(child, c, full.clone(), false, by_abs, declared);
                    break;
                }
            }
        }
    }

    fn index(&mut self) {
        for (fi, f) in self.files.iter().enumerate() {
            let Some((c, module)) = &f.at else { continue };
            for m in &f.ex.mods {
                if m.inline {
                    let mut full = module.clone();
                    full.extend(m.mod_path.iter().cloned());
                    full.push(m.name.clone());
                    self.modules.insert((*c, full));
                }
            }
            for (di, d) in f.ex.defs.iter().enumerate() {
                let mut full = module.clone();
                full.extend(d.mod_path.iter().cloned());
                let r = DefRef(fi, di);
                match &d.owner {
                    None => {
                        self.fns.entry((*c, full, d.name.clone())).or_default().push(r);
                        self.fn_names.insert(d.name.clone());
                    }
                    Some(t) => {
                        self.methods.entry((*c, t.clone(), d.name.clone())).or_default().push(r);
                        self.types.insert((*c, t.clone()));
                        self.method_names.insert(d.name.clone());
                        if d.trait_name.as_deref() == Some(t.as_str()) {
                            self.traits.insert((*c, t.clone()));
                        }
                    }
                }
            }
            for (t, tr) in &f.ex.impls {
                self.types.insert((*c, t.clone()));
                if let Some(tr) = tr {
                    self.traits.insert((*c, tr.clone()));
                }
            }
            for s in &f.ex.facts.structures {
                self.types.insert((*c, s.name.clone()));
                if s.kind.as_str() == "INTERFACE" {
                    self.traits.insert((*c, s.name.clone()));
                }
            }
            for u in &f.ex.uses {
                if u.reference == Tri::False {
                    continue;
                }
                let mut at = module.clone();
                at.extend(u.mod_path.iter().cloned());
                if u.local == "*" {
                    self.globs.entry((*c, at)).or_default().push(u.target.clone());
                } else {
                    self.uses.entry((*c, at, u.local.clone())).or_default().push(u.target.clone());
                }
            }
        }
    }

    // ---------------------------------------------------------------- paths --- //

    /// What `segs` names, written in module `module` of crate `c`.
    fn resolve_path(&self, c: usize, module: &[String], self_type: Option<&str>, segs: &[String],
                    depth: usize) -> Res {
        if segs.is_empty() || depth > 12 {
            return Res::Unknown;
        }
        let (mut cur, rest) = match segs[0].as_str() {
            "crate" => (Res::Module(c, Vec::new()), &segs[1..]),
            "self" => (Res::Module(c, module.to_vec()), &segs[1..]),
            "super" => {
                let mut m = module.to_vec();
                let mut i = 0;
                while i < segs.len() && segs[i] == "super" {
                    if m.pop().is_none() {
                        return Res::Unknown;
                    }
                    i += 1;
                }
                (Res::Module(c, m), &segs[i..])
            }
            "Self" => match self_type {
                Some(t) => (Res::Type(c, t.to_owned()), &segs[1..]),
                None => return Res::Unknown,
            },
            "std" | "core" | "alloc" => return Res::Outside,
            first => {
                let r = self.lookup(c, module, first, depth);
                match r {
                    Res::Unknown if segs.len() > 1 => {
                        // A path whose first segment is nothing of this program's — a
                        // crate it depends on — goes outside it.
                        return Res::Outside;
                    }
                    Res::Unknown => {
                        // A bare name nothing here declares: the prelude, a glob from a
                        // dependency, or a name this resolver could not follow. Outside
                        // only where no function of that name exists anywhere in the
                        // program; otherwise it is ours and unnamed.
                        return if self.fn_names.contains(first) { Res::Unknown } else { Res::Outside };
                    }
                    other => (other, &segs[1..]),
                }
            }
        };
        for (i, seg) in rest.iter().enumerate() {
            let last = i == rest.len() - 1;
            cur = match cur {
                Res::Module(mc, m) => {
                    if self.excluded.contains(&(mc, m.clone())) {
                        return Res::Unknown;
                    }
                    match self.lookup(mc, &m, seg, depth) {
                        Res::Unknown => return Res::Unknown,
                        r => r,
                    }
                }
                Res::Type(tc, t) if last => return self.method(tc, &t, seg),
                Res::Outside => return Res::Outside,
                _ => return Res::Unknown,
            };
        }
        cur
    }

    /// One name in one module: its functions, its child modules, its types, its `use`s,
    /// its globs, and the crates the workspace names.
    fn lookup(&self, c: usize, module: &[String], name: &str, depth: usize) -> Res {
        if let Some(defs) = self.fns.get(&(c, module.to_vec(), name.to_owned())) {
            return Res::Fns(defs.clone());
        }
        let mut child = module.to_vec();
        child.push(name.to_owned());
        if self.modules.contains(&(c, child.clone())) {
            return Res::Module(c, child);
        }
        if let Some(targets) = self.uses.get(&(c, module.to_vec(), name.to_owned())) {
            // Two `use`s of one name in one module are two `cfg` arms whose predicates
            // this resolver could not decide; the first that resolves is not an answer.
            let got: Vec<Res> = targets.iter()
                .map(|t| self.resolve_path(c, module, None, t, depth + 1))
                .filter(|r| !matches!(r, Res::Unknown))
                .collect();
            return match got.len() {
                0 => Res::Unknown,
                1 => got.into_iter().next().unwrap(),
                _ => Res::Unknown,
            };
        }
        if self.types.contains(&(c, name.to_owned())) && name.chars().next().is_some_and(char::is_uppercase) {
            return Res::Type(c, name.to_owned());
        }
        if let Some(globs) = self.globs.get(&(c, module.to_vec())) {
            for g in globs {
                if let Res::Module(gc, gm) = self.resolve_path(c, module, None, g, depth + 1) {
                    if (gc, gm.as_slice()) != (c, module) {
                        match self.lookup(gc, &gm, name, depth + 1) {
                            Res::Unknown => {}
                            r => return r,
                        }
                    }
                }
            }
        }
        if let Some(&lib) = self.by_name.get(name) {
            return Res::Module(lib, Vec::new());
        }
        Res::Unknown
    }

    /// `Type::m`: inherent first, else the one trait impl that has it.
    fn method(&self, c: usize, ty: &str, name: &str) -> Res {
        let Some(all) = self.methods.get(&(c, ty.to_owned(), name.to_owned())) else {
            // Derived, blanket or from a trait this program did not write.
            return Res::Outside;
        };
        let pick = |want_trait: bool| -> Vec<DefRef> {
            all.iter().copied().filter(|r| self.def(*r).trait_name.is_some() == want_trait).collect()
        };
        let inherent = pick(false);
        if !inherent.is_empty() {
            return Res::Fns(inherent);
        }
        Res::Fns(pick(true))
    }

    fn def(&self, r: DefRef) -> &Def {
        &self.files[r.0].ex.defs[r.1]
    }

    // ------------------------------------------------------------- resolving --- //

    fn resolve_all(&mut self, found: &mut Found) {
        let mut edges = Vec::new();
        for f in &self.files {
            let Some((c, module)) = &f.at else {
                found.unknown += f.ex.sites.len();
                continue;
            };
            for s in &f.ex.sites {
                if s.at_boundary {
                    continue; // rule 2: the host makes it external whatever is said here
                }
                if s.bound_locally {
                    found.unknown += 1; // a closure or a pointer: which one is a type's question
                    continue;
                }
                let mut at = module.clone();
                at.extend(s.mod_path.iter().cloned());
                let res = match s.kind {
                    SiteKind::Macro => Res::Outside,
                    SiteKind::Path => self.resolve_path(*c, &at, s.self_type.as_deref(), &s.path, 0),
                    SiteKind::SelfMethod => match &s.self_type {
                        Some(t) if self.traits.contains(&(*c, t.clone())) => {
                            // A trait's default body: `self` is whichever type implements
                            // it, and that is not something a path can say.
                            let n = self.implementors(*c, t, &s.path[0]);
                            found.unknown += 1;
                            edges.push(ambiguous(s, n.max(2)));
                            continue;
                        }
                        Some(t) => self.method(*c, t, &s.path[0]),
                        None => Res::Unknown,
                    },
                    SiteKind::Method => {
                        if self.method_names.contains(&s.path[0]) { Res::Unknown } else { Res::Outside }
                    }
                };
                match res {
                    Res::Fns(defs) => {
                        let kept: Vec<DefRef> = defs.iter().copied()
                            .filter(|r| self.def(*r).reference != Tri::False).collect();
                        match kept.len() {
                            1 => {
                                let d = self.def(kept[0]);
                                let how = if defs.len() > 1 {
                                    format!("{HOW}; the linux/x86_64 one of {} cfg variants", defs.len())
                                } else {
                                    HOW.to_owned()
                                };
                                edges.push(SuppliedEdge {
                                    site_id: s.site_id.clone(),
                                    caller_id: s.caller_id.clone(),
                                    file: self.files[kept[0].0].rel.clone(),
                                    line: d.line,
                                    name: d.name.clone(),
                                    how,
                                    candidates: 0,
                                });
                            }
                            0 => found.unknown += 1,
                            n => {
                                found.unknown += 1;
                                edges.push(ambiguous(s, n as i64));
                            }
                        }
                    }
                    Res::Outside => found.outside += 1,
                    Res::Module(..) | Res::Type(..) | Res::Unknown => found.unknown += 1,
                }
            }
        }
        found.edges = edges;
    }

    /// How many types in this crate could answer `self.m()` in trait `t`'s default body.
    fn implementors(&self, c: usize, t: &str, m: &str) -> i64 {
        let mut n = 0;
        for ((mc, _, name), defs) in &self.methods {
            if *mc == c && name == m {
                n += defs.iter().filter(|r| self.def(**r).trait_name.as_deref() == Some(t)).count();
            }
        }
        n as i64
    }
}

fn ambiguous(s: &extract::Site, n: i64) -> SuppliedEdge {
    SuppliedEdge {
        site_id: s.site_id.clone(),
        caller_id: s.caller_id.clone(),
        how: HOW.to_owned(),
        candidates: n,
        ..Default::default()
    }
}

/// `a/./b/../c` -> `a/c`, without touching the disk.
fn normalise(p: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for comp in p.components() {
        match comp {
            std::path::Component::CurDir => {}
            std::path::Component::ParentDir => {
                out.pop();
            }
            other => out.push(other),
        }
    }
    out
}
