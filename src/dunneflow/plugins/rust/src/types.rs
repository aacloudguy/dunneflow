//! What a receiver's type is, where the source writes it down — and nothing more.
//!
//! **Not inference.** A type checker works a value's type out; this reads the types a
//! program *declares* and follows them one definition at a time: a parameter's annotation,
//! a `let x: T`, a struct's field, a function's `-> T`, a constructor `T::new(..)` or
//! `T { .. }`. `?`, `.unwrap()` and `.expect()` take the `Result` or `Option` off; `&`,
//! `Box`, `Rc` and `Arc` are seen through, because a method call auto-dereferences through
//! all of them. A closure's parameter, an iterator's item, a generic `T` and anything
//! else that would need the checker has no hint, and the call stays unknown (rule 1).
//!
//! **A name bound twice is trusted only if both bindings say the same thing.** The
//! hints are collected over the whole routine, not per block, so `let x = a(); … let x =
//! b();` gives `x` no hint at all rather than whichever came last.
//!
//! A hint is a description, resolved later by `edges.rs` against the program's own
//! definitions, because what `T` names depends on the `use`s of the module it is written
//! in and those are only all known once every file is read.

use std::collections::HashMap;

use syn::visit::{self, Visit};
use syn::{Expr, GenericArgument, Item, Member, Pat, PathArguments, Type, TypeParamBound};

#[derive(Debug, Clone, PartialEq)]
pub enum Hint {
    /// A type path as written, with its type arguments.
    Ty { segs: Vec<String>, args: Vec<Hint> },
    /// `dyn Trait` / `impl Trait`.
    Dyn(Vec<String>),
    /// What a path call returns: `T::new(..)`, `open(..)`.
    Ret(Vec<String>),
    /// What a method returns, called on a value with this hint.
    RetM(Box<Hint>, String),
    /// A field of a value with this hint.
    Field(Box<Hint>, String),
    /// `?`, `.unwrap()`, `.expect()`: the `Result`'s or `Option`'s first argument.
    Unwrap(Box<Hint>),
    /// The type of the `impl` this is written in.
    SelfTy,
}

/// Smart pointers a method call sees through.
const THROUGH: &[&str] = &["Box", "Rc", "Arc"];

pub fn type_hint(t: &Type) -> Option<Hint> {
    match t {
        Type::Reference(r) => type_hint(&r.elem),
        Type::Paren(p) => type_hint(&p.elem),
        Type::Group(g) => type_hint(&g.elem),
        Type::Path(p) if p.qself.is_none() => {
            let segs: Vec<String> = p.path.segments.iter().map(|s| s.ident.to_string()).collect();
            if segs == ["Self"] {
                return Some(Hint::SelfTy);
            }
            let last = p.path.segments.last()?;
            let args: Vec<Hint> = match &last.arguments {
                PathArguments::AngleBracketed(a) => a.args.iter().filter_map(|g| match g {
                    GenericArgument::Type(t) => Some(type_hint(t).unwrap_or(Hint::Ty { segs: Vec::new(), args: Vec::new() })),
                    _ => None,
                }).collect(),
                _ => Vec::new(),
            };
            if THROUGH.contains(&last.ident.to_string().as_str()) && args.len() == 1 {
                return Some(args.into_iter().next().unwrap());
            }
            Some(Hint::Ty { segs, args })
        }
        Type::TraitObject(o) => first_bound(o.bounds.iter()),
        Type::ImplTrait(i) => first_bound(i.bounds.iter()),
        _ => None,
    }
}

fn first_bound<'a>(mut bounds: impl Iterator<Item = &'a TypeParamBound>) -> Option<Hint> {
    bounds.find_map(|b| match b {
        TypeParamBound::Trait(t) => Some(Hint::Dyn(t.path.segments.iter().map(|s| s.ident.to_string()).collect())),
        _ => None,
    })
}

/// Methods that hand back the value they were called on, or the same type.
const SAME: &[&str] = &["clone", "to_owned", "borrow", "borrow_mut", "as_ref", "as_mut"];
const UNWRAPS: &[&str] = &["unwrap", "expect", "unwrap_or_default", "unwrap_unchecked"];

pub fn expr_hint(e: &Expr, locals: &HashMap<String, Option<Hint>>) -> Option<Hint> {
    match e {
        Expr::Path(p) if p.qself.is_none() => {
            if p.path.is_ident("self") {
                return Some(Hint::SelfTy);
            }
            let id = p.path.get_ident()?.to_string();
            locals.get(&id).cloned().flatten()
        }
        Expr::Field(f) => match &f.member {
            Member::Named(n) => Some(Hint::Field(Box::new(expr_hint(&f.base, locals)?), n.to_string())),
            Member::Unnamed(i) => Some(Hint::Field(Box::new(expr_hint(&f.base, locals)?), i.index.to_string())),
        },
        Expr::Call(c) => match &*c.func {
            Expr::Path(p) if p.qself.is_none() => {
                Some(Hint::Ret(p.path.segments.iter().map(|s| s.ident.to_string()).collect()))
            }
            _ => None,
        },
        Expr::MethodCall(m) => {
            let recv = expr_hint(&m.receiver, locals)?;
            let name = m.method.to_string();
            if UNWRAPS.contains(&name.as_str()) {
                Some(Hint::Unwrap(Box::new(recv)))
            } else if SAME.contains(&name.as_str()) {
                Some(recv)
            } else {
                Some(Hint::RetM(Box::new(recv), name))
            }
        }
        Expr::Try(t) => Some(Hint::Unwrap(Box::new(expr_hint(&t.expr, locals)?))),
        // An `async fn` declares the type its future resolves to, so `.await` on a call
        // to one has the call's declared type.
        Expr::Await(a) => expr_hint(&a.base, locals),
        Expr::Paren(p) => expr_hint(&p.expr, locals),
        Expr::Reference(r) => expr_hint(&r.expr, locals),
        Expr::Unary(u) if matches!(u.op, syn::UnOp::Deref(_)) => expr_hint(&u.expr, locals),
        Expr::Struct(s) if s.qself.is_none() => Some(Hint::Ty {
            segs: s.path.segments.iter().map(|s| s.ident.to_string()).collect(),
            args: Vec::new(),
        }),
        Expr::Cast(c) => type_hint(&c.ty),
        _ => None,
    }
}

/// Every name a routine binds, with its hint where every binding of it agrees. Parameters
/// first; then each `let`, in order, so `let a = A::new(); let b = a.make();` reads
/// `b` through `a`. Every other binding — a `for` pattern, a `match` arm, a closure's
/// parameter, `if let` — binds a name with no hint. Nested items are routines of their own
/// and are not entered.
pub fn bindings(params: &[(String, Option<Hint>)], body: &syn::Block) -> HashMap<String, Option<Hint>> {
    struct B {
        seen: HashMap<String, Vec<Option<Hint>>>,
    }
    impl B {
        fn current(&self) -> HashMap<String, Option<Hint>> {
            self.seen.iter().map(|(k, v)| (k.clone(), agree(v))).collect()
        }
        fn bind(&mut self, name: String, h: Option<Hint>) {
            self.seen.entry(name).or_default().push(h);
        }
    }
    impl<'ast> Visit<'ast> for B {
        fn visit_item(&mut self, _: &'ast Item) {}
        fn visit_local(&mut self, l: &'ast syn::Local) {
            if let Some(init) = &l.init {
                self.visit_expr(&init.expr);
                if let Some((_, d)) = &init.diverge {
                    self.visit_expr(d);
                }
            }
            match &l.pat {
                Pat::Ident(pi) if pi.subpat.is_none() => {
                    let h = l.init.as_ref().and_then(|i| expr_hint(&i.expr, &self.current()));
                    // `let Ok(x) = f() else { .. }` is a pattern, not this arm.
                    let h = if l.init.as_ref().is_some_and(|i| i.diverge.is_some()) { None } else { h };
                    self.bind(pi.ident.to_string(), h);
                }
                Pat::Type(pt) => match &*pt.pat {
                    Pat::Ident(pi) => self.bind(pi.ident.to_string(), type_hint(&pt.ty)),
                    other => self.visit_pat(other),
                },
                other => self.visit_pat(other),
            }
        }
        fn visit_pat_ident(&mut self, p: &'ast syn::PatIdent) {
            self.bind(p.ident.to_string(), None);
            visit::visit_pat_ident(self, p);
        }
    }
    let mut b = B { seen: HashMap::new() };
    for (name, h) in params {
        b.bind(name.clone(), h.clone());
    }
    b.visit_block(body);
    b.current()
}

fn agree(v: &[Option<Hint>]) -> Option<Hint> {
    let first = v.first()?.clone()?;
    v.iter().all(|h| h.as_ref() == Some(&first)).then_some(first)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn body(src: &str) -> HashMap<String, Option<Hint>> {
        let f: syn::ItemFn = syn::parse_str(src).unwrap();
        let params: Vec<(String, Option<Hint>)> = f.sig.inputs.iter().filter_map(|a| match a {
            syn::FnArg::Typed(pt) => match &*pt.pat {
                Pat::Ident(pi) => Some((pi.ident.to_string(), type_hint(&pt.ty))),
                _ => None,
            },
            _ => None,
        }).collect();
        bindings(&params, &f.block)
    }

    fn ty(s: &str) -> Hint {
        Hint::Ty { segs: s.split("::").map(str::to_owned).collect(), args: Vec::new() }
    }

    #[test]
    fn declared_types_are_read_and_inference_is_not_attempted() {
        let b = body("fn f(tx: &rusqlite::Transaction, s: Arc<Store>, n: u8) {
            let a = Store::open();
            let c: Conn = make();
            let d = a.conn()?;
            let e = Thing { x: 1 };
            for row in rows { }
            let twice = A::new();
            let twice = B::new();
            let g = |x| x;
        }");
        assert_eq!(b["tx"], Some(ty("rusqlite::Transaction")));
        assert_eq!(b["s"], Some(ty("Store")), "Arc is seen through");
        assert_eq!(b["a"], Some(Hint::Ret(vec!["Store".into(), "open".into()])));
        assert_eq!(b["c"], Some(ty("Conn")));
        assert_eq!(b["d"], Some(Hint::Unwrap(Box::new(Hint::RetM(
            Box::new(Hint::Ret(vec!["Store".into(), "open".into()])), "conn".into())))));
        assert_eq!(b["e"], Some(ty("Thing")));
        assert_eq!(b["row"], None, "an iterator's item needs the checker");
        assert_eq!(b["twice"], None, "two bindings that disagree give no hint");
        assert_eq!(b["g"], None, "a closure is not a type");
    }
}
