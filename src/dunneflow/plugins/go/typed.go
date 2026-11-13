// What a receiver is, asked of `go/types` over one file and the packages `go.yaml`
// declares, and nothing else.
//
// **Why a method needs its receiver's type.** `r.ReadFile(name)` is a file read when `r` is
// an `*os.Root` and nobody's business when `r` is a type of the program's own with a method
// of that name. A bare method name cannot tell them apart (rule 5), and a variable's name
// is a label, not a type (rule 30). Since Go 1.24 `os.Root` is how code that must not
// follow a symlink out of a folder reads and writes, so the gap hid exactly the file
// boundaries that matter most (Comitia2, `internal/cli/project_folder.go`, 2026-11-07).
//
// **Checked against declarations, never against GOROOT, and that is the cache key.** A
// file's facts are cached under its own hash and the reader's stamp, and the stamp does
// not carry the toolchain (rule 81): facts read against the standard library of whatever
// Go is installed would change with a `brew upgrade` and nothing would notice, and putting
// the toolchain in the stamp would make every Go row stale on a machine with no Go at all,
// which a writable open discards. So the packages a typed rule needs are declared in
// `go.yaml` under `typed_packages`, as Go source with no bodies, and the answer depends on
// the file and the rules and nothing else. The API they declare is Go 1's promise, so a
// declaration that is right once stays right.
//
// **One file, never its package, and that is rule 95.** A receiver whose type is declared
// in another file (a field of a struct defined there, a helper that returns `*os.Root`) is
// undefined here, so its methods are not typed and no row is recorded: a missed row, never
// a wrong one (rule 1). The edge pass, which checks the whole module, counts those calls
// and says how many there were (`edges.go`, `typedResidue`), so the residue is visible
// rather than silent (rule 38).
//
// **Only methods are named by their type.** A package function keeps the spelling the file
// writes (`os.Stat`, rule 4) and the checker is asked only whether a name taken as a value
// is a function at all, because `os.Stat` passed as an argument touches nothing until it is
// called and `embed.FS` written as a type is not a call of anything.

package main

import (
	"go/ast"
	"go/parser"
	"go/token"
	"go/types"
	"sort"
	"strconv"
	"strings"
)

// typing is one file's checked view: nil wherever the file imports none of the declared
// packages, which is most files, so most files cost nothing.
type typing struct {
	info     *types.Info
	declared map[string]bool
}

// typeFile checks one file against the declared packages. Every error is expected and
// survivable: everything outside the declarations is undefined, and only the selections
// whose receiver is a declared type are ever read.
func typeFile(fset *token.FileSet, file *ast.File, rules *Rules) *typing {
	if rules == nil || len(rules.TypedPackages) == 0 || file == nil {
		return nil
	}
	wanted := false
	for _, im := range file.Imports {
		if p, err := strconv.Unquote(im.Path.Value); err == nil {
			if _, ok := rules.TypedPackages[p]; ok {
				wanted = true
			}
		}
	}
	if !wanted {
		return nil
	}
	t := &typing{
		info: &types.Info{
			Uses:       map[*ast.Ident]types.Object{},
			Selections: map[*ast.SelectorExpr]*types.Selection{},
		},
		declared: map[string]bool{},
	}
	for p := range rules.TypedPackages {
		t.declared[p] = true
	}
	conf := types.Config{
		Importer:    &declaredImporter{fset: fset, rules: rules, pkgs: map[string]*types.Package{}},
		FakeImportC: true,
		Error:       func(error) {},
	}
	// A path no import can spell, so a package of the program's own that happens to be
	// called `os` is never mistaken for the declared one.
	name := "_"
	if file.Name != nil {
		name = file.Name.Name
	}
	conf.Check("dunneflow.local/file#"+name, fset, []*ast.File{file}, t.info)
	return t
}

// declaredImporter answers a declared package from its declaration and every other import
// with an empty package of the right name, as the edge pass answers a dependency it cannot
// see (`checker.ImportFrom`).
type declaredImporter struct {
	fset  *token.FileSet
	rules *Rules
	pkgs  map[string]*types.Package
}

func (d *declaredImporter) Import(path string) (*types.Package, error) {
	if p, ok := d.pkgs[path]; ok {
		return p, nil
	}
	var p *types.Package
	if src, ok := d.rules.TypedPackages[path]; ok {
		f, _ := parser.ParseFile(d.fset, "go.yaml:typed_packages:"+path, src,
			parser.SkipObjectResolution)
		if f != nil {
			conf := types.Config{Importer: d, Error: func(error) {}}
			p, _ = conf.Check(path, d.fset, []*ast.File{f}, nil)
		}
		if p == nil {
			note("go.yaml declares typed_packages[%s] and it does not parse as Go", path)
		}
	}
	if p == nil {
		name := path[strings.LastIndexByte(path, '/')+1:]
		if i := strings.IndexAny(name, ".-"); i > 0 {
			name = name[:i]
		}
		p = types.NewPackage(path, name)
		p.MarkComplete()
	}
	d.pkgs[path] = p
	return p, nil
}

// methodName is `os.Root.ReadFile` for a method of a declared type, and "" otherwise.
// Embedding is followed because the checker follows it: a struct that embeds `*os.Root`
// reads through `os.Root.ReadFile`, which is what its call does.
func methodName(fn *types.Func, declared map[string]bool) string {
	sig, ok := fn.Type().(*types.Signature)
	if !ok || sig.Recv() == nil {
		return ""
	}
	recv := sig.Recv().Type()
	if p, ok := recv.(*types.Pointer); ok {
		recv = p.Elem()
	}
	named, ok := recv.(*types.Named)
	if !ok || named.Obj().Pkg() == nil || !declared[named.Obj().Pkg().Path()] {
		return ""
	}
	return named.Obj().Pkg().Name() + "." + named.Obj().Name() + "." + fn.Name()
}

// method is what a selector names when it is a method of a declared type, and whether it
// is a method expression (`(*os.Root).Lchown`), whose first argument is the receiver.
func (t *typing) method(sel *ast.SelectorExpr) (name string, isExpr bool) {
	if t == nil || sel == nil {
		return "", false
	}
	s := t.info.Selections[sel]
	if s == nil || (s.Kind() != types.MethodVal && s.Kind() != types.MethodExpr) {
		return "", false
	}
	fn, ok := s.Obj().(*types.Func)
	if !ok {
		return "", false
	}
	return methodName(fn, t.declared), s.Kind() == types.MethodExpr
}

// isDeclaredFunc says whether `pkg.Name` is a function of a declared package: the one
// question asked of a package-level name taken as a value.
func (t *typing) isDeclaredFunc(sel *ast.SelectorExpr) bool {
	if t == nil || sel == nil {
		return false
	}
	fn, ok := t.info.Uses[sel.Sel].(*types.Func)
	if !ok || fn.Pkg() == nil || !t.declared[fn.Pkg().Path()] {
		return false
	}
	sig, ok := fn.Type().(*types.Signature)
	return ok && sig.Recv() == nil
}

// typedTypes is the declared types a typed rule names, for the residue's sentence:
// `os.Root`, `net.Dialer`. Declared, so `os.Stdout.Write`, which is a spelling and names no
// type, is not one of them.
func (r *Rules) typedTypes() []string {
	seen := map[string]bool{}
	for _, b := range r.Boundaries {
		for _, x := range b.Exact {
			if i := strings.LastIndexByte(x, '.'); i > 0 && r.typedType[x[:i]] {
				seen[x[:i]] = true
			}
		}
	}
	out := make([]string, 0, len(seen))
	for x := range seen {
		out = append(out, x)
	}
	sort.Strings(out)
	return out
}
