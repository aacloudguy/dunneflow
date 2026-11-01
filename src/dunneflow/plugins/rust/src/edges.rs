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
use crate::types::Hint;
use crate::deps;
use crate::text;

#[derive(Default)]
pub struct Found {
    pub edges: Vec<SuppliedEdge>,
    pub notes: Vec<String>,
    pub outside: usize,
    pub unknown: usize,
    /// Dependencies whose source was read from this machine, `name version` each.
    pub read_beyond: Vec<String>,
    /// Dependencies that were not, each with why.
    pub not_present: Vec<String>,
    /// The program's files that only a `#[cfg(test)] mod x;` reaches: test code, which the
    /// host leaves out as it leaves out a test file. Sorted, relative.
    pub test_only: Vec<String>,
}

/// A bound on the dependency files read, so a program that depends on half of crates.io
/// costs a bounded walk; what it left unread is said (rule 55).
const DEP_FILE_BOUND: usize = 20_000;

const HOW: &str = "rust path";

struct FileUnit {
    rel: String,
    abs: PathBuf,
    ex: Extracted,
    /// `(crate, module path)` once placed in a crate's tree.
    at: Option<(usize, Vec<String>)>,
    /// Which dependency this file is the source of, for a file outside the program.
    dep: Option<usize>,
    /// Reached through a `#[cfg(test)] mod x;`, directly or from under one.
    test: bool,
}

struct Crate {
    /// The package directory the crate's root is in, if it is in one.
    #[allow(dead_code)]
    package: Option<PathBuf>,
    /// A dependency's crate, read for the frontier and never resolved or drawn.
    dep: Option<usize>,
}

/// `(crate, module, name, depth)`: one `lookup` question.
type MemoKey = (usize, Vec<String>, String, usize);

/// A definition, by file and index into that file's `defs`.
#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct DefRef(usize, usize);

#[derive(Clone)]
enum Res {
    Fns(Vec<DefRef>),
    /// Builds one of the program's own types: `(file, index into its types)`.
    Construct(usize, usize),
    Module(usize, Vec<String>),
    Type(usize, String),
    /// Not this program's: the path it went outside by, as far as it is known.
    Outside(String),
    Unknown,
}

/// Where a type or a definition is written, which is what its names are resolved in.
#[derive(Clone)]
struct Ctx {
    c: usize,
    module: Vec<String>,
    self_type: Option<String>,
}

/// What a receiver's declared type comes to.
enum TyRes {
    Local(usize, String),
    Trait(usize, String),
    Outside(String),
    /// A type parameter with no bound: no type is written down at all.
    Generic(String),
}

struct Program {
    memo: std::cell::RefCell<HashMap<MemoKey, Res>>,
    memo_on: std::cell::Cell<bool>,
    files: Vec<FileUnit>,
    /// `(name, version)` of each dependency read.
    deps: Vec<(String, String)>,
    crates: Vec<Crate>,
    /// crate name (with `-` read as `_`) -> its library crate.
    by_name: HashMap<String, usize>,
    /// `(crate, module)` -> the files and inline modules it is made of.
    modules: HashSet<(usize, Vec<String>)>,
    /// Modules a `#[cfg]` false on the reference target leaves out.
    excluded: HashSet<(usize, Vec<String>)>,
    /// `(crate, module, name)` -> free functions.
    fns: HashMap<(usize, Vec<String>, String), Vec<DefRef>>,
    /// `(enclosing routine id, name)` -> the functions a function body declares, which no
    /// module can see.
    local_fns: HashMap<(String, String), Vec<DefRef>>,
    /// `(crate, type key, method)` -> methods. A type key is `module::Name`, crate-relative.
    methods: HashMap<(usize, String, String), Vec<DefRef>>,
    traits: HashSet<(usize, String)>,
    /// Traits written without `pub`: every impl of one is in its own crate, so in this map.
    sealed: HashSet<(usize, String)>,
    /// `(crate, module, name)` -> the key of the type declared there under that name.
    declared: HashMap<(usize, Vec<String>, String), String>,
    /// `(crate, name)` -> every key of a type of that name, for the last-resort lookup.
    by_short: HashMap<(usize, String), Vec<String>>,
    /// A trait impl's method -> the trait's key.
    def_trait: HashMap<DefRef, (usize, String)>,
    /// `(crate, module, local)` -> `(module the use is in, target)`.
    uses: HashMap<(usize, Vec<String>, String), Vec<Vec<String>>>,
    globs: HashMap<(usize, Vec<String>), Vec<Vec<String>>>,
    /// Macro names the program defines with `macro_rules!`.
    macros: HashSet<String>,
    /// Method names the program defines anywhere.
    method_names: HashSet<String>,
    fn_names: HashSet<String>,
    /// `(crate, trait key)` -> its supertraits' keys.
    supertraits: HashMap<(usize, String), Vec<String>>,
    /// `(crate, type key)` -> its declarations (two only under two `cfg`s).
    typedefs: HashMap<(usize, String), Vec<(usize, usize)>>,
}

pub fn collect(root: &Path, files: &[PathBuf], rules: &Rules) -> Found {
    let mut found = Found::default();
    let clock = std::time::Instant::now();
    let mut units = Vec::new();
    for abs in files {
        let abs = std::path::absolute(abs).unwrap_or_else(|_| abs.clone());
        let Ok(src) = text::read_source(&abs) else { continue };
        let rel = match abs.strip_prefix(root) {
            Ok(r) => r.to_string_lossy().replace('\\', "/"),
            Err(_) => abs.to_string_lossy().replace('\\', "/"),
        };
        let ex = extract::extract(&rel, &src, rules);
        units.push(FileUnit { rel, abs, ex, at: None, dep: None, test: false });
    }
    // The program's packages, and their direct dependencies where this machine has them.
    let mut packages: Vec<PathBuf> = Vec::new();
    for u in &units {
        let mut dir = u.abs.parent();
        while let Some(d) = dir {
            if !d.starts_with(root) {
                break;
            }
            if d.join("Cargo.toml").is_file() {
                if !packages.iter().any(|p| p == d) {
                    packages.push(d.to_path_buf());
                }
                break;
            }
            dir = d.parent();
        }
    }
    let got = deps::find(root, &packages);
    let mut dep_meta: Vec<(String, String, PathBuf, std::collections::BTreeSet<String>)> = Vec::new();
    let mut budget = DEP_FILE_BOUND;
    for d in got.deps {
        let files = deps::files(&d);
        if files.len() > budget {
            found.not_present.push(format!("{} {} (past the {DEP_FILE_BOUND}-file bound)", d.name, d.version));
            continue;
        }
        budget -= files.len();
        let i = dep_meta.len();
        for abs in files {
            let Ok(src) = text::read_source(&abs) else { continue };
            let rel = format!("{}-{}/{}", d.name, d.version,
                abs.strip_prefix(&d.dir).map(|r| r.to_string_lossy().replace('\\', "/")).unwrap_or_default());
            let ex = extract::extract(&rel, &src, rules);
            units.push(FileUnit { rel, abs, ex, at: None, dep: Some(i), test: false });
        }
        found.read_beyond.push(format!("{} {}", d.name, d.version));
        dep_meta.push((d.name, d.version, d.dir, d.aliases));
    }
    found.not_present.extend(got.missing);
    let read = clock.elapsed();
    let mut prog = Program::build(root, units, &dep_meta, &mut found);
    let built = clock.elapsed();
    prog.resolve_all(&mut found);
    // Evidence on stderr, which the host drains and never parses: where the time went.
    found.notes.push(format!(
        "edges: read and walked {} files in {:.1}s, placed and indexed in {:.1}s, resolved in {:.1}s",
        prog.files.len(), read.as_secs_f64(), (built - read).as_secs_f64(),
        (clock.elapsed() - built).as_secs_f64()));
    found
}

// ------------------------------------------------------------------ crates --- //

/// `[package] name`, `[lib] name` and `path`, and every `[[bin]] path`, read by a line
/// scanner rather than a TOML parser, which would be a vendored crate for four keys. What
/// it does not read: a name or path written as an inline table, or continued over lines.
struct Manifest {
    name: Option<String>,
    /// `[lib] name`: **the name the library is used by, where it is set**. Tauri's template
    /// sets it (`dunnenote_lib`) so that `main.rs` calls `dunnenote_lib::run()`; read by the
    /// package name alone, that call left the program and the binary reached nothing.
    lib_name: Option<String>,
    lib: Option<String>,
    bins: Vec<String>,
}

fn read_manifest(path: &Path) -> Option<Manifest> {
    let text = std::fs::read_to_string(path).ok()?;
    let mut m = Manifest { name: None, lib_name: None, lib: None, bins: Vec::new() };
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
            ("lib", "name") => m.lib_name = Some(v),
            ("bin", "path") => m.bins.push(v),
            _ => {}
        }
    }
    m.name.as_ref()?;
    Some(m)
}

impl Program {
    fn build(root: &Path, files: Vec<FileUnit>,
             dep_meta: &[(String, String, PathBuf, std::collections::BTreeSet<String>)],
             found: &mut Found) -> Program {
        let mut prog = Program {
            memo: std::cell::RefCell::new(HashMap::new()),
            memo_on: std::cell::Cell::new(false),
            files,
            deps: dep_meta.iter().map(|(n, v, _, _)| (n.clone(), v.clone())).collect(),
            crates: Vec::new(),
            by_name: HashMap::new(),
            modules: HashSet::new(),
            excluded: HashSet::new(),
            fns: HashMap::new(),
            local_fns: HashMap::new(),
            methods: HashMap::new(),
            traits: HashSet::new(),
            sealed: HashSet::new(),
            declared: HashMap::new(),
            by_short: HashMap::new(),
            def_trait: HashMap::new(),
            uses: HashMap::new(),
            globs: HashMap::new(),
            method_names: HashSet::new(),
            macros: HashSet::new(),
            fn_names: HashSet::new(),
            typedefs: HashMap::new(),
            supertraits: HashMap::new(),
        };
        let by_abs: HashMap<PathBuf, usize> =
            prog.files.iter().enumerate().map(|(i, f)| (f.abs.clone(), i)).collect();

        // Every package a file belongs to, and its crate roots.
        let mut packages: BTreeMap<PathBuf, Manifest> = BTreeMap::new();
        for (d, ..) in dep_meta.iter().map(|(_, _, d, a)| (d, a)) {
            if let Some(m) = read_manifest(&d.join("Cargo.toml")) {
                packages.insert(d.clone(), m);
            }
        }
        let dep_dirs: Vec<PathBuf> = dep_meta.iter().map(|(_, _, d, _)| d.clone()).collect();
        for f in prog.files.iter().filter(|f| f.dep.is_none()) {
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
            // A dependency is read for its library and nothing else.
            if dep_dirs.contains(dir) {
                continue;
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
            let dep = prog.files[file].dep;
            prog.crates.push(Crate { package: pkg.clone(), dep });
            if is_lib {
                if let Some(m) = pkg.as_ref().and_then(|p| packages.get(p)) {
                    // Cargo's own rule: the `[lib] name` where one is written, and otherwise
                    // the package's name with `-` made `_`. Never both — a library has one name.
                    if let Some(n) = m.lib_name.as_ref().or(m.name.as_ref()) {
                        prog.by_name.insert(n.replace('-', "_"), c);
                    }
                }
                // The names the program's manifests depend on it by.
                if let Some(i) = dep {
                    for a in &dep_meta[i].3 {
                        prog.by_name.insert(a.clone(), c);
                    }
                }
            }
            prog.place(file, c, Vec::new(), true, false, &by_abs, &mut declared);
        }
        // A file nobody declares is a crate of its own. One a `cfg` leaves out is not.
        let mut orphans = 0;
        for i in 0..prog.files.len() {
            if prog.files[i].at.is_none() && !declared.contains(&i) && prog.files[i].dep.is_none() {
                let pkg = packages.keys().filter(|d| prog.files[i].abs.starts_with(d)).max_by_key(|d| d.as_os_str().len()).cloned();
                let c = prog.crates.len();
                prog.crates.push(Crate { package: pkg, dep: None });
                prog.place(i, c, Vec::new(), true, false, &by_abs, &mut declared);
                orphans += 1;
            }
        }
        if orphans > 0 {
            found.notes.push(format!(
                "{orphans} .rs file(s) are no crate's module and are read as crates of their own"
            ));
        }
        found.test_only = prog.files.iter()
            .filter(|f| f.test && f.dep.is_none())
            .map(|f| f.rel.clone())
            .collect();
        found.test_only.sort();
        prog.index();
        prog.memo_on.set(true);
        prog
    }

    /// Put a file in its crate at `module`, and everything it declares under it.
    /// `test`: the file is reached through a `#[cfg(test)] mod x;`, or from under one.
    #[allow(clippy::too_many_arguments)]
    fn place(&mut self, file: usize, c: usize, module: Vec<String>, is_root: bool, test: bool,
             by_abs: &HashMap<PathBuf, usize>, declared: &mut HashSet<usize>) {
        if self.files[file].at.is_some() {
            // Reached a second way: production code wherever any way in is not a test's.
            if !test {
                self.files[file].test = false;
            }
            return;
        }
        self.files[file].at = Some((c, module.clone()));
        self.files[file].test = test;
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
                    self.place(child, c, full.clone(), false, test || m.test, by_abs, declared);
                    break;
                }
            }
        }
    }

    /// **A type's identity is its crate, its module and its name.** Two private types of
    /// one name in two modules of one crate — DunneNote's search crate has a `struct Tok` in
    /// `plain.rs` and an `enum Tok` in `parse.rs` — are two types, and a key on the name
    /// alone pooled their methods, so a call on one could have resolved to the other's.
    /// The key is the crate-relative path, `parse::Tok`, and an `impl`'s type and trait are
    /// resolved in the module the `impl` is written in.
    fn index(&mut self) {
        // Pass 1: what each module declares, and what it brings into scope.
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
            for (ti, t) in f.ex.types.iter().enumerate() {
                let mut at = module.clone();
                at.extend(t.mod_path.iter().cloned());
                let key = type_key(&at, &t.name);
                self.typedefs.entry((*c, key.clone())).or_default().push((fi, ti));
                self.declared.insert((*c, at, t.name.clone()), key.clone());
                self.by_short.entry((*c, t.name.clone())).or_default().push(key.clone());
                if t.is_trait {
                    if t.sealed {
                        self.sealed.insert((*c, key.clone()));
                    }
                    self.traits.insert((*c, key));
                }
            }
            for (di, d) in f.ex.defs.iter().enumerate() {
                if d.owner.is_none() {
                    if let Some(at) = &d.in_fn {
                        self.local_fns.entry((at.clone(), d.name.clone())).or_default().push(DefRef(fi, di));
                    } else {
                        let mut full = module.clone();
                        full.extend(d.mod_path.iter().cloned());
                        self.fns.entry((*c, full, d.name.clone())).or_default().push(DefRef(fi, di));
                    }
                    // The program's own names only: a dependency defining `get` must not
                    // turn every `x.get()` the program writes from *outside* into *unknown*.
                    if f.dep.is_none() {
                        self.fn_names.insert(d.name.clone());
                    }
                } else if f.dep.is_none() {
                    self.method_names.insert(d.name.clone());
                }
            }
            if f.dep.is_none() {
                self.macros.extend(f.ex.macros.iter().cloned());
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
        for v in self.by_short.values_mut() {
            v.sort();
            v.dedup();
        }
        // Pass 2: whose each method is, and which trait each impl is of, now that every
        // name in every module can be looked up. **Remembered while it runs** — every
        // dependency `impl` asks for its type, and asked cold that was 59.7 of DunneNote's
        // 61.5 s — and **forgotten after**, because what this pass is asking is a type, and
        // a lookup that reached a method here was asked before `methods` was filled.
        self.memo_on.set(true);
        let mut methods: Vec<((usize, String, String), DefRef)> = Vec::new();
        let mut owners: Vec<(DefRef, Option<(usize, String)>)> = Vec::new();
        let mut supers: Vec<((usize, String), Vec<String>)> = Vec::new();
        for (fi, f) in self.files.iter().enumerate() {
            let Some((c, module)) = &f.at else { continue };
            for (di, d) in f.ex.defs.iter().enumerate() {
                let Some(owner) = &d.owner else { continue };
                let mut at = module.clone();
                at.extend(d.mod_path.iter().cloned());
                let Some((oc, okey)) = self.type_key_of(*c, &at, owner) else { continue };
                let r = DefRef(fi, di);
                methods.push(((oc, okey, d.name.clone()), r));
                owners.push((r, d.trait_name.as_ref().and_then(|t| self.type_key_of(*c, &at, t))));
            }
            for t in f.ex.types.iter().filter(|t| t.is_trait) {
                let mut at = module.clone();
                at.extend(t.mod_path.iter().cloned());
                let keys: Vec<String> = t.supers.iter().filter_map(|p| {
                    match self.resolve_path(*c, &at, None, p, 0) {
                        Res::Type(sc, k) if sc == *c => Some(k),
                        _ => None,
                    }
                }).collect();
                supers.push(((*c, type_key(&at, &t.name)), keys));
            }
        }
        for (k, r) in methods {
            self.methods.entry(k).or_default().push(r);
        }
        for (r, t) in owners {
            if let Some(t) = t {
                self.def_trait.insert(r, t);
            }
        }
        for (k, v) in supers {
            self.supertraits.insert(k, v);
        }
        self.memo.borrow_mut().clear();
    }

    /// The key of the type a name means in a module: declared there, brought in by a `use`
    /// or a glob, or — the fallback — the one type of that name in the crate.
    fn type_key_of(&self, c: usize, module: &[String], name: &str) -> Option<(usize, String)> {
        match self.resolve_path(c, module, None, &[name.to_owned()], 0) {
            Res::Type(tc, k) => Some((tc, k)),
            _ => None,
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
            "std" | "core" | "alloc" => return Res::Outside(segs.join("::")),
            first => {
                let r = self.lookup(c, module, first, depth);
                match r {
                    Res::Unknown if segs.len() > 1 => {
                        // A path whose first segment is nothing of this program's — a
                        // crate it depends on — goes outside it.
                        return Res::Outside(segs.join("::"));
                    }
                    Res::Unknown => {
                        // A bare name nothing here declares: the prelude, a glob from a
                        // dependency, or a name this resolver could not follow. Outside
                        // only where no function of that name exists anywhere in the
                        // program; otherwise it is ours and unnamed.
                        return if self.fn_names.contains(first) { Res::Unknown } else { Res::Outside(first.to_owned()) };
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
                Res::Type(tc, t) if last => {
                    if let Some(at) = self.variant(tc, &t, seg) {
                        return at;
                    }
                    return self.method(tc, &t, seg);
                }
                Res::Outside(p) => {
                    let mut full = vec![p];
                    full.extend(rest[i..].iter().cloned());
                    return Res::Outside(full.join("::"));
                }
                _ => return Res::Unknown,
            };
        }
        cur
    }

    /// A call whose path ends at a type calls the type: a tuple struct's constructor. Asked
    /// of a call site only, never of a `use`, which names the type itself.
    fn called(&self, r: Res) -> Res {
        if let Res::Type(tc, t) = &r {
            if let Some((fi, ti)) = self.one_type(*tc, t) {
                if self.files[fi].ex.types[ti].tuple {
                    return Res::Construct(fi, ti);
                }
            }
            return Res::Unknown;
        }
        r
    }

    /// The single declaration of a type name in a crate, or nothing where it is not one.
    fn one_type(&self, c: usize, key: &str) -> Option<(usize, usize)> {
        match self.typedefs.get(&(c, key.to_owned())).map(Vec::as_slice) {
            Some([one]) => Some(*one),
            _ => None,
        }
    }

    /// `Enum::Variant(..)`, where `Variant` is one of the enum's tuple variants.
    fn variant(&self, c: usize, ty: &str, seg: &str) -> Option<Res> {
        let (fi, ti) = self.one_type(c, ty)?;
        self.files[fi].ex.types[ti].variants.iter().any(|v| v == seg).then_some(Res::Construct(fi, ti))
    }

    /// One name in one module: its functions, its child modules, its types, its `use`s,
    /// its globs, and the crates the workspace names.
    fn lookup(&self, c: usize, module: &[String], name: &str, depth: usize) -> Res {
        // **Remembered once the index is whole.** A dependency's chains of `pub use …::*`
        // made the same question cost the same glob walk thousands of times: DunneNote's
        // edges took 61.5 s with forty dependencies read and 0.9 s without. The depth is
        // in the key, because an answer cut short at the bound, or one taking the depth-0
        // fallback, is not the answer at another depth.
        if !self.memo_on.get() {
            return self.lookup_uncached(c, module, name, depth);
        }
        let key = (c, module.to_vec(), name.to_owned(), depth);
        if let Some(r) = self.memo.borrow().get(&key) {
            return r.clone();
        }
        let r = self.lookup_uncached(c, module, name, depth);
        self.memo.borrow_mut().insert(key, r.clone());
        r
    }

    fn lookup_uncached(&self, c: usize, module: &[String], name: &str, depth: usize) -> Res {
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
        if let Some(key) = self.declared.get(&(c, module.to_vec(), name.to_owned())) {
            return Res::Type(c, key.clone());
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
        // The last resort, and only for a name nothing above answered: the one type of
        // that name in this crate. Two are two answers, and neither is taken.
        if depth == 0 {
            if let Some([one]) = self.by_short.get(&(c, name.to_owned())).map(Vec::as_slice) {
                return Res::Type(c, one.clone());
            }
        }
        Res::Unknown
    }

    /// `Type::m`: inherent first, else the one trait impl that has it.
    fn method(&self, c: usize, ty: &str, name: &str) -> Res {
        let Some(all) = self.methods.get(&(c, ty.to_owned(), name.to_owned())) else {
            // Derived, blanket, or from a trait or a `Deref` target this program did not
            // write: the method is not here, so neither is its far end.
            // `crate::` so the frontier says the type is this program's and only the method
            // is somebody else's (a derive, a foreign trait's impl, a `Deref` target); a
            // dependency's type is spelt with the dependency's name.
            return Res::Outside(format!("{}::{ty}::{name}", self.crate_name(c)));
        };
        let pick = |want_trait: bool| -> Vec<DefRef> {
            all.iter().copied().filter(|r| self.def(*r).trait_name.is_some() == want_trait).collect::<Vec<_>>()
        };
        let inherent = pick(false);
        if !inherent.is_empty() {
            return Res::Fns(inherent);
        }
        Res::Fns(pick(true))
    }

    /// The functions a body this call is written in declares under its bare name, innermost
    /// body first.
    fn in_body(&self, s: &extract::Site) -> Option<&Vec<DefRef>> {
        let [name] = s.path.as_slice() else { return None };
        s.scopes.iter().find_map(|sc| self.local_fns.get(&(sc.clone(), name.clone())))
    }

    fn def(&self, r: DefRef) -> &Def {
        &self.files[r.0].ex.defs[r.1]
    }

    // ------------------------------------------------------------- resolving --- //

    fn resolve_all(&mut self, found: &mut Found) {
        let mut edges = Vec::new();
        for f in self.files.iter().filter(|f| f.dep.is_none()) {
            let Some((c, module)) = &f.at else {
                for s in f.ex.sites.iter().filter(|s| !s.at_boundary) {
                    found.unknown += 1;
                    edges.push(stop(s, "unfollowed", "", "the file is no crate's module"));
                }
                continue;
            };
            for s in &f.ex.sites {
                if s.at_boundary {
                    continue; // rule 2: the host makes it external whatever is said here
                }
                if s.bound_locally {
                    // A closure or a function pointer: which one is a type's question.
                    found.unknown += 1;
                    edges.push(stop(s, "bound", "", "a value this routine binds itself"));
                    continue;
                }
                let mut at = module.clone();
                at.extend(s.mod_path.iter().cloned());
                // The `impl`'s type, as a key, resolved where the call is written.
                let self_key = s.self_type.as_ref()
                    .and_then(|t| self.type_key_of(*c, &at, t)).map(|(_, k)| k);
                if s.kind == SiteKind::Macro && s.path.last().is_some_and(|m| self.macros.contains(m)) {
                    // The program's own `macro_rules!`: its expansion is code this reader
                    // does not read, though the calls in its arguments are read as calls.
                    found.unknown += 1;
                    edges.push(stop(s, "unfollowed", "", "this program's own macro_rules!, whose expansion is not read"));
                    continue;
                }
                let res = match s.kind {
                    SiteKind::Macro => Res::Outside(self.macro_path(*c, &at, &s.path)),
                    SiteKind::Path if s.recv.is_some() => {
                        // A path on a type parameter (`D::open()`): its bound decides.
                        let ctx = Ctx { c: *c, module: at.clone(), self_type: self_key.clone() };
                        let m = s.path.last().cloned().unwrap_or_default();
                        match s.recv.as_ref().and_then(|h| self.receiver(h, &ctx)) {
                            Some(TyRes::Trait(tc, t)) => match self.implementors(tc, &t, &m) {
                                Dispatch::None => Res::Outside(format!("crate::{t}::{m}")),
                                Dispatch::One(r) => Res::Fns(vec![r]),
                                Dispatch::Many(n) => {
                                    found.unknown += 1;
                                    edges.push(ambiguous(s, n, &format!("a type parameter bound by {t}")));
                                    continue;
                                }
                            },
                            Some(TyRes::Outside(p)) => Res::Outside(format!("{p}::{m}")),
                            _ => {
                                found.unknown += 1;
                                edges.push(stop(s, "untyped", "", "a type parameter with no bound"));
                                continue;
                            }
                        }
                    }
                    // **A bare name looks in the function bodies it is written inside first**,
                    // innermost out, because an item a body declares shadows the module's
                    // and is invisible outside it. pdfcraft's `script.rs` has three
                    // `fn walk`, each inside a different function and each called by its
                    // own: indexed by module, the three were one ambiguous name.
                    SiteKind::Path => match self.in_body(s) {
                        Some(defs) => Res::Fns(defs.clone()),
                        None => self.called(self.resolve_path(*c, &at, self_key.as_deref(), &s.path, 0)),
                    },
                    SiteKind::SelfMethod => match &self_key {
                        Some(t) if self.traits.contains(&(*c, t.clone())) => {
                            // A trait's default body: `self` is whichever type implements
                            // it, and that is not something a path can say.
                            // Unless the trait is sealed and one definition answers.
                            match self.implementors(*c, t, &s.path[0]) {
                                Dispatch::One(r) => Res::Fns(vec![r]),
                                d => {
                                    let n = if let Dispatch::Many(n) = d { n } else { 0 };
                                    found.unknown += 1;
                                    edges.push(ambiguous(s, n.max(2), &format!("self in trait {t}'s default body")));
                                    continue;
                                }
                            }
                        }
                        Some(t) => self.method(*c, t, &s.path[0]),
                        None => Res::Unknown,
                    },
                    SiteKind::Method => {
                        let ctx = Ctx { c: *c, module: at.clone(), self_type: self_key.clone() };
                        match s.recv.as_ref().and_then(|h| self.receiver(h, &ctx)) {
                            Some(TyRes::Local(tc, t)) => self.method(tc, &t, &s.path[0]),
                            Some(TyRes::Trait(tc, t)) => match self.implementors(tc, &t, &s.path[0]) {
                                // No implementor and no default body here: a supertrait's
                                // or another crate's method, so not this program's.
                                Dispatch::None => Res::Outside(format!("crate::{t}::{}", s.path[0])),
                                Dispatch::One(r) => Res::Fns(vec![r]),
                                Dispatch::Many(n) => {
                                    found.unknown += 1;
                                    edges.push(ambiguous(s, n, &format!("a dyn {t}")));
                                    continue;
                                }
                            },
                            Some(TyRes::Outside(p)) => Res::Outside(format!("{p}::{}", s.path[0])),
                            Some(TyRes::Generic(g)) => {
                                found.unknown += 1;
                                edges.push(stop(s, "untyped", "", &format!("a value of type parameter {g}, which has no bound")));
                                continue;
                            }
                            None if self.method_names.contains(&s.path[0]) => {
                                found.unknown += 1;
                                edges.push(stop(s, "untyped", "",
                                    "the receiver's type is not written down, and this program defines a method of that name"));
                                continue;
                            }
                            None => {
                                found.outside += 1;
                                edges.push(stop(s, "outside", &format!("?::{}", s.path[0]),
                                    "a method no type in this program defines, on a receiver whose type is not written down"));
                                continue;
                            }
                        }
                    }
                };
                // A dependency's definition is a frontier, confirmed: its file is not in
                // this map and no edge can name it, but the reader has read it.
                let res = match res {
                    Res::Fns(defs) if !defs.is_empty() && defs.iter().all(|r| self.files[r.0].dep.is_some()) => {
                        let kept: Vec<DefRef> = defs.iter().copied()
                            .filter(|r| self.def(*r).reference != Tri::False).collect();
                        match kept.as_slice() {
                            [one] => {
                                found.outside += 1;
                                let (path, how) = self.dep_path(*one);
                                edges.push(stop(s, "outside", &path, &how));
                                continue;
                            }
                            _ => Res::Outside(self.dep_path(defs[0]).0),
                        }
                    }
                    Res::Construct(fi, ti) if self.files[fi].dep.is_some() => {
                        let ctx = self.type_ctx(fi, ti);
                        let key = ctx.self_type.unwrap_or_default();
                        Res::Outside(format!("{}::{key}", self.crate_name(ctx.c)))
                    }
                    other => other,
                };
                match res {
                    Res::Fns(defs) => {
                        let kept: Vec<DefRef> = defs.iter().copied()
                            .filter(|r| self.def(*r).reference != Tri::False).collect();
                        match kept.len() {
                            1 => {
                                let d = self.def(kept[0]);
                                let mut how = HOW.to_owned();
                                if s.kind == SiteKind::Method {
                                    how.push_str("; by the receiver's declared type");
                                }
                                if defs.len() > 1 {
                                    how.push_str(&format!("; the linux/x86_64 one of {} cfg variants", defs.len()));
                                }
                                edges.push(SuppliedEdge {
                                    site_id: s.site_id.clone(),
                                    caller_id: s.caller_id.clone(),
                                    file: self.files[kept[0].0].rel.clone(),
                                    line: d.line,
                                    name: d.name.clone(),
                                    how,
                                    ..Default::default()
                                });
                            }
                            0 => {
                                found.unknown += 1;
                                edges.push(stop(s, "unfollowed", "", "every definition is another platform's"));
                            }
                            n => {
                                found.unknown += 1;
                                edges.push(ambiguous(s, n as i64, "several definitions on the reference target"));
                            }
                        }
                    }
                    Res::Construct(fi, ti) => {
                        let t = &self.files[fi].ex.types[ti];
                        edges.push(SuppliedEdge {
                            site_id: s.site_id.clone(),
                            caller_id: s.caller_id.clone(),
                            file: self.files[fi].rel.clone(),
                            line: t.line,
                            name: t.name.clone(),
                            how: format!("{HOW}; builds {}", t.name),
                            constructs: t.qualname.clone(),
                            ..Default::default()
                        });
                    }
                    Res::Outside(p) => {
                        found.outside += 1;
                        let how = match s.kind {
                            SiteKind::Macro => "a macro",
                            SiteKind::Method => "by the receiver's declared type",
                            _ => "by the path as written",
                        };
                        edges.push(stop(s, "outside", &qualify(&p), how));
                    }
                    Res::Module(..) | Res::Type(..) | Res::Unknown => {
                        found.unknown += 1;
                        edges.push(stop(s, "unfollowed", "", "a path this resolver could not follow to a definition"));
                    }
                }
            }
        }
        found.edges = edges;
    }

    // ------------------------------------------------------------- receivers --- //

    /// What a receiver's declared type comes to, or nothing where the source does not say.
    fn receiver(&self, h: &Hint, ctx: &Ctx) -> Option<TyRes> {
        let (h, ctx) = self.expand(h, ctx, 0)?;
        self.ty(&h, &ctx)
    }

    /// Follow a hint through declared return types and fields until it is a written type.
    fn expand(&self, h: &Hint, ctx: &Ctx, depth: usize) -> Option<(Hint, Ctx)> {
        if depth > 8 {
            return None;
        }
        match h {
            Hint::Ty { .. } | Hint::Dyn(_) | Hint::Generic(_) => Some(self.dealias(h.clone(), ctx.clone(), depth)),
            Hint::SelfTy => {
                ctx.self_type.as_ref()?;
                Some((Hint::Ty { segs: vec!["Self".into()], args: Vec::new() }, ctx.clone()))
            }
            Hint::Ret(path) => match self.called(self.resolve_path(ctx.c, &ctx.module, ctx.self_type.as_deref(), path, 0)) {
                Res::Fns(defs) => self.returned(&defs, depth),
                Res::Construct(fi, ti) => {
                    Some((Hint::Ty { segs: vec!["Self".into()], args: Vec::new() }, self.type_ctx(fi, ti)))
                }
                _ => None,
            },
            Hint::RetM(recv, m) => match self.receiver(recv, ctx)? {
                TyRes::Local(c, t) => match self.method(c, &t, m) {
                    Res::Fns(defs) => self.returned(&defs, depth),
                    _ => None,
                },
                _ => None,
            },
            Hint::Field(base, f) => match self.receiver(base, ctx)? {
                TyRes::Local(c, t) => {
                    let (fi, ti) = self.one_type(c, &t)?;
                    let (_, fh) = self.files[fi].ex.types[ti].fields.iter().find(|(n, _)| n == f)?;
                    Some((fh.clone(), self.type_ctx(fi, ti)))
                }
                _ => None,
            },
            Hint::Unwrap(inner) => {
                let (h, ctx) = self.expand(inner, ctx, depth + 1)?;
                let (h, ctx) = self.dealias(h, ctx, depth + 1);
                match h {
                    Hint::Ty { segs, args } => {
                        let last = segs.last()?;
                        // `Result`, `Option`, and a crate's own `Result<T>` alias.
                        if (last == "Option" || last.ends_with("Result")) && !args.is_empty() {
                            let first = args.into_iter().next()?;
                            self.expand(&first, &ctx, depth + 1)
                        } else {
                            None
                        }
                    }
                    _ => None,
                }
            }
        }
    }

    /// `type IpcResult<T> = Result<T, E>`: a local alias, replaced by what it stands for,
    /// with its parameters filled from the arguments it was written with.
    fn dealias(&self, h: Hint, ctx: Ctx, depth: usize) -> (Hint, Ctx) {
        if depth > 8 {
            return (h, ctx);
        }
        let Hint::Ty { segs, args } = &h else { return (h, ctx) };
        let Res::Type(c, t) = self.resolve_path(ctx.c, &ctx.module, ctx.self_type.as_deref(), segs, 0) else {
            return (h, ctx);
        };
        let Some((fi, ti)) = self.one_type(c, &t) else { return (h, ctx) };
        let Some((params, target)) = self.files[fi].ex.types[ti].alias.clone() else { return (h, ctx) };
        // An alias used with arguments (`IpcResult<Foo>`) stands for the caller's type, so it
        // stays in the caller's module; one with none (`type Db = Database;`) is resolved
        // where it is written. The residue is an argument-taking alias whose target also
        // names a type only its own module can see, which resolves to nothing, never wrongly.
        let target = substitute(target, &params, args);
        let next = if args.is_empty() { self.type_ctx(fi, ti) } else { ctx };
        self.dealias(target, next, depth + 1)
    }

    /// The declared return type of the one definition kept on the reference target.
    fn returned(&self, defs: &[DefRef], depth: usize) -> Option<(Hint, Ctx)> {
        let kept: Vec<DefRef> = defs.iter().copied().filter(|r| self.def(*r).reference != Tri::False).collect();
        let [one] = kept.as_slice() else { return None };
        let d = self.def(*one);
        let ret = d.ret.clone()?;
        let (c, module) = self.files[one.0].at.clone()?;
        let mut m = module;
        m.extend(d.mod_path.iter().cloned());
        let owner = d.owner.as_ref().and_then(|o| self.type_key_of(c, &m, o)).map(|(_, k)| k);
        self.expand(&ret, &Ctx { c, module: m, self_type: owner }, depth + 1)
    }

    fn type_ctx(&self, fi: usize, ti: usize) -> Ctx {
        let t = &self.files[fi].ex.types[ti];
        let (c, mut module) = self.files[fi].at.clone().unwrap_or((0, Vec::new()));
        module.extend(t.mod_path.iter().cloned());
        let key = type_key(&module, &t.name);
        Ctx { c, module, self_type: Some(key) }
    }

    /// A written type, resolved in the module it is written in.
    fn ty(&self, h: &Hint, ctx: &Ctx) -> Option<TyRes> {
        let (segs, dynamic) = match h {
            Hint::Ty { segs, .. } => (segs, false),
            Hint::Dyn(segs) => (segs, true),
            Hint::Generic(g) => return Some(TyRes::Generic(g.clone())),
            _ => return None,
        };
        if segs.is_empty() {
            return None;
        }
        match self.resolve_path(ctx.c, &ctx.module, ctx.self_type.as_deref(), segs, 0) {
            Res::Type(c, t) if dynamic || self.traits.contains(&(c, t.clone())) => Some(TyRes::Trait(c, t)),
            Res::Type(c, t) => Some(TyRes::Local(c, t)),
            Res::Outside(p) if !p.is_empty() => Some(TyRes::Outside(p)),
            _ => None,
        }
    }

    /// A macro's full path where a `use` brought it in (`params!` -> `rusqlite::params!`),
    /// else as written.
    fn macro_path(&self, c: usize, module: &[String], path: &[String]) -> String {
        if let [one] = path {
            if let Some(targets) = self.uses.get(&(c, module.to_vec(), one.clone())) {
                if let [t] = targets.as_slice() {
                    return format!("{}!", t.join("::"));
                }
            }
        }
        format!("{}!", path.join("::"))
    }

    /// `crate`, or a dependency's own name.
    fn crate_name(&self, c: usize) -> String {
        match self.crates.get(c).and_then(|k| k.dep) {
            Some(i) => self.deps[i].0.clone(),
            None => "crate".into(),
        }
    }

    /// A dependency's definition as a path in that crate, and how it was known.
    fn dep_path(&self, r: DefRef) -> (String, String) {
        let f = &self.files[r.0];
        let d = self.def(r);
        let i = f.dep.unwrap_or(0);
        let (name, version) = &self.deps[i];
        let (_, module) = f.at.clone().unwrap_or((0, Vec::new()));
        let mut parts = vec![name.clone()];
        parts.extend(module);
        parts.extend(d.mod_path.iter().cloned());
        if let Some(o) = &d.owner {
            parts.push(o.clone());
        }
        parts.push(d.name.clone());
        (parts.join("::"), format!("confirmed in {name} {version}'s source on this machine"))
    }

    /// Which definitions in this crate could answer `t::m` when `t` is dispatched on: `self`
    /// in its default body, a `dyn t`, or a type parameter bound by it. The method may be the
    /// trait's own or a supertrait's (`trait Streaming: Destination`), so the supertraits are
    /// counted too, each once.
    ///
    /// **One answer is an edge only when every trait in that chain is sealed** — written
    /// without `pub`, so no other crate can implement it and an override this map does not
    /// hold cannot exist. A `pub` trait with one implementor here is still `Many`: another
    /// crate may write the second (rule 1).
    fn implementors(&self, c: usize, t: &str, m: &str) -> Dispatch {
        let mut want: Vec<String> = vec![t.to_owned()];
        let mut i = 0;
        while i < want.len() && want.len() < 32 {
            for sup in self.supertraits.get(&(c, want[i].clone())).cloned().unwrap_or_default() {
                if !want.contains(&sup) {
                    want.push(sup);
                }
            }
            i += 1;
        }
        let mut found: Vec<DefRef> = Vec::new();
        for ((_, owner, name), defs) in &self.methods {
            if name != m {
                continue;
            }
            found.extend(defs.iter().copied().filter(|r| {
                // A default body is the trait's own; an impl's method is the impl's trait's.
                let own = want.contains(owner) && self.traits.contains(&(c, owner.clone()));
                own || self.def_trait.get(r).is_some_and(|(tc, tk)| *tc == c && want.contains(tk))
            }));
        }
        match found.as_slice() {
            [] => Dispatch::None,
            [one] if want.iter().all(|w| self.sealed.contains(&(c, w.clone()))) => Dispatch::One(*one),
            _ => Dispatch::Many(found.len() as i64),
        }
    }
}

/// What a dispatch through a trait can land on.
enum Dispatch {
    /// Nothing this program defines.
    None,
    /// Exactly one definition, and the trait is sealed, so nothing else can be written.
    One(DefRef),
    /// Several, or one where another crate could add a second.
    Many(i64),
}

fn ambiguous(s: &extract::Site, n: i64, why: &str) -> SuppliedEdge {
    SuppliedEdge {
        site_id: s.site_id.clone(),
        caller_id: s.caller_id.clone(),
        how: format!("{HOW}; {why}"),
        candidates: n,
        reason: "dynamic".into(),
        ..Default::default()
    }
}

/// A type's crate-relative key: `parse::Tok`, or `Tok` at a crate's root.
fn type_key(module: &[String], name: &str) -> String {
    let mut parts: Vec<&str> = module.iter().map(String::as_str).collect();
    parts.push(name);
    parts.join("::")
}

/// An alias's target with its own type parameters replaced by the arguments it was used
/// with. A parameter with no argument is left as written.
fn substitute(h: Hint, params: &[String], args: &[Hint]) -> Hint {
    match h {
        Hint::Ty { segs, args: inner } => {
            if let [one] = segs.as_slice() {
                if let Some(i) = params.iter().position(|p| p == one) {
                    if let Some(a) = args.get(i) {
                        return a.clone();
                    }
                }
            }
            Hint::Ty { segs, args: inner.into_iter().map(|a| substitute(a, params, args)).collect() }
        }
        other => other,
    }
}

/// The prelude's values and types, std's own macros and the primitive types: names a
/// program uses bare that are std's, spelt as std's so a frontier groups by crate.
const PRELUDE_VALUES: &[&str] = &["Ok", "Err", "Some", "None", "drop", "Box", "Vec", "String",
    "Option", "Result", "Default", "From", "Into", "ToString", "ToOwned", "Iterator"];
const PRIMITIVES: &[&str] = &["str", "bool", "char", "u8", "u16", "u32", "u64", "u128", "usize",
    "i8", "i16", "i32", "i64", "i128", "isize", "f32", "f64"];
const STD_MACROS: &[&str] = &["format", "vec", "println", "print", "eprintln", "eprint", "write",
    "writeln", "panic", "assert", "assert_eq", "assert_ne", "debug_assert", "debug_assert_eq",
    "debug_assert_ne", "unreachable", "unimplemented", "todo", "matches", "concat", "stringify",
    "include_str", "include_bytes", "env", "option_env", "dbg", "line", "file", "column",
    "module_path", "cfg", "format_args", "thread_local"];

fn qualify(p: &str) -> String {
    let first = p.split("::").next().unwrap_or(p);
    if let Some(name) = first.strip_suffix('!') {
        if !p.contains("::") && STD_MACROS.contains(&name) {
            return format!("std::{p}");
        }
        return p.to_owned();
    }
    if PRIMITIVES.contains(&first) {
        return format!("std::primitive::{p}");
    }
    if PRELUDE_VALUES.contains(&first) {
        return format!("std::{p}");
    }
    p.to_owned()
}

/// A call with no edge, and what is known about where it stops.
fn stop(s: &extract::Site, reason: &str, frontier: &str, why: &str) -> SuppliedEdge {
    SuppliedEdge {
        site_id: s.site_id.clone(),
        caller_id: s.caller_id.clone(),
        how: format!("{HOW}; {why}"),
        frontier: frontier.to_owned(),
        reason: reason.to_owned(),
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
