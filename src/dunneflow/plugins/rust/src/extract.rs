//! One file's facts.
//!
//! `plugins/go/extract.go` is the model and the two agree wherever the languages let them;
//! where Rust differs, the difference is said at the place it is decided.
//!
//! **Identity first** (LANGUAGES.md: decide it before writing the reader). The module is
//! the file's dotted path, as Go's is. A free function is `module.f`; an inherent method
//! is `module.Type.m`; **a trait method is `module.Type.Trait.m`**, because one type
//! implementing both `Display` and `Debug` has two `fmt`s and without the trait they are one
//! qualname twice; an inline `mod x { }` adds a segment; a function inside a function is
//! `outer.inner`. A duplicate in one file — the same item under two `#[cfg]`s — takes an
//! ordinal through `definition_id`, and nothing else mints an id.
//!
//! **Test code inside a source file is left out and counted.** About 120 of DunneNote's
//! files carry `#[cfg(test)] mod tests`, which is Rust's idiom where Go and Python write a
//! second file; the walk leaves those files out as tests, so this leaves the items out as
//! tests, and `tests_dropped` says how many (design rule 1). `--include-tests` does not
//! reach a reader and the cache key does not carry it, so it does not bring these back —
//! a stated residue, because making it would be a key change (rule 81).
//!
//! **A closure is not a routine.** `let f = |x| …` is everywhere in Rust and is the
//! internal computation this tool does not report; what a closure calls belongs to the
//! routine it is written in. Go makes `h := func(){…}` a routine; Rust's idiom is too
//! common for that to help anybody orient.
//!
//! **A struct literal is not a call.** `Foo { a: 1 }` runs no constructor, so it is not a
//! call site (Go's answer for `T{}`); `Foo::new()` is an ordinary call to `Foo.new`.

use std::collections::{HashMap, HashSet};

use proc_macro2::Span;
use syn::punctuated::Punctuated;
use syn::spanned::Spanned;
use syn::visit::{self, Visit};
use syn::{
    Attribute, Expr, FnArg, ImplItem, Item, Lit, Macro, Member, Meta, Pat, ReturnType, Stmt,
    Token, TraitItem, Type, UseTree, Visibility,
};

use crate::cfg;
use crate::comments;
use crate::facts::*;
use crate::ids::{call_site_id, control_point_id, definition_id, entrypoint_id, hash_source};
use crate::rules::{BoundaryRule, Rules};

pub const MODULE_SCOPE: &str = "<module>";
const LITERAL_MIN: usize = 3;
const LITERAL_MAX: usize = 200_000;

/// `src/net/mod.rs` -> `src.net.mod`. The file's own dotted path, as Go's `moduleName`,
/// so `probe.rs` is module `probe` beside `probe.go` and `probe.py` (`test_identity`).
pub fn module_name(rel: &str) -> String {
    let stem = rel.strip_suffix(".rs").unwrap_or(rel);
    stem.split('/').filter(|p| !p.is_empty()).collect::<Vec<_>>().join(".")
}

/// What the edge pass needs to know about one call, recorded by the same walk that minted
/// its `site_id`, so the two passes cannot disagree about which call is which.
#[derive(Debug, Clone)]
pub struct Site {
    pub site_id: String,
    pub caller_id: String,
    pub kind: SiteKind,
    /// The path as written, segment by segment (`crate`, `super` and `Self` included).
    pub path: Vec<String>,
    /// The inline modules the call is written inside.
    pub mod_path: Vec<String>,
    /// The type of the `impl` the call is written in, if any.
    pub self_type: Option<String>,
    pub at_boundary: bool,
    pub bound_locally: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SiteKind {
    /// `a::b::f(…)`
    Path,
    /// `self.m(…)`
    SelfMethod,
    /// `x.m(…)` on anything else
    Method,
    /// `name!(…)`
    Macro,
}

/// A definition the edge pass can resolve to.
#[derive(Debug, Clone)]
pub struct Def {
    pub name: String,
    pub line: i64,
    pub mod_path: Vec<String>,
    /// `Some(type)` for a method, with the trait if it is a trait impl's.
    pub owner: Option<String>,
    pub trait_name: Option<String>,
    /// `#[cfg]` evaluated against the reference target.
    pub reference: cfg::Tri,
}

/// One name a `use` brings into scope.
#[derive(Debug, Clone)]
pub struct UseRec {
    pub mod_path: Vec<String>,
    /// The local name, or `*` for a glob.
    pub local: String,
    pub target: Vec<String>,
    pub reference: cfg::Tri,
}

/// `mod x;` — a module whose body is another file.
#[derive(Debug, Clone)]
pub struct ModDecl {
    pub mod_path: Vec<String>,
    pub name: String,
    pub path_attr: Option<String>,
    pub reference: cfg::Tri,
    /// `mod x { … }`, whose body is in this file.
    pub inline: bool,
}

#[derive(Default)]
pub struct Extracted {
    pub facts: FileFacts,
    pub sites: Vec<Site>,
    pub defs: Vec<Def>,
    pub uses: Vec<UseRec>,
    pub mods: Vec<ModDecl>,
    pub impls: Vec<(String, Option<String>)>,
}

pub fn extract_file(rel: &str, source: &str, rules: &Rules) -> FileFacts {
    extract(rel, source, rules).facts
}

/// Facts and the edge pass's side tables, in one walk.
pub fn extract(rel: &str, source: &str, rules: &Rules) -> Extracted {
    let module = module_name(rel);
    let mut ff = FileFacts {
        path: rel.to_owned(),
        lang: crate::LANG.to_owned(),
        module: module.clone(),
        content_hash: hash_source(source),
        ..Default::default()
    };
    // `syn::parse_file` strips a BOM and a shebang and then reports offsets into what is
    // left. Stripped here instead, so every byte range is into the file as the host reads
    // it; the shebang's newline is kept, so lines need no correction.
    let mut base = 0usize;
    if source.starts_with('\u{feff}') {
        base = '\u{feff}'.len_utf8();
    }
    if source[base..].starts_with("#!") && !source[base + 2..].trim_start().starts_with('[') {
        base += source[base..].find('\n').unwrap_or(source.len() - base);
    }
    let parsed = syn::parse_str::<syn::File>(&source[base..]);
    let file = match parsed {
        Ok(f) => f,
        Err(e) => {
            // A parse error is a fact about the file, never a failure of the reader.
            let at = e.span().start();
            ff.errors.push(format!("{}:{} {}", at.line, at.column + 1, e));
            proc_macro2::extra::invalidate_current_thread_spans();
            return Extracted { facts: ff, ..Default::default() };
        }
    };
    let mut ex = Ex::new(rel, &module, source, base, rules);
    ex.facts.doc = docs(&file.attrs).unwrap_or_default();
    for item in &file.items {
        ex.item(item);
    }
    ex.land_comments();
    let out = ex.finish(ff);
    proc_macro2::extra::invalidate_current_thread_spans();
    out
}

struct Ex<'a> {
    path: String,
    module: String,
    src: &'a str,
    base: usize,
    rules: &'a Rules,
    facts: FileFacts,
    routines: Vec<Routine>,
    /// Indices into `routines`, innermost last.
    scope: Vec<usize>,
    module_scope: Routine,
    module_claimed: bool,
    seen_qual: HashMap<String, i64>,
    call_ord: HashMap<String, i64>,
    ctrl_ord: HashMap<String, i64>,
    depth: i64,
    mod_path: Vec<String>,
    /// `(type, trait)` of the `impl` being read.
    imp: Option<(String, Option<String>)>,
    /// Calls whose value is thrown away, by byte offset (see `rust.yaml` on `inert`).
    discarded: HashSet<usize>,
    /// Names each open routine binds itself — its parameters and every `let` — innermost
    /// last. Over the whole routine rather than per block, which declines a few calls it
    /// could have resolved and never resolves one it should not (rule 1).
    locals: Vec<HashSet<String>>,
    sites: Vec<Site>,
    defs: Vec<Def>,
    uses: Vec<UseRec>,
    mods: Vec<ModDecl>,
    impls: Vec<(String, Option<String>)>,
}

impl<'a> Ex<'a> {
    fn new(rel: &str, module: &str, src: &'a str, base: usize, rules: &'a Rules) -> Ex<'a> {
        let qual = format!("{module}.{MODULE_SCOPE}");
        let lines = src.matches('\n').count().max(1) as i64;
        let module_scope = Routine {
            id: definition_id(rel, &qual, 1),
            name: MODULE_SCOPE.to_owned(),
            qualname: qual,
            module: module.to_owned(),
            file: rel.to_owned(),
            line_start: 1,
            line_end: lines,
            docstring: Some(
                "Items at module level: statics, consts and their initialisers.".into(),
            ),
            body_hash: hash_source(src),
            ..Default::default()
        };
        Ex {
            path: rel.to_owned(),
            module: module.to_owned(),
            src,
            base,
            rules,
            facts: FileFacts::default(),
            routines: Vec::new(),
            scope: Vec::new(),
            module_scope,
            module_claimed: false,
            seen_qual: HashMap::new(),
            call_ord: HashMap::new(),
            ctrl_ord: HashMap::new(),
            depth: 0,
            mod_path: Vec::new(),
            imp: None,
            discarded: HashSet::new(),
            locals: Vec::new(),
            sites: Vec::new(),
            defs: Vec::new(),
            uses: Vec::new(),
            mods: Vec::new(),
            impls: Vec::new(),
        }
    }

    fn finish(mut self, mut ff: FileFacts) -> Extracted {
        if self.module_claimed {
            self.routines.insert(0, self.module_scope.clone());
        }
        ff.doc = std::mem::take(&mut self.facts.doc);
        ff.routines = std::mem::take(&mut self.routines);
        let f = &mut self.facts;
        ff.calls = std::mem::take(&mut f.calls);
        ff.boundaries = std::mem::take(&mut f.boundaries);
        ff.structures = std::mem::take(&mut f.structures);
        ff.classes = std::mem::take(&mut f.classes);
        ff.entrypoints = std::mem::take(&mut f.entrypoints);
        ff.imports = std::mem::take(&mut f.imports);
        ff.constants = std::mem::take(&mut f.constants);
        ff.control = std::mem::take(&mut f.control);
        ff.control_arms = std::mem::take(&mut f.control_arms);
        ff.literals = std::mem::take(&mut f.literals);
        ff.network = std::mem::take(&mut f.network);
        ff.literals_dropped = f.literals_dropped;
        ff.tests_dropped = f.tests_dropped;
        // Always sent, claimed or not: a string names its owner before anybody knows
        // whether it is a fact (rule 96, `extract.ts:moduleScope`).
        ff.module_scope = Some(self.module_scope.clone());
        Extracted {
            facts: ff,
            sites: self.sites,
            defs: self.defs,
            uses: self.uses,
            mods: self.mods,
            impls: self.impls,
        }
    }

    // ------------------------------------------------------------ positions --- //

    fn line(&self, s: Span) -> i64 {
        s.start().line as i64
    }

    fn end_line(&self, s: Span) -> i64 {
        s.end().line as i64
    }

    /// A node as written, sliced from the file's own text and never re-rendered. A byte
    /// range, never a column: `proc-macro2` counts columns in characters (rule 75).
    fn text(&self, s: Span) -> String {
        let r = s.byte_range();
        let (a, b) = (r.start + self.base, r.end + self.base);
        if a <= b && b <= self.src.len() && self.src.is_char_boundary(a) && self.src.is_char_boundary(b) {
            self.src[a..b].to_owned()
        } else {
            String::new()
        }
    }

    fn offset(&self, s: Span) -> usize {
        s.byte_range().start + self.base
    }

    // ---------------------------------------------------------------- owner --- //

    fn identity(&mut self, qual: &str) -> String {
        let n = self.seen_qual.entry(qual.to_owned()).or_insert(0);
        *n += 1;
        definition_id(&self.path, qual, *n)
    }

    /// The routine a fact belongs to, claiming the module scope only when it is needed,
    /// so asking is not what puts a routine in the map (rule 96).
    fn owner_id(&mut self) -> String {
        if let Some(&i) = self.scope.last() {
            return self.routines[i].id.clone();
        }
        self.module_claimed = true;
        self.module_scope.id.clone()
    }

    fn owner_async(&self) -> bool {
        self.scope.last().is_some_and(|&i| self.routines[i].is_async)
    }

    fn prefix(&self) -> String {
        let mut parts = vec![self.module.clone()];
        parts.extend(self.mod_path.iter().cloned());
        parts.join(".")
    }

    // ---------------------------------------------------------------- items --- //

    fn item(&mut self, item: &Item) {
        if let Some(attrs) = item_attrs(item) {
            if cfg::is_test(attrs) {
                self.facts.tests_dropped += 1;
                return;
            }
        }
        match item {
            Item::Fn(f) => {
                let qual = format!("{}.{}", self.prefix(), f.sig.ident);
                let start = vis_or(&f.vis, f.sig.span());
                let top = self.mod_path.is_empty();
                self.defs.push(Def {
                    name: f.sig.ident.to_string(),
                    line: self.line(start),
                    mod_path: self.mod_path.clone(),
                    owner: None,
                    trait_name: None,
                    reference: cfg::item(&f.attrs, cfg::REFERENCE),
                });
                let public = matches!(f.vis, Visibility::Public(_));
                let r = self.routine(
                    &f.sig, Some(&f.block), &f.attrs, public, start, qual, None, false,
                );
                if top && self.scope.is_empty() && self.rules.entry_names.iter().any(|n| f.sig.ident == n) {
                    self.way_in(r);
                }
            }
            Item::Impl(imp) => {
                let ty = type_name(&imp.self_ty);
                let tr = imp.trait_.as_ref().and_then(|(_, p, _)| p.segments.last()).map(|s| s.ident.to_string());
                let Some(ty) = ty else {
                    // `impl<T> Trait for &T`: no named type to hang a method on. Its bodies
                    // are still walked, under the module scope, so their calls are kept.
                    for it in &imp.items {
                        if let ImplItem::Fn(m) = it {
                            self.block_body(&m.block);
                        }
                    }
                    return;
                };
                self.impls.push((ty.clone(), tr.clone()));
                let saved = self.imp.replace((ty.clone(), tr.clone()));
                for it in &imp.items {
                    match it {
                        ImplItem::Fn(m) => {
                            if cfg::is_test(&m.attrs) {
                                self.facts.tests_dropped += 1;
                                continue;
                            }
                            let mut qual = format!("{}.{}", self.prefix(), ty);
                            if let Some(t) = &tr {
                                qual.push('.');
                                qual.push_str(t);
                            }
                            qual.push('.');
                            qual.push_str(&m.sig.ident.to_string());
                            let has_self = matches!(m.sig.inputs.first(), Some(FnArg::Receiver(_)));
                            self.defs.push(Def {
                                name: m.sig.ident.to_string(),
                                line: self.line(vis_or(&m.vis, m.sig.span())),
                                mod_path: self.mod_path.clone(),
                                owner: Some(ty.clone()),
                                trait_name: tr.clone(),
                                reference: cfg::item(&m.attrs, cfg::REFERENCE)
                                    .and(cfg::item(&imp.attrs, cfg::REFERENCE)),
                            });
                            // A trait's method is as visible as the trait, whatever the impl
                            // writes (it can write nothing).
                            let public = tr.is_some() || matches!(m.vis, Visibility::Public(_));
                            self.routine(
                                &m.sig, Some(&m.block), &m.attrs, public,
                                vis_or(&m.vis, m.sig.span()), qual, Some(ty.clone()), has_self,
                            );
                        }
                        ImplItem::Const(c) => self.walk_expr(&c.expr),
                        _ => {}
                    }
                }
                self.imp = saved;
            }
            Item::Trait(t) => {
                let name = t.ident.to_string();
                let mut ds = self.structure(&name, StructureKind::Interface, t.ident.span(), &t.attrs);
                for sup in &t.supertraits {
                    ds.bases.push(self.text(sup.span()));
                }
                let saved = self.imp.replace((name.clone(), None));
                for it in &t.items {
                    if let TraitItem::Fn(m) = it {
                        ds.fields.push(Field_ {
                            name: m.sig.ident.to_string(),
                            r#type: Some(self.text(m.sig.span())),
                            ..Default::default()
                        });
                        if let Some(body) = &m.default {
                            let qual = format!("{}.{}.{}", self.prefix(), name, m.sig.ident);
                            let has_self = matches!(m.sig.inputs.first(), Some(FnArg::Receiver(_)));
                            self.defs.push(Def {
                                name: m.sig.ident.to_string(),
                                line: self.line(m.sig.span()),
                                mod_path: self.mod_path.clone(),
                                owner: Some(name.clone()),
                                trait_name: Some(name.clone()),
                                reference: cfg::item(&m.attrs, cfg::REFERENCE),
                            });
                            self.routine(
                                &m.sig, Some(body), &m.attrs, true,
                                m.sig.span(), qual, Some(name.clone()), has_self,
                            );
                        }
                    }
                }
                self.imp = saved;
                self.facts.structures.push(ds);
            }
            Item::Struct(s) => {
                let name = s.ident.to_string();
                let mut ds = self.structure(&name, StructureKind::Class, s.ident.span(), &s.attrs);
                for (i, f) in s.fields.iter().enumerate() {
                    ds.fields.push(Field_ {
                        name: f.ident.as_ref().map(|i| i.to_string()).unwrap_or_else(|| i.to_string()),
                        r#type: Some(self.text(f.ty.span())),
                        comment: docs(&f.attrs),
                        ..Default::default()
                    });
                }
                self.facts.classes.push(ClassDef_ {
                    name: name.clone(),
                    qualname: format!("{}.{}", self.prefix(), name),
                    module: self.module.clone(),
                    file: self.path.clone(),
                    line: ds.line,
                    bases: Vec::new(),
                });
                self.facts.structures.push(ds);
            }
            Item::Union(u) => {
                let name = u.ident.to_string();
                let mut ds = self.structure(&name, StructureKind::Class, u.ident.span(), &u.attrs);
                for f in &u.fields.named {
                    ds.fields.push(Field_ {
                        name: f.ident.as_ref().map(|i| i.to_string()).unwrap_or_default(),
                        r#type: Some(self.text(f.ty.span())),
                        ..Default::default()
                    });
                }
                self.facts.structures.push(ds);
            }
            Item::Enum(e) => {
                // Rule 19: a set of named values of one type is an enum, and Rust says so.
                let name = e.ident.to_string();
                let mut ds = self.structure(&name, StructureKind::Enum, e.ident.span(), &e.attrs);
                for v in &e.variants {
                    ds.fields.push(Field_ {
                        name: v.ident.to_string(),
                        default: v.discriminant.as_ref().map(|(_, x)| self.text(x.span())),
                        comment: docs(&v.attrs),
                        ..Default::default()
                    });
                    if let Some((_, x)) = &v.discriminant {
                        self.walk_expr(x);
                    }
                }
                self.facts.structures.push(ds);
            }
            Item::Type(t) => {
                let name = t.ident.to_string();
                let mut ds = self.structure(&name, StructureKind::TypeAlias, t.ident.span(), &t.attrs);
                ds.bases.push(self.text(t.ty.span()));
                self.facts.structures.push(ds);
            }
            Item::Const(c) => {
                self.constant(&c.ident, Some(&c.ty), &c.expr, true, &c.vis, &c.attrs);
            }
            Item::Static(s) => {
                let fin = matches!(s.mutability, syn::StaticMutability::None);
                self.constant(&s.ident, Some(&s.ty), &s.expr, fin, &s.vis, &s.attrs);
            }
            Item::Use(u) => {
                let reference = cfg::item(&u.attrs, cfg::REFERENCE);
                let line = self.line(u.span());
                let mut found = Vec::new();
                flatten_use(&u.tree, &mut Vec::new(), &mut found);
                for (target, local) in found {
                    let (module, name) = match target.split_last() {
                        Some((last, rest)) if !rest.is_empty() => (rest.join("::"), last.clone()),
                        Some((last, _)) => (last.clone(), last.clone()),
                        None => continue,
                    };
                    let alias = if local != name && local != "*" { local.clone() } else { String::new() };
                    self.facts.imports.push(ImportRec {
                        module,
                        name,
                        alias,
                        is_from: target.len() > 1,
                        line,
                    });
                    self.uses.push(UseRec { mod_path: self.mod_path.clone(), local, target, reference });
                }
            }
            Item::Mod(m) => {
                let name = m.ident.to_string();
                match &m.content {
                    Some((_, items)) => {
                        self.mods.push(ModDecl {
                            mod_path: self.mod_path.clone(),
                            name: name.clone(),
                            path_attr: None,
                            reference: cfg::item(&m.attrs, cfg::REFERENCE),
                            inline: true,
                        });
                        self.mod_path.push(name);
                        for it in items {
                            self.item(it);
                        }
                        self.mod_path.pop();
                    }
                    None => {
                        let path_attr = m.attrs.iter().find(|a| a.path().is_ident("path")).and_then(|a| match &a.meta {
                            Meta::NameValue(nv) => match &nv.value {
                                Expr::Lit(l) => match &l.lit {
                                    Lit::Str(s) => Some(s.value()),
                                    _ => None,
                                },
                                _ => None,
                            },
                            _ => None,
                        });
                        self.mods.push(ModDecl {
                            mod_path: self.mod_path.clone(),
                            name,
                            path_attr,
                            reference: cfg::item(&m.attrs, cfg::REFERENCE),
                            inline: false,
                        });
                    }
                }
            }
            // `macro_rules! name { … }` defines a macro; its body is a pattern language, not
            // code, and is not walked. Any other item-level macro is a call, owned by the
            // module scope because that is where it is written.
            Item::Macro(m) if m.ident.is_none() => self.mac(&m.mac, false),
            _ => {}
        }
    }

    fn structure(&mut self, name: &str, kind: StructureKind, at: Span, attrs: &[Attribute]) -> DataStructure {
        let qual = format!("{}.{}", self.prefix(), name);
        DataStructure {
            id: self.identity(&format!("struct\0{qual}")),
            name: name.to_owned(),
            kind,
            module: self.module.clone(),
            file: self.path.clone(),
            line: self.line(at),
            docstring: docs(attrs),
            ..Default::default()
        }
    }

    fn constant(&mut self, ident: &syn::Ident, ty: Option<&Type>, expr: &Expr, fin: bool,
                vis: &Visibility, attrs: &[Attribute]) {
        let comment = docs(attrs).and_then(|d| d.lines().next().map(|l| l.trim().to_owned()))
            .filter(|l| !l.is_empty());
        self.facts.constants.push(Constant {
            name: ident.to_string(),
            value: self.text(expr.span()),
            line: self.line(ident.span()),
            r#type: ty.map(|t| self.text(t.span())),
            is_final: fin,
            comment,
            private: !matches!(vis, Visibility::Public(_)),
        });
        // An initialiser runs where it is written — at first use for a `static`, at compile
        // time for a `const` — and either way it belongs to no function.
        self.walk_expr(expr);
    }

    #[allow(clippy::too_many_arguments)]
    fn routine(&mut self, sig: &syn::Signature, body: Option<&syn::Block>, attrs: &[Attribute],
               public: bool, start: Span, qual: String, class: Option<String>,
               has_self: bool) -> usize {
        let parent = self.scope.last().copied();
        let qual = match parent {
            Some(p) => format!("{}.{}", self.routines[p].qualname, sig.ident),
            None => qual,
        };
        let end = body.map(|b| b.brace_token.span.close()).unwrap_or_else(|| sig.span());
        let mut r = Routine {
            id: self.identity(&qual),
            name: sig.ident.to_string(),
            qualname: qual,
            module: self.module.clone(),
            file: self.path.clone(),
            line_start: self.line(start),
            line_end: self.end_line(end),
            body_hash: hash_source(&body.map(|b| self.text(b.span())).unwrap_or_default()),
            is_async: sig.asyncness.is_some(),
            is_method: has_self,
            class_name: class,
            is_nested: parent.is_some(),
            docstring: docs(attrs),
            ..Default::default()
        };
        // **Always declared.** A function with no `->` returns `()`, and says so by the
        // absence; `None` would mean *undeclared*, which no Rust function is, and Go's
        // `MISSING_RETURN_TYPE` finding is what that costs (rule 98).
        r.returns = Some(match &sig.output {
            ReturnType::Default => String::new(),
            ReturnType::Type(_, t) => self.text(t.span()),
        });
        if !public {
            r.visibility = "private".into();
        }
        for a in attrs {
            if !a.path().is_ident("doc") {
                r.decorators.push(dotted_path(a.path()));
            }
        }
        for arg in &sig.inputs {
            if let FnArg::Typed(pt) = arg {
                let name = match &*pt.pat {
                    Pat::Ident(pi) => pi.ident.to_string(),
                    other => self.text(other.span()),
                };
                r.params.push(Param { name, r#type: Some(self.text(pt.ty.span())), ..Default::default() });
            }
        }
        if sig.variadic.is_some() {
            r.params.push(Param { name: "...".into(), kind: "vararg".into(), ..Default::default() });
        }
        let mut bound: HashSet<String> = r.params.iter().map(|p| p.name.clone()).collect();
        if let Some(b) = body {
            collect_lets(b, &mut bound);
        }
        self.routines.push(r);
        let idx = self.routines.len() - 1;
        self.scope.push(idx);
        self.locals.push(bound);
        let saved = self.depth;
        self.depth = 0;
        if let Some(b) = body {
            self.block_body(b);
        }
        self.depth = saved;
        self.scope.pop();
        self.locals.pop();
        idx
    }

    fn way_in(&mut self, idx: usize) {
        // A build script is a way into the build, not into the program it builds.
        if self.path == "build.rs" || self.path.ends_with("/build.rs") {
            return;
        }
        let r = &self.routines[idx];
        let ep = Entrypoint {
            id: entrypoint_id(&self.path, &[&r.qualname, "main"]),
            kind: EntrypointKind::Main,
            name: r.name.clone(),
            routine_id: Some(r.id.clone()),
            module: self.module.clone(),
            evidence: format!("{}() at {}:{}", r.name, self.path, r.line_start),
            ..Default::default()
        };
        self.facts.entrypoints.push(ep);
    }

    fn block_body(&mut self, b: &syn::Block) {
        for s in &b.stmts {
            self.stmt(s);
        }
    }

    fn stmt(&mut self, s: &Stmt) {
        match s {
            Stmt::Item(it) => {
                // A function inside a function is a routine of its own, nested.
                self.item(it);
            }
            Stmt::Expr(e, Some(_)) => {
                self.mark_discarded(e);
                self.walk_expr(e);
            }
            Stmt::Local(l) => {
                if let (Pat::Wild(_), Some(init)) = (&l.pat, &l.init) {
                    self.mark_discarded(&init.expr);
                }
                if let Some(init) = &l.init {
                    if let Some((_, diverge)) = &init.diverge {
                        self.let_else(l, &init.expr, diverge);
                        return;
                    }
                }
                let mut v = Walker { ex: self };
                v.visit_local(l);
            }
            _ => {
                let mut v = Walker { ex: self };
                v.visit_stmt(s);
            }
        }
    }

    /// `f(x);` and `let _ = f(x);` throw the value away. For an inert future that is the
    /// whole of the defect; a future that is bound, returned, awaited or handed to
    /// anything is not discarded and is never reported (`rust.yaml`, `unawaited_async`).
    fn mark_discarded(&mut self, e: &Expr) {
        let mut cur = e;
        loop {
            match cur {
                Expr::Paren(p) => cur = &p.expr,
                Expr::Call(c) => {
                    self.discarded.insert(self.offset(c.span()));
                    return;
                }
                Expr::MethodCall(m) => {
                    self.discarded.insert(self.offset(m.span()));
                    cur = &m.receiver;
                }
                _ => return,
            }
        }
    }

    fn walk_expr(&mut self, e: &Expr) {
        let mut v = Walker { ex: self };
        v.visit_expr(e);
    }

    // ----------------------------------------------------------------- calls --- //

    fn record_call(&mut self, expr: &str, line: i64, at_boundary: bool, args: Vec<CallArg>) -> (String, String) {
        let caller = self.owner_id();
        let key = format!("{caller}\0{expr}");
        let ord = self.call_ord.entry(key).or_insert(0);
        let ordinal = *ord;
        *ord += 1;
        let site_id = call_site_id(&caller, expr, ordinal);
        self.facts.calls.push(CallSite {
            caller_id: caller.clone(),
            callee_expr: expr.to_owned(),
            line,
            site_id: site_id.clone(),
            // Rule 2: a call that touches a boundary is never also an internal edge.
            at_boundary,
            args,
            ..Default::default()
        });
        (caller, site_id)
    }

    fn call(&mut self, expr: String, kind: SiteKind, path: Vec<String>, span: Span, args: &[&Expr]) {
        if expr.is_empty() {
            return;
        }
        let line = self.line(span);
        let rule = self.rules.match_call(&expr).cloned();
        let call_args: Vec<CallArg> = args.iter().enumerate()
            .map(|(i, a)| CallArg { idx: i as i64, expr: self.text(a.span()), ..Default::default() })
            .collect();
        // **A bare call to a name this routine binds is a call to that binding** — a
        // closure, a function pointer, a parameter — and never to a function elsewhere
        // that shares the name (`CallSite.bound_locally`, schema 16).
        let bound = kind == SiteKind::Path && path.len() == 1
            && self.locals.last().is_some_and(|l| l.contains(&path[0]));
        let (caller, site_id) = self.record_call(&expr, line, rule.is_some(), call_args);
        if bound {
            if let Some(c) = self.facts.calls.last_mut() {
                c.bound_locally = true;
            }
        }
        if let Some(rule) = &rule {
            let target = self.target(args, rule);
            let mut hit = BoundaryHit {
                routine_id: caller.clone(),
                kind: boundary_kind(&rule.kind),
                direction: direction(&rule.direction),
                target,
                line,
                evidence: expr.clone(),
                ..Default::default()
            };
            if rule.salience != "normal" {
                hit.salience = rule.salience.clone();
            }
            self.facts.boundaries.push(hit);
        }
        self.network(&expr, line, args, span);
        self.sites.push(Site {
            site_id,
            caller_id: caller,
            kind,
            path,
            mod_path: self.mod_path.clone(),
            self_type: self.imp.as_ref().map(|(t, _)| t.clone()),
            at_boundary: rule.is_some(),
            bound_locally: bound,
        });
    }

    fn target(&self, args: &[&Expr], rule: &BoundaryRule) -> String {
        let Some(idx) = rule.target_arg else { return String::new() };
        let Some(a) = args.get(idx as usize) else { return String::new() };
        match string_value(a) {
            Some(s) => s,
            None => self.text(a.span()),
        }
    }

    fn network(&mut self, expr: &str, line: i64, args: &[&Expr], span: Span) {
        let Some(lib) = self.rules.match_network(expr).cloned() else { return };
        let last = expr.rsplit('.').next().unwrap_or(expr);
        let mut nc = NetworkCall {
            routine_id: self.owner_id(),
            expr: expr.to_owned(),
            protocol: lib.protocol.clone(),
            line,
            is_async: lib.is_async,
            in_async_routine: self.owner_async(),
            awaited: !self.discarded.contains(&self.offset(span)),
            ..Default::default()
        };
        if self.rules.verbs.iter().any(|v| v.eq_ignore_ascii_case(last)) {
            nc.verb = last.to_ascii_uppercase();
        }
        if let Some(a) = args.first() {
            nc.destination = string_value(a).unwrap_or_else(|| self.text(a.span()));
        }
        self.facts.network.push(nc);
    }

    /// A macro invocation. Its arguments are read as expressions where they parse as
    /// a comma-separated list — `format!`, `vec!`, `assert!`, and DunneNote's own
    /// `with_unlocked!(…)`, which wraps the dispatch calls — and left as tokens otherwise.
    fn mac(&mut self, m: &Macro, _in_expr: bool) {
        let name = dotted_path(&m.path);
        let expr = format!("{name}!");
        let parsed = m.parse_body_with(Punctuated::<Expr, Token![,]>::parse_terminated);
        let args: Vec<Expr> = match parsed {
            Ok(p) => p.into_iter().collect(),
            Err(_) => {
                // `vec![x; n]`, `matches!(x, Pat)` and the rest: the leading expression is
                // still code, and is read where it stands alone.
                m.parse_body_with(|input: syn::parse::ParseStream| {
                    let e: Expr = input.parse()?;
                    let _ = input.parse::<proc_macro2::TokenStream>();
                    Ok(vec![e])
                }).unwrap_or_default()
            }
        };
        let refs: Vec<&Expr> = args.iter().collect();
        let path: Vec<String> = m.path.segments.iter().map(|s| s.ident.to_string()).collect();
        self.call(expr, SiteKind::Macro, path, m.span(), &refs);
        for a in &args {
            self.walk_expr(a);
        }
    }

    // --------------------------------------------------------------- strings --- //

    fn literal(&mut self, s: &syn::LitStr) {
        let text = s.value();
        let n = text.chars().count();
        if !(LITERAL_MIN..=LITERAL_MAX).contains(&n) {
            self.facts.literals_dropped += 1;
            return;
        }
        let rid = self.owner_id();
        self.facts.literals.push(StringLiteral { routine_id: rid, line: self.line(s.span()), text, ..Default::default() });
    }

    // --------------------------------------------------------------- control --- //

    #[allow(clippy::too_many_arguments)]
    fn add_point(&mut self, span: Span, kind: ControlKind, header: String, word: &str, arms: i64,
                 exits: &str, once: (i64, i64)) -> (String, String) {
        let rid = self.owner_id();
        let key = format!("{rid}\0{}\0{header}", kind.as_str());
        let ord = self.ctrl_ord.entry(key).or_insert(0);
        let ordinal = *ord;
        *ord += 1;
        let pid = control_point_id(&rid, kind.as_str(), &header, ordinal);
        self.facts.control.push(ControlPoint {
            point_id: pid.clone(),
            routine_id: rid.clone(),
            kind,
            line_start: self.line(span),
            line_end: self.end_line(span),
            depth: self.depth,
            header,
            arms: if arms != 1 { arms } else { 0 },
            exits: exits.to_owned(),
            word: word.to_owned(),
            once_start: once.0,
            once_end: once.1,
        });
        (pid, rid)
    }

    fn add_arm(&mut self, p: &(String, String), idx: i64, kind: ArmKind, span: Span, header: String) {
        self.facts.control_arms.push(ControlArm {
            point_id: p.0.clone(),
            routine_id: p.1.clone(),
            idx,
            kind,
            line_start: self.line(span),
            line_end: self.end_line(span),
            header,
        });
    }

    /// The lines a loop evaluates once before its first pass: the evaluated part minus
    /// every line the body also occupies (`extract.ts:onceRange`).
    fn once(&self, evaluated: Span, body: Span) -> (i64, i64) {
        let (start, mut end) = (self.line(evaluated), self.end_line(evaluated));
        let b = self.line(body);
        if b <= end {
            end = b - 1;
        }
        if end >= start { (start, end) } else { (0, 0) }
    }

    fn if_ladder(&mut self, s: &syn::ExprIf) {
        let mut rungs = vec![s];
        let mut tail: Option<&Expr> = None;
        let mut cur = s;
        while let Some((_, e)) = &cur.else_branch {
            match &**e {
                Expr::If(next) => {
                    rungs.push(next);
                    cur = next;
                }
                other => {
                    tail = Some(other);
                    break;
                }
            }
        }
        let exits = if rungs.len() == 1 && tail.is_none() { leaves_with(&s.then_branch) } else { "" };
        let kind = if exits.is_empty() { ControlKind::Decision } else { ControlKind::Guard };
        let arms = rungs.len() as i64 + tail.is_some() as i64;
        let header = self.text(s.cond.span());
        let p = self.add_point(s.span(), kind, header, "if", arms, exits, (0, 0));
        for (i, r) in rungs.iter().enumerate() {
            let k = if i == 0 { ArmKind::If } else { ArmKind::ElseIf };
            let h = self.text(r.cond.span());
            self.add_arm(&p, i as i64, k, r.then_branch.span(), h);
        }
        if let Some(t) = tail {
            self.add_arm(&p, rungs.len() as i64, ArmKind::Else, t.span(), String::new());
        }
        self.depth += 1;
        for r in &rungs {
            self.walk_expr(&r.cond);
            self.block_body(&r.then_branch);
        }
        if let Some(t) = tail {
            self.walk_expr(t);
        }
        self.depth -= 1;
    }

    /// `let Ok(x) = f() else { return … };` is a guard: the test, and how it leaves.
    fn let_else(&mut self, l: &syn::Local, init: &Expr, diverge: &Expr) {
        let header = format!("let {} = {}", self.text(l.pat.span()), self.text(init.span()));
        let exits = match diverge {
            Expr::Block(b) => leaves_with(&b.block),
            _ => "",
        };
        let p = self.add_point(l.span(), ControlKind::Guard, header, "let else", 1, exits, (0, 0));
        self.add_arm(&p, 0, ArmKind::Else, diverge.span(), String::new());
        self.walk_expr(init);
        self.depth += 1;
        self.walk_expr(diverge);
        self.depth -= 1;
    }
}

struct Walker<'e, 'a> {
    ex: &'e mut Ex<'a>,
}

impl<'ast> Visit<'ast> for Walker<'_, '_> {
    // Attributes hold `#[doc = "…"]` and `#[cfg(target_os = "…")]`: strings that are
    // documentation and configuration, never values the program moves.
    fn visit_attribute(&mut self, _: &'ast Attribute) {}

    fn visit_item(&mut self, i: &'ast Item) {
        self.ex.item(i);
    }

    fn visit_block(&mut self, b: &'ast syn::Block) {
        self.ex.block_body(b);
    }

    fn visit_expr_call(&mut self, c: &'ast syn::ExprCall) {
        let (expr, path) = callee(&c.func);
        let args: Vec<&Expr> = c.args.iter().collect();
        self.ex.call(expr, SiteKind::Path, path, c.span(), &args);
        // The callee is walked too: `f(x)(y)` holds the call `f`, and a closure called
        // where it is written belongs to the routine around it.
        self.visit_expr(&c.func);
        for a in &c.args {
            self.visit_expr(a);
        }
    }

    fn visit_expr_method_call(&mut self, m: &'ast syn::ExprMethodCall) {
        let base = receiver(&m.receiver);
        let expr = if base.is_empty() { String::new() } else { format!("{base}.{}", m.method) };
        let kind = if is_self(&m.receiver) { SiteKind::SelfMethod } else { SiteKind::Method };
        let args: Vec<&Expr> = m.args.iter().collect();
        self.ex.call(expr, kind, vec![m.method.to_string()], m.span(), &args);
        self.visit_expr(&m.receiver);
        for a in &m.args {
            self.visit_expr(a);
        }
    }

    fn visit_macro(&mut self, m: &'ast Macro) {
        self.ex.mac(m, true);
    }

    fn visit_lit_str(&mut self, s: &'ast syn::LitStr) {
        self.ex.literal(s);
    }

    fn visit_expr_if(&mut self, s: &'ast syn::ExprIf) {
        self.ex.if_ladder(s);
    }

    fn visit_expr_for_loop(&mut self, s: &'ast syn::ExprForLoop) {
        let header = format!("{} in {}", self.ex.text(s.pat.span()), self.ex.text(s.expr.span()));
        // The iterated expression is evaluated once.
        let once = self.ex.once(s.expr.span(), s.body.span());
        let p = self.ex.add_point(s.span(), ControlKind::Loop, header, "for", 1, "", once);
        self.ex.add_arm(&p, 0, ArmKind::For, s.body.span(), String::new());
        self.ex.depth += 1;
        self.visit_expr(&s.expr);
        self.ex.block_body(&s.body);
        self.ex.depth -= 1;
    }

    fn visit_expr_while(&mut self, s: &'ast syn::ExprWhile) {
        let header = self.ex.text(s.cond.span());
        let p = self.ex.add_point(s.span(), ControlKind::Loop, header, "while", 1, "", (0, 0));
        self.ex.add_arm(&p, 0, ArmKind::While, s.body.span(), String::new());
        self.ex.depth += 1;
        self.visit_expr(&s.cond);
        self.ex.block_body(&s.body);
        self.ex.depth -= 1;
    }

    fn visit_expr_loop(&mut self, s: &'ast syn::ExprLoop) {
        let p = self.ex.add_point(s.span(), ControlKind::Loop, String::new(), "loop", 1, "", (0, 0));
        self.ex.add_arm(&p, 0, ArmKind::While, s.body.span(), String::new());
        self.ex.depth += 1;
        self.ex.block_body(&s.body);
        self.ex.depth -= 1;
    }

    fn visit_expr_match(&mut self, s: &'ast syn::ExprMatch) {
        let header = self.ex.text(s.expr.span());
        let arms = s.arms.len().max(1) as i64;
        let p = self.ex.add_point(s.span(), ControlKind::Decision, header, "match", arms, "", (0, 0));
        for (i, a) in s.arms.iter().enumerate() {
            let wild = matches!(a.pat, Pat::Wild(_)) && a.guard.is_none();
            let kind = if wild { ArmKind::Default } else { ArmKind::Case };
            let mut h = if wild { String::new() } else { self.ex.text(a.pat.span()) };
            if let Some((_, g)) = &a.guard {
                h = format!("{h} if {}", self.ex.text(g.span()));
            }
            self.ex.add_arm(&p, i as i64, kind, a.span(), h);
        }
        self.visit_expr(&s.expr);
        self.ex.depth += 1;
        for a in &s.arms {
            if let Some((_, g)) = &a.guard {
                self.visit_expr(g);
            }
            self.visit_expr(&a.body);
        }
        self.ex.depth -= 1;
    }

    fn visit_expr_struct(&mut self, s: &'ast syn::ExprStruct) {
        // Not a call (see the header); its field values are still code.
        for f in &s.fields {
            self.visit_expr(&f.expr);
        }
        if let Some(rest) = &s.rest {
            self.visit_expr(rest);
        }
    }

    fn visit_stmt(&mut self, s: &'ast Stmt) {
        match s {
            Stmt::Macro(m) => self.ex.mac(&m.mac, false),
            other => visit::visit_stmt(self, other),
        }
    }
}

// ------------------------------------------------------------------ helpers --- //

/// Every name a `let` (or a closure's parameter) binds anywhere in a body, not descending
/// into nested items, which are routines of their own.
fn collect_lets(b: &syn::Block, out: &mut HashSet<String>) {
    struct Lets<'o>(&'o mut HashSet<String>);
    impl<'ast> Visit<'ast> for Lets<'_> {
        fn visit_item(&mut self, _: &'ast Item) {}
        fn visit_pat_ident(&mut self, p: &'ast syn::PatIdent) {
            self.0.insert(p.ident.to_string());
            visit::visit_pat_ident(self, p);
        }
    }
    Lets(out).visit_block(b);
}

fn item_attrs(item: &Item) -> Option<&[Attribute]> {
    Some(match item {
        Item::Fn(i) => &i.attrs,
        Item::Impl(i) => &i.attrs,
        Item::Mod(i) => &i.attrs,
        Item::Struct(i) => &i.attrs,
        Item::Enum(i) => &i.attrs,
        Item::Trait(i) => &i.attrs,
        Item::Use(i) => &i.attrs,
        Item::Const(i) => &i.attrs,
        Item::Static(i) => &i.attrs,
        Item::Type(i) => &i.attrs,
        Item::Union(i) => &i.attrs,
        Item::Macro(i) => &i.attrs,
        _ => return None,
    })
}

/// A routine's first line is its `pub` where it has one, else its signature — never its
/// attributes, which `Spanned` would include and which belong to nobody's body.
fn vis_or(vis: &Visibility, sig: Span) -> Span {
    match vis {
        Visibility::Inherited => sig,
        v => v.span(),
    }
}

/// `///` lines, which reach here as `#[doc = "…"]`, joined and trimmed.
pub fn docs(attrs: &[Attribute]) -> Option<String> {
    let mut lines = Vec::new();
    for a in attrs {
        if !a.path().is_ident("doc") {
            continue;
        }
        if let Meta::NameValue(nv) = &a.meta {
            if let Some(s) = string_value(&nv.value) {
                lines.push(s.strip_prefix(' ').unwrap_or(&s).trim_end().to_owned());
            }
        }
    }
    let joined = lines.join("\n").trim().to_owned();
    if joined.is_empty() { None } else { Some(joined) }
}

fn string_value(e: &Expr) -> Option<String> {
    match e {
        Expr::Lit(l) => match &l.lit {
            Lit::Str(s) => Some(s.value()),
            _ => None,
        },
        _ => None,
    }
}

/// A path as the dotted contract spells it: `::` read as `.`, a leading `::` dropped, and
/// no type arguments (clause 6).
fn dotted_path(p: &syn::Path) -> String {
    p.segments.iter().map(|s| s.ident.to_string()).collect::<Vec<_>>().join(".")
}

/// The callee of `f(…)`, as the contract spells it, and its path segments.
fn callee(func: &Expr) -> (String, Vec<String>) {
    match func {
        Expr::Path(p) if p.qself.is_none() => {
            let segs: Vec<String> = p.path.segments.iter().map(|s| s.ident.to_string()).collect();
            (segs.join("."), segs)
        }
        // `(self.handler)(x)` and `(f)(x)`: the name inside.
        Expr::Paren(p) => callee(&p.expr),
        Expr::Field(_) => (receiver(func), Vec::new()),
        // Clause 2: `f(x)(y)` folds to `f`.
        Expr::Call(c) => callee(&c.func),
        // Clause 3: a literal, a closure, a `<T as Trait>::f` — no name at the root without
        // resolving something, and `""` is never matched against a rule.
        _ => (String::new(), Vec::new()),
    }
}

/// The receiver of `x.m(…)`, as the contract spells it.
fn receiver(e: &Expr) -> String {
    match e {
        Expr::Path(p) if p.qself.is_none() => dotted_path(&p.path),
        Expr::Field(f) => {
            let base = receiver(&f.base);
            if base.is_empty() {
                return String::new();
            }
            match &f.member {
                Member::Named(n) => format!("{base}.{n}"),
                Member::Unnamed(i) => format!("{base}.{}", i.index),
            }
        }
        // Clause 2: a call in the middle folds to its callee.
        Expr::Call(c) => callee(&c.func).0,
        Expr::MethodCall(m) => {
            let base = receiver(&m.receiver);
            if base.is_empty() { String::new() } else { format!("{base}.{}", m.method) }
        }
        Expr::Macro(m) => format!("{}!", dotted_path(&m.mac.path)),
        // Clause 5's shape: `?`, `.await`, `&` and `*` say how a value is had, not which.
        Expr::Paren(p) => receiver(&p.expr),
        Expr::Try(t) => receiver(&t.expr),
        Expr::Await(a) => receiver(&a.base),
        Expr::Reference(r) => receiver(&r.expr),
        Expr::Unary(u) if matches!(u.op, syn::UnOp::Deref(_)) => receiver(&u.expr),
        _ => String::new(),
    }
}

fn is_self(e: &Expr) -> bool {
    matches!(e, Expr::Path(p) if p.qself.is_none() && p.path.is_ident("self"))
}

/// The named type an `impl` is for: `Foo`, `Foo<T>`, `&Foo` and `crate::x::Foo` are `Foo`.
fn type_name(t: &Type) -> Option<String> {
    match t {
        Type::Path(p) if p.qself.is_none() => p.path.segments.last().map(|s| s.ident.to_string()),
        Type::Reference(r) => type_name(&r.elem),
        Type::Paren(p) => type_name(&p.elem),
        Type::Group(g) => type_name(&g.elem),
        _ => None,
    }
}

/// Every leaf of a `use` tree as `(target path, local name)`. A glob's local name is `*`.
fn flatten_use(tree: &UseTree, prefix: &mut Vec<String>, out: &mut Vec<(Vec<String>, String)>) {
    match tree {
        UseTree::Path(p) => {
            prefix.push(p.ident.to_string());
            flatten_use(&p.tree, prefix, out);
            prefix.pop();
        }
        UseTree::Name(n) => {
            let name = n.ident.to_string();
            if name == "self" {
                // `use a::b::{self}` names `b`.
                if let Some(last) = prefix.last().cloned() {
                    out.push((prefix.clone(), last));
                }
            } else {
                let mut t = prefix.clone();
                t.push(name.clone());
                out.push((t, name));
            }
        }
        UseTree::Rename(r) => {
            let mut t = prefix.clone();
            let name = r.ident.to_string();
            if name != "self" {
                t.push(name);
            }
            out.push((t, r.rename.to_string()));
        }
        UseTree::Glob(_) => out.push((prefix.clone(), "*".into())),
        UseTree::Group(g) => {
            for t in &g.items {
                flatten_use(t, prefix, out);
            }
        }
    }
}

/// How a one-armed decision leaves, read off its last statement: `if x { return }` and
/// `if x { panic!() }` are the same sentence and opposite facts.
fn leaves_with(b: &syn::Block) -> &'static str {
    let Some(last) = b.stmts.last() else { return "" };
    let e = match last {
        Stmt::Expr(e, _) => e,
        Stmt::Macro(m) => {
            return macro_exit(&m.mac);
        }
        _ => return "",
    };
    match e {
        Expr::Return(_) => "return",
        Expr::Break(_) => "break",
        Expr::Continue(_) => "continue",
        Expr::Macro(m) => macro_exit(&m.mac),
        Expr::Call(c) => match callee(&c.func).0.as_str() {
            "std.process.exit" | "process.exit" | "exit" => "exit",
            _ => "",
        },
        _ => "",
    }
}

fn macro_exit(m: &Macro) -> &'static str {
    match dotted_path(&m.path).as_str() {
        "panic" | "unreachable" | "todo" | "unimplemented" => "panic",
        _ => "",
    }
}

fn boundary_kind(s: &str) -> BoundaryKind {
    match s {
        "ENV" => BoundaryKind::Env,
        "FILE" => BoundaryKind::File,
        "PROCESS" => BoundaryKind::Process,
        "NETWORK" => BoundaryKind::Network,
        "DATABASE" => BoundaryKind::Database,
        "QUEUE" => BoundaryKind::Queue,
        "STDIO" => BoundaryKind::Stdio,
        "CLOUD_SDK" => BoundaryKind::CloudSdk,
        "LLM_API" => BoundaryKind::LlmApi,
        "CRYPTO" => BoundaryKind::Crypto,
        // The host validated the rules file; an unknown kind cannot arrive.
        other => panic!("detectors/rust.yaml names a boundary kind this reader does not know: {other}"),
    }
}

fn direction(s: &str) -> Direction {
    match s {
        "IN" => Direction::In,
        "OUT" => Direction::Out,
        _ => Direction::Both,
    }
}

// ----------------------------------------------------------------- comments --- //

impl Ex<'_> {
    /// Every comment that is not documentation lands on the innermost routine whose span
    /// holds it, and the module scope owns what no function does (rule 18).
    fn land_comments(&mut self) {
        for c in comments::scan(self.src) {
            let mut home: Option<usize> = None;
            for (i, r) in self.routines.iter().enumerate() {
                if r.line_start <= c.line && c.line <= r.line_end
                    && home.map_or(true, |h| r.line_start >= self.routines[h].line_start)
                {
                    home = Some(i);
                }
            }
            let comment = Comment { text: c.text, line: c.line, leading: c.leading };
            match home {
                Some(i) => self.routines[i].comments.push(comment),
                None => {
                    self.module_claimed = true;
                    self.module_scope.comments.push(comment);
                }
            }
        }
    }
}
