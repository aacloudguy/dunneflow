// Where each call goes, answered by `go/types` over the whole module.
//
// `plugins/typescript/src/edges.ts`'s job, for Go: the checker names the function a call
// reaches, and this reports it as a **location** (file, first line, name), never an id,
// because the host turns a location into an id and a plugin minting ids would be a second
// `make_id` where a disagreement is least recoverable (`resolve/supplied.py`).
//
// **Four answers, and three are honest forms of no.**
//
//   - A function or method of this program: a location the host will find a routine at.
//   - A call into the standard library, a dependency, or a builtin: `outside`. The call
//     happens and its far end is not in this map, which is what external means (rule 26).
//   - A call through an interface: ambiguous, with the number of types in the module that
//     implement it as `candidates`. Never guessed (rule 1).
//   - A call through a value the checker cannot follow to a declaration (a parameter, a
//     field, a closure): `unknown`. Left external, never matched by name.
//
// **Build constraints are answered deterministically, never by the machine reading.**
// `run_linux.go` and `run_windows.go` may both define `run`, and a reader that checked only
// the host's GOOS would draw a different map on each machine (rule 66). Each package is
// checked under a fixed set of targets and the answers are joined per call site.
//
// **Where the targets name different definitions, the edge goes to the reference
// target's**, which is the first of `targets`, linux/amd64, and the edge's `how` says how
// many variants there were. Decided by Tom on 2026-11-01, on beads: drawn as ambiguous,
// as the plan first said, a function defined once per platform cut every flow through
// it and raised 16 LOST_EDGE SUSPECT findings saying *anything downstream is missing*
// about Go that was correct. The residue is stated rather than hidden: the other
// platforms' variants are drawn uncalled. That is a fixed, documented choice, never the
// order a file happened to be read in (rule 100).
//
// **Nothing is downloaded.** The standard library is checked from GOROOT's own source, and
// a package outside the analysed tree is an empty stand-in: calls into it are counted as
// outside, and its absence is a diagnostic rather than a failure (design rule 14).

package main

import (
	"go/ast"
	"go/build"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
)

// targets is the fixed set every package is checked under. Fixed rather than the host's,
// so the map does not depend on the machine (rule 66); three because they are the three
// this tool itself ships for.
var targets = []struct{ goos, goarch string }{
	{"linux", "amd64"}, {"darwin", "arm64"}, {"windows", "amd64"},
}

type harvest struct {
	edges   []SuppliedEdge
	outside int
	unknown int
	notes   []string
}

// parsedFile is one file of the session, parsed once and walked by the extractor so its
// call nodes carry the site ids the facts pass minted.
type parsedFile struct {
	abs, rel string
	file     *ast.File
	ex       *extractor
}

// goModule is one `go.mod` under the analysed root.
type goModule struct {
	path, root string
}

type session struct {
	root    string
	fset    *token.FileSet
	rules   *Rules
	byAbs   map[string]*parsedFile
	byDir   map[string][]*parsedFile
	modules []goModule
	std     types.Importer
	notes   map[string]bool
	// Routines this reader minted, by where they start: the targets an edge may name.
	routines map[string]bool
}

func (s *session) note(msg string) { s.notes[msg] = true }

// goroot settles where the standard library's source is. Built with `-trimpath`, this
// program does not know its own GOROOT, so it asks the toolchain the host already found.
func goroot() string {
	if build.Default.GOROOT != "" {
		if _, err := os.Stat(filepath.Join(build.Default.GOROOT, "src", "fmt")); err == nil {
			return build.Default.GOROOT
		}
	}
	out, err := exec.Command("go", "env", "GOROOT").Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

func readModulePath(gomod string) string {
	raw, err := os.ReadFile(gomod)
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "module ") {
			return strings.Trim(strings.TrimSpace(strings.TrimPrefix(line, "module")), `"`)
		}
	}
	return ""
}

// findModules is every `go.mod` that governs a file of the session: the nearest one above
// each file, up to the root and no further (rule 108).
func (s *session) findModules() {
	seen := map[string]bool{}
	for dir := range s.byDir {
		for d := dir; ; d = filepath.Dir(d) {
			if seen[d] {
				break
			}
			gm := filepath.Join(d, "go.mod")
			if _, err := os.Stat(gm); err == nil {
				seen[d] = true
				if mp := readModulePath(gm); mp != "" {
					s.modules = append(s.modules, goModule{path: mp, root: d})
				}
				break
			}
			if d == s.root || filepath.Dir(d) == d || !strings.HasPrefix(d, s.root) {
				break
			}
		}
	}
	// Longest module path first, so a nested module answers for its own imports.
	sort.Slice(s.modules, func(i, j int) bool {
		if len(s.modules[i].path) != len(s.modules[j].path) {
			return len(s.modules[i].path) > len(s.modules[j].path)
		}
		return s.modules[i].path < s.modules[j].path
	})
}

// dirOf is the directory an import path names inside this tree, or "" when it is not one
// of this tree's packages.
func (s *session) dirOf(path string) string {
	for _, m := range s.modules {
		if path == m.path {
			return m.root
		}
		if strings.HasPrefix(path, m.path+"/") {
			return filepath.Join(m.root, filepath.FromSlash(strings.TrimPrefix(path, m.path+"/")))
		}
	}
	return ""
}

func isStd(path string) bool {
	first, _, _ := strings.Cut(path, "/")
	return !strings.Contains(first, ".") && path != "C"
}

// ctxFor is a build context for one target, with cgo off: a reader cannot run cgo, and the
// pure-Go files are the ones every target can read.
func ctxFor(goos, goarch string) build.Context {
	c := build.Default
	c.GOOS, c.GOARCH, c.CgoEnabled = goos, goarch, false
	return c
}

// filesFor is a package directory's files that one target compiles, of one package name.
// A directory the session did not open (one the host's rules skipped) is parsed from disk
// for its declarations, so an import into it still resolves.
func (s *session) filesFor(dir, pkg string, ctx build.Context) []*parsedFile {
	have := s.byDir[dir]
	if have == nil {
		entries, err := os.ReadDir(dir)
		if err != nil {
			return nil
		}
		for _, en := range entries {
			n := en.Name()
			if en.IsDir() || !strings.HasSuffix(n, ".go") || strings.HasSuffix(n, "_test.go") {
				continue
			}
			abs := filepath.Join(dir, n)
			src, err := readSource(abs)
			if err != nil {
				continue
			}
			f, _ := parser.ParseFile(s.fset, abs, src, parser.SkipObjectResolution)
			if f == nil {
				continue
			}
			pf := &parsedFile{abs: abs, file: f}
			s.byAbs[abs] = pf
			have = append(have, pf)
		}
		s.byDir[dir] = have
	}
	var out []*parsedFile
	for _, pf := range have {
		if pkg != "" && pf.file.Name.Name != pkg {
			continue
		}
		if ok, err := ctx.MatchFile(dir, filepath.Base(pf.abs)); err == nil && ok {
			out = append(out, pf)
		}
	}
	return out
}

// pkgName is the package a directory's ordinary files declare: the one that is not an
// external test package.
func pkgName(files []*parsedFile) string {
	counts := map[string]int{}
	for _, pf := range files {
		if n := pf.file.Name.Name; !strings.HasSuffix(n, "_test") {
			counts[n]++
		}
	}
	best := ""
	for n, c := range counts {
		if c > counts[best] || (c == counts[best] && n < best) {
			best = n
		}
	}
	return best
}

// checker is one target's view of the tree: every package of it, checked once.
type checker struct {
	s       *session
	ctx     build.Context
	pkgs    map[string]*types.Package
	busy    map[string]bool
	info    *types.Info
	fakes   map[string]*types.Package
	named   []*types.Named
	checked map[*ast.File]bool
}

func (c *checker) Import(path string) (*types.Package, error) {
	return c.ImportFrom(path, "", 0)
}

func (c *checker) ImportFrom(path, _ string, _ types.ImportMode) (*types.Package, error) {
	if p, ok := c.pkgs[path]; ok {
		return p, nil
	}
	if dir := c.s.dirOf(path); dir != "" {
		files := c.s.filesFor(dir, "", c.ctx)
		return c.check(path, dir, pkgName(files)), nil
	}
	if isStd(path) && c.s.std != nil {
		if p, err := c.s.std.Import(path); err == nil {
			c.pkgs[path] = p
			return p, nil
		}
	}
	// Outside this tree and outside the standard library: an empty stand-in, so the file
	// still checks and calls into it are counted as outside rather than lost.
	if p, ok := c.fakes[path]; ok {
		return p, nil
	}
	name := path[strings.LastIndexByte(path, '/')+1:]
	if i := strings.IndexAny(name, ".-"); i > 0 {
		name = name[:i]
	}
	p := types.NewPackage(path, name)
	p.MarkComplete()
	c.fakes[path] = p
	return p, nil
}

// check type-checks one package of this tree under this target.
func (c *checker) check(path, dir, name string) *types.Package {
	key := path
	if p, ok := c.pkgs[key]; ok {
		return p
	}
	if c.busy[key] {
		// An import cycle is not valid Go; the stand-in keeps the checker from recursing.
		return types.NewPackage(path, name)
	}
	c.busy[key] = true
	defer delete(c.busy, key)
	var files []*ast.File
	for _, pf := range c.s.filesFor(dir, name, c.ctx) {
		files = append(files, pf.file)
		c.checked[pf.file] = true
	}
	conf := types.Config{
		Importer:    c,
		FakeImportC: true,
		GoVersion:   "",
		// Errors are expected and survivable: a dependency that is a stand-in leaves
		// every use of it undefined, and the rest of the package still resolves.
		Error: func(error) {},
	}
	pkg, _ := conf.Check(path, c.s.fset, files, c.info)
	if pkg == nil {
		pkg = types.NewPackage(path, name)
	}
	c.pkgs[key] = pkg
	for _, n := range pkg.Scope().Names() {
		if tn, ok := pkg.Scope().Lookup(n).(*types.TypeName); ok {
			if nt, ok := tn.Type().(*types.Named); ok {
				if _, isIface := nt.Underlying().(*types.Interface); !isIface {
					c.named = append(c.named, nt)
				}
			}
		}
	}
	return pkg
}

// answer is what one target said about one call site.
type answer struct {
	file, name string
	line       int
	outside    bool
	candidates int
}

// implementers is how many named types of this tree implement an interface: the number a
// call through it could reach, which is reported and never chosen between (rule 1).
func (c *checker) implementers(iface *types.Interface) int {
	n := 0
	for _, t := range c.named {
		if types.Implements(t, iface) || types.Implements(types.NewPointer(t), iface) {
			n++
		}
	}
	return n
}

// resolve asks the checker where one call goes.
func (c *checker) resolve(call *ast.CallExpr) answer {
	var id *ast.Ident
	switch fun := ast.Unparen(call.Fun).(type) {
	case *ast.Ident:
		id = fun
	case *ast.SelectorExpr:
		id = fun.Sel
	case *ast.IndexExpr:
		id = identOf(fun.X)
	case *ast.IndexListExpr:
		id = identOf(fun.X)
	}
	if id == nil {
		return answer{}
	}
	obj := c.info.Uses[id]
	if obj == nil {
		// A selector whose package is a stand-in leaves its name undefined.
		if sel, ok := ast.Unparen(call.Fun).(*ast.SelectorExpr); ok {
			if x, ok := sel.X.(*ast.Ident); ok {
				if pn, ok := c.info.Uses[x].(*types.PkgName); ok && pn.Imported() != nil {
					return answer{outside: true}
				}
			}
		}
		return answer{}
	}
	switch o := obj.(type) {
	case *types.Builtin, *types.TypeName:
		// A builtin, or a conversion that is written as a call: nothing of this program.
		return answer{outside: true}
	case *types.Func:
		o = o.Origin()
		if sig, ok := o.Type().(*types.Signature); ok && sig.Recv() != nil {
			if iface, ok := sig.Recv().Type().Underlying().(*types.Interface); ok {
				return answer{candidates: c.implementers(iface)}
			}
		}
		return c.at(o.Pos(), o.Name())
	case *types.Var:
		// A function held in a variable is followed only to a routine this reader minted
		// there (`h := func() {...}`); a parameter or a field is `unknown`.
		a := c.at(o.Pos(), o.Name())
		if a.file != "" && c.s.routines[a.file+"\x00"+itoa(a.line)+"\x00"+a.name] {
			return a
		}
		return answer{}
	}
	return answer{}
}

func identOf(x ast.Expr) *ast.Ident {
	switch v := ast.Unparen(x).(type) {
	case *ast.Ident:
		return v
	case *ast.SelectorExpr:
		return v.Sel
	}
	return nil
}

// at turns a declaration's position into a location in this map, or `outside`.
func (c *checker) at(pos token.Pos, name string) answer {
	if !pos.IsValid() {
		return answer{outside: true}
	}
	p := c.s.fset.Position(pos)
	pf, ok := c.s.byAbs[p.Filename]
	if !ok || pf.rel == "" {
		return answer{outside: true}
	}
	return answer{file: pf.rel, line: p.Line, name: name}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b [20]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	return string(b[i:])
}

func collectEdges(root string, files []string, rules *Rules) harvest {
	var h harvest
	s := &session{root: root, fset: token.NewFileSet(), rules: rules,
		byAbs: map[string]*parsedFile{}, byDir: map[string][]*parsedFile{},
		notes: map[string]bool{}, routines: map[string]bool{}}

	// Every file of the session, parsed once and walked by the extractor, so each call
	// node carries the `site_id` the facts pass minted for it.
	sort.Strings(files)
	for _, f := range files {
		abs, err := filepath.Abs(f)
		if err != nil {
			continue
		}
		src, err := readSource(abs)
		if err != nil {
			continue
		}
		file, _ := parser.ParseFile(s.fset, abs, src, parser.ParseComments|parser.AllErrors)
		if file == nil {
			continue
		}
		rel, err := filepath.Rel(root, abs)
		if err != nil {
			rel = abs
		}
		rel = filepath.ToSlash(rel)
		ex := newExtractor(rel, src, s.fset, file, rules)
		ex.run()
		for _, r := range ex.routines {
			s.routines[r.File+"\x00"+itoa(r.LineStart)+"\x00"+r.Name] = true
		}
		pf := &parsedFile{abs: abs, rel: rel, file: file, ex: ex}
		s.byAbs[abs] = pf
		dir := filepath.Dir(abs)
		s.byDir[dir] = append(s.byDir[dir], pf)
	}
	s.findModules()
	if gr := goroot(); gr != "" {
		build.Default.GOROOT = gr
		build.Default.CgoEnabled = false
		s.std = importer.ForCompiler(s.fset, "source", nil)
	} else {
		s.note("no GOROOT was found, so every call into the standard library is unknown")
	}

	// One answer per site per target.
	answers := map[string][]answer{}
	siteOf := map[string]CallSite{}
	for _, t := range targets {
		c := &checker{s: s, ctx: ctxFor(t.goos, t.goarch), pkgs: map[string]*types.Package{},
			busy: map[string]bool{}, fakes: map[string]*types.Package{},
			checked: map[*ast.File]bool{},
			info:    &types.Info{Uses: map[*ast.Ident]types.Object{}}}
		dirs := make([]string, 0, len(s.byDir))
		for d := range s.byDir {
			dirs = append(dirs, d)
		}
		sort.Strings(dirs)
		for _, dir := range dirs {
			opened := []*parsedFile{}
			for _, pf := range s.byDir[dir] {
				if pf.ex != nil {
					opened = append(opened, pf)
				}
			}
			if len(opened) == 0 {
				continue
			}
			names := map[string]bool{}
			for _, pf := range opened {
				names[pf.file.Name.Name] = true
			}
			sorted := make([]string, 0, len(names))
			for n := range names {
				sorted = append(sorted, n)
			}
			sort.Strings(sorted)
			for _, name := range sorted {
				path := s.importPath(dir, name)
				c.check(path, dir, name)
			}
			for _, pf := range opened {
				if !c.checked[pf.file] {
					continue
				}
				for call, site := range pf.ex.sites {
					if site.AtBoundary {
						// Rule 2: a boundary call is never also an internal edge.
						continue
					}
					// Appended in `targets` order, which is what makes the first location
					// the reference target's (`join`).
					answers[site.SiteId] = append(answers[site.SiteId], c.resolve(call))
					siteOf[site.SiteId] = *site
				}
			}
		}
	}

	// Files no target compiles (`//go:build ignore`, a generator) have facts and no edges.
	never := 0
	for _, pf := range s.byAbs {
		if pf.ex == nil {
			continue
		}
		for _, site := range pf.ex.sites {
			if _, ok := answers[site.SiteId]; !ok && !site.AtBoundary {
				never++
			}
		}
	}
	if never > 0 {
		s.note(itoa(never) + " call(s) are in files no target compiles, and have no edge")
	}

	variants := 0
	ids := make([]string, 0, len(answers))
	for id := range answers {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		site := siteOf[id]
		e, kind := join(answers[id])
		switch kind {
		case "edge":
			e.SiteId, e.CallerId = id, site.CallerId
			if e.How == "" {
				e.How = "go/types"
			} else {
				variants++
			}
			h.edges = append(h.edges, e)
		case "ambiguous":
			e.SiteId, e.CallerId, e.How = id, site.CallerId, "go/types"
			h.edges = append(h.edges, e)
			h.unknown++
		case "outside":
			h.outside++
		default:
			h.unknown++
		}
	}
	if variants > 0 {
		s.note(itoa(variants) + " call(s) reach a function defined once per platform; each " +
			"is drawn to the " + targets[0].goos + "/" + targets[0].goarch + " definition")
	}
	for n := range s.notes {
		h.notes = append(h.notes, n)
	}
	sort.Strings(h.notes)
	return h
}

// importPath is the path a directory of this tree is imported by.
func (s *session) importPath(dir, name string) string {
	for _, m := range s.modules {
		if dir == m.root {
			return m.path
		}
		if strings.HasPrefix(dir, m.root+string(filepath.Separator)) {
			rel, _ := filepath.Rel(m.root, dir)
			return m.path + "/" + filepath.ToSlash(rel)
		}
	}
	// A directory under no `go.mod`: named for itself, which nothing imports.
	return "dunneflow.local/" + filepath.ToSlash(dir) + "#" + name
}

// join is the targets' answers about one site, as one. The same location from every
// target that compiled the site is that location; different locations are ambiguous,
// with how many there were; and an interface is ambiguous however it was reached.
func join(as []answer) (SuppliedEdge, string) {
	locs := map[string]answer{}
	outside, iface := false, 0
	for _, a := range as {
		switch {
		case a.file != "":
			locs[a.file+"\x00"+itoa(a.line)] = a
		case a.outside:
			outside = true
		case a.candidates > 0:
			if a.candidates > iface {
				iface = a.candidates
			}
		}
	}
	switch {
	case len(locs) == 1 && !outside && iface == 0:
		for _, a := range locs {
			return SuppliedEdge{File: a.file, Line: a.line, Name: a.name}, "edge"
		}
	case len(locs) > 1 && !outside && iface == 0:
		// One definition per platform. The reference target's, which answered first.
		for _, a := range as {
			if a.file != "" {
				return SuppliedEdge{File: a.file, Line: a.line, Name: a.name,
					How: "go/types · " + targets[0].goos + "/" + targets[0].goarch +
						" of " + itoa(len(locs)) + " platform variants"}, "edge"
			}
		}
	case len(locs) > 1 || (len(locs) == 1 && (outside || iface > 0)):
		n := len(locs) + iface
		if outside {
			n++
		}
		return SuppliedEdge{Candidates: n}, "ambiguous"
	case iface > 0:
		return SuppliedEdge{Candidates: iface}, "ambiguous"
	case outside:
		return SuppliedEdge{}, "outside"
	}
	return SuppliedEdge{}, "unknown"
}
