// What one Go file is: the facts `schema.FileFacts` holds, read from its syntax tree.
//
// `plugins/typescript/src/extract.ts`, one language over, and shaped the same way so the
// two can be read against each other. What moves is the subject; internal computation is
// not. A loop is recorded as a **span**, never as a variable, an operator or a value.
//
// **What this reader deliberately does not do here, and each one is stated:**
//
//   - **It resolves nothing.** Which function a call reaches is `edges.go`'s question,
//     asked of `go/types` over the whole module. This file reads one file's syntax.
//   - **An anonymous function is not a routine.** A declaration, a method, and a function
//     literal *bound to a name* (`h := func() {...}`, `var h = func() {...}`) are routines;
//     a literal passed inline, or started with `go func() {...}()`, is not, and its calls
//     belong to the nearest named routine that encloses it. Naming one would invent a word
//     for a reader to look for in a file that does not contain it (rule 30).
//   - **Go has no constructor syntax, so clause 7 has nothing to say.** `new(T)` is a call
//     to a builtin and `T{}` is a composite literal, not a call; recording either as
//     `T`-with-`is_construction` would put a call in the map that the source does not
//     make. The conformance cases leave Go out of clause 7 and the runner says so.
//   - **A function with no body is not a routine** (`LANGUAGES.md`, after C++): an
//     assembly stub or a `//go:linkname` declaration has nothing in it to read.

package main

import (
	"go/ast"
	"go/parser"
	"go/scanner"
	"go/token"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"
)

// `ingest/literals.py`'s bound, applied where the wire is. The host declares it.
const (
	literalMin  = 3
	literalMax  = 200_000
	moduleScope = "<module>"
)

// moduleName is a file's dotted path with `.go` dropped, so `probe.go` is `probe` and
// `pkg/run.go` is `pkg.run`: the shape every other reader gives a module, which keeps
// `probe.main` comparable across languages in one directory (`test_identity`).
func moduleName(rel string) string {
	parts := strings.Split(strings.TrimSuffix(rel, ".go"), "/")
	kept := parts[:0]
	for _, p := range parts {
		if p != "" {
			kept = append(kept, p)
		}
	}
	return strings.Join(kept, ".")
}

type extractor struct {
	path, module, src string
	fset              *token.FileSet
	file              *ast.File
	rules             *Rules
	isMain            bool

	routines    []*Routine
	calls       []CallSite
	boundaries  []BoundaryHit
	structures  []DataStructure
	classes     []ClassDef
	entrypoints []Entrypoint
	imports     []ImportRec
	constants   []Constant
	control     []ControlPoint
	arms        []ControlArm
	literals    []StringLiteral
	network     []NetworkCall
	dropped     int

	scope         []*Routine
	moduleRoutine *Routine
	moduleClaimed bool
	depth         int
	seenQual      map[string]int
	callOrdinal   map[string]int
	ctrlOrdinal   map[string]int
	// The package-level variable whose initialiser is being walked, and the handler each
	// command declared under it: `commentsAddCmd.Run` is a handler this file has already
	// minted, and an alias command that names it is linked to it (`linkHandlers`).
	declaring     string
	fieldHandlers map[string]string
	// How many handlers each enclosing qualname has registered under each word, for the
	// ordinal an inline handler's name carries.
	handlerOrdinal map[string]int
	// Comments that are a declaration's own documentation, recorded there as its
	// docstring and so never again as a comment (rule 40: one sentence, one fact).
	docs map[*ast.CommentGroup]bool
}

// extractFile reads one file. A file that will not parse comes back as facts carrying
// the error, which is the shape the in-process readers produce, so it is cached and not
// retried and `WalkStats` counts it as every other unreadable file. What did parse is
// still read: `go/parser` returns the tree it could build alongside its errors.
func extractFile(rel, source string, rules *Rules) FileFacts {
	ff := FileFacts{Path: rel, Lang: lang, Module: moduleName(rel),
		ContentHash: hashSource(source)}
	fset := token.NewFileSet()
	file, err := parser.ParseFile(fset, rel, source, parser.ParseComments|parser.AllErrors)
	if err != nil {
		ff.Errors = append(ff.Errors, parseErrors(err)...)
	}
	if file == nil {
		return ff
	}
	e := &extractor{
		path: rel, module: ff.Module, src: source, fset: fset, file: file, rules: rules,
		isMain:   file.Name != nil && file.Name.Name == "main",
		seenQual: map[string]int{}, callOrdinal: map[string]int{},
		ctrlOrdinal: map[string]int{}, docs: map[*ast.CommentGroup]bool{},
		handlerOrdinal: map[string]int{}, fieldHandlers: map[string]string{},
	}
	e.run()

	if file.Doc != nil {
		ff.Doc = strings.TrimSpace(file.Doc.Text())
	}
	for _, r := range e.routines {
		ff.Routines = append(ff.Routines, *r)
	}
	ff.Calls = e.calls
	ff.Boundaries = e.boundaries
	ff.Structures = e.structures
	ff.Classes = e.classes
	ff.Entrypoints = e.entrypoints
	ff.Imports = e.imports
	ff.Constants = e.constants
	ff.Control = e.control
	ff.ControlArms = e.arms
	ff.Literals = e.literals
	ff.Network = e.network
	ff.LiteralsDropped = e.dropped
	// Always sent, claimed or not: a string names its owner before anybody knows whether
	// it is a fact, and the host decides that (rule 96, `extract.ts:moduleScope`).
	ms := *e.moduleScopeRoutine()
	ff.ModuleScope = &ms
	return ff
}

// parseErrors is every error the parser reported, at most ten of them, as `line:col msg`.
func parseErrors(err error) []string {
	list, ok := err.(scanner.ErrorList)
	if !ok {
		return []string{err.Error()}
	}
	out := []string{}
	for i, e := range list {
		if i == 10 {
			out = append(out, "and more")
			break
		}
		out = append(out, e.Error())
	}
	return out
}

// ------------------------------------------------------------------ text --- //

func (e *extractor) line(p token.Pos) int { return e.fset.Position(p).Line }

func (e *extractor) endLine(n ast.Node) int {
	// `End` is one past the node; the last line is the line of its last byte.
	return e.fset.Position(n.End() - 1).Line
}

// text is a node as written, sliced from the file's own text and never re-rendered.
func (e *extractor) text(n ast.Node) string {
	if n == nil {
		return ""
	}
	start := e.fset.Position(n.Pos()).Offset
	end := e.fset.Position(n.End()).Offset
	if start < 0 || end > len(e.src) || start > end {
		return ""
	}
	return e.src[start:end]
}

func (e *extractor) span(from, to ast.Node) string {
	start := e.fset.Position(from.Pos()).Offset
	end := e.fset.Position(to.End()).Offset
	if start < 0 || end > len(e.src) || start > end {
		return ""
	}
	return e.src[start:end]
}

func exported(name string) bool {
	r, _ := utf8.DecodeRuneInString(name)
	return unicode.IsUpper(r)
}

// ----------------------------------------------------------------- owner --- //

func (e *extractor) identity(qualname string) string {
	n := e.seenQual[qualname] + 1
	e.seenQual[qualname] = n
	return definitionID(e.path, qualname, n)
}

func (e *extractor) moduleScopeRoutine() *Routine {
	if e.moduleRoutine == nil {
		qual := e.module + "." + moduleScope
		lines := strings.Count(e.src, "\n")
		if lines == 0 {
			lines = 1
		}
		e.moduleRoutine = &Routine{
			Id: definitionID(e.path, qual, 1), Name: moduleScope, Qualname: qual,
			Module: e.module, File: e.path, LineStart: 1, LineEnd: lines,
			Docstring: ptr("Package-level code: runs at initialisation, before main."),
			BodyHash:  hashSource(e.src),
		}
	}
	return e.moduleRoutine
}

// owner is the routine a fact belongs to, claiming the package scope only when it is
// needed, so asking is not what puts a routine in the map (rule 96).
func (e *extractor) owner() *Routine {
	if n := len(e.scope); n > 0 {
		return e.scope[n-1]
	}
	ms := e.moduleScopeRoutine()
	if !e.moduleClaimed {
		e.moduleClaimed = true
		e.routines = append(e.routines, ms)
	}
	return ms
}

func (e *extractor) ownerID() string {
	if n := len(e.scope); n > 0 {
		return e.scope[n-1].Id
	}
	return e.moduleScopeRoutine().Id
}

func ptr[T any](v T) *T { return &v }

// ------------------------------------------------------------------- run --- //

func (e *extractor) run() {
	for _, cg := range []*ast.CommentGroup{e.file.Doc} {
		if cg != nil {
			e.docs[cg] = true
		}
	}
	// Types first, so a constant block can be read as an enum of a type declared below it.
	enums := e.enumMembers()
	for _, d := range e.file.Decls {
		switch d := d.(type) {
		case *ast.FuncDecl:
			e.funcDecl(d)
		case *ast.GenDecl:
			switch d.Tok {
			case token.IMPORT:
				e.importDecl(d)
			case token.TYPE:
				e.typeDecl(d, enums)
			case token.CONST, token.VAR:
				e.valueDecl(d)
			}
		}
	}
	e.comments()
	e.linkHandlers()
}

// comments lands every comment that is not a declaration's own documentation on the
// innermost routine whose span holds it, and the package scope owns what no function
// does (rule 18).
func (e *extractor) comments() {
	for _, cg := range e.file.Comments {
		if e.docs[cg] {
			continue
		}
		for _, c := range cg.List {
			text := c.Text
			if strings.HasPrefix(text, "//") {
				text = strings.TrimSpace(text[2:])
			} else {
				text = strings.TrimSpace(strings.TrimSuffix(strings.TrimPrefix(text, "/*"), "*/"))
			}
			// A directive is an instruction to the toolchain, not prose for a reader.
			if text == "" || strings.HasPrefix(c.Text, "//go:") || strings.HasPrefix(c.Text, "//line ") {
				continue
			}
			ln := e.line(c.Pos())
			leading := e.leading(c)
			var home *Routine
			for _, r := range e.routines {
				if r.Name == moduleScope {
					continue
				}
				if r.LineStart <= ln && ln <= r.LineEnd && (home == nil || r.LineStart >= home.LineStart) {
					home = r
				}
			}
			if home == nil {
				saved := e.scope
				e.scope = nil
				home = e.owner()
				e.scope = saved
			}
			home.Comments = append(home.Comments, Comment{Text: text, Line: ln, Leading: leading})
		}
	}
}

// leading says whether a comment stands on a line of its own.
func (e *extractor) leading(c *ast.Comment) bool {
	off := e.fset.Position(c.Pos()).Offset
	start := strings.LastIndexByte(e.src[:off], '\n') + 1
	return strings.TrimSpace(e.src[start:off]) == ""
}

// ---------------------------------------------------------------- import --- //

// importDecl records each import. `name` is the path, which is the whole package, and
// `alias` is the local name **only where the file writes one** (`_`, `.` and a rename
// included): Go's default name is the package clause of a file this reader has not opened,
// and guessing it from the path's last element is wrong for `gopkg.in/yaml.v3` and every
// `/v2` module (rule 30).
func (e *extractor) importDecl(d *ast.GenDecl) {
	for _, s := range d.Specs {
		spec := s.(*ast.ImportSpec)
		path, err := strconv.Unquote(spec.Path.Value)
		if err != nil {
			path = spec.Path.Value
		}
		alias := ""
		if spec.Name != nil {
			alias = spec.Name.Name
		}
		e.imports = append(e.imports, ImportRec{Module: path, Name: path, Alias: alias,
			IsFrom: false, Line: e.line(spec.Pos())})
	}
}

// ------------------------------------------------------------------ types --- //

// enumMembers is the constants declared with an explicit named type, per type name, in
// declaration order: `type Color string` plus `const (Red Color = "red" ...)` is Go's
// enumeration, and rule 19 says a set of named values of one type is one.
func (e *extractor) enumMembers() map[string][]Field {
	out := map[string][]Field{}
	for _, d := range e.file.Decls {
		g, ok := d.(*ast.GenDecl)
		if !ok || g.Tok != token.CONST {
			continue
		}
		var typ string
		var values []ast.Expr
		for _, s := range g.Specs {
			spec := s.(*ast.ValueSpec)
			// Implicit repetition: a spec with neither type nor values repeats the last
			// one's, which is how an `iota` block is written.
			if spec.Type != nil || len(spec.Values) > 0 {
				typ, values = "", spec.Values
				if id, ok := spec.Type.(*ast.Ident); ok {
					typ = id.Name
				}
			}
			if typ == "" {
				continue
			}
			for i, n := range spec.Names {
				if n.Name == "_" {
					continue
				}
				f := Field{Name: n.Name}
				if i < len(values) {
					f.Default = ptr(e.text(values[i]))
				}
				out[typ] = append(out[typ], f)
			}
		}
	}
	return out
}

func (e *extractor) typeDecl(d *ast.GenDecl, enums map[string][]Field) {
	if d.Doc != nil {
		e.docs[d.Doc] = true
	}
	for _, s := range d.Specs {
		spec := s.(*ast.TypeSpec)
		doc := spec.Doc
		if doc == nil && len(d.Specs) == 1 {
			doc = d.Doc
		}
		if doc != nil {
			e.docs[doc] = true
		}
		name := spec.Name.Name
		qual := e.module + "." + name
		ds := DataStructure{Id: e.identity("struct\x00" + qual), Name: name,
			Module: e.module, File: e.path, Line: e.line(spec.Pos())}
		if doc != nil {
			ds.Docstring = ptr(strings.TrimSpace(doc.Text()))
		}
		switch t := spec.Type.(type) {
		case *ast.StructType:
			ds.Kind = StructureKindClass
			for _, f := range t.Fields.List {
				e.markDocs(f.Doc, f.Comment)
				typ := e.text(f.Type)
				if len(f.Names) == 0 {
					// An embedded type is what Go has for a base: its methods are promoted.
					ds.Bases = append(ds.Bases, typ)
					ds.Fields = append(ds.Fields, Field{Name: typ, Type: ptr(typ)})
					continue
				}
				for _, n := range f.Names {
					field := Field{Name: n.Name, Type: ptr(typ)}
					if f.Comment != nil {
						field.Comment = ptr(strings.TrimSpace(f.Comment.Text()))
					}
					ds.Fields = append(ds.Fields, field)
				}
			}
			cd := ClassDef{Name: name, Qualname: qual, Module: e.module, File: e.path,
				Line: ds.Line, Bases: ds.Bases}
			e.classes = append(e.classes, cd)
		case *ast.InterfaceType:
			ds.Kind = StructureKindInterface
			for _, m := range t.Methods.List {
				e.markDocs(m.Doc, m.Comment)
				typ := e.text(m.Type)
				if len(m.Names) == 0 {
					ds.Bases = append(ds.Bases, typ)
					continue
				}
				for _, n := range m.Names {
					ds.Fields = append(ds.Fields, Field{Name: n.Name, Type: ptr(typ)})
				}
			}
		default:
			if members := enums[name]; len(members) > 0 && !spec.Assign.IsValid() {
				ds.Kind = StructureKindEnum
				ds.Fields = members
				ds.Bases = List[string]{e.text(spec.Type)}
			} else {
				// `type A = B` is an alias and `type H func()` a defined type; neither has
				// fields, and the schema's nearest word for both is TYPE_ALIAS. The type
				// as written is carried in `bases` so the difference is still readable.
				ds.Kind = StructureKindTypeAlias
				ds.Bases = List[string]{e.text(spec.Type)}
			}
		}
		e.structures = append(e.structures, ds)
	}
}

// markDocs records comments that a declaration has already taken as its own, so they are
// not landed a second time as free comments (rule 40).
func (e *extractor) markDocs(groups ...*ast.CommentGroup) {
	for _, g := range groups {
		if g != nil {
			e.docs[g] = true
		}
	}
}

// --------------------------------------------------------------- values --- //

// valueDecl reads package-level `const` and `var`. A function literal bound to a name is
// a routine; anything else is a constant, as written, and its initialiser is walked under
// the package scope because that is when it runs.
func (e *extractor) valueDecl(d *ast.GenDecl) {
	if d.Doc != nil {
		e.docs[d.Doc] = true
	}
	var lastType ast.Expr
	var lastValues []ast.Expr
	for _, s := range d.Specs {
		spec := s.(*ast.ValueSpec)
		if spec.Doc != nil {
			e.docs[spec.Doc] = true
		}
		typ, values := spec.Type, spec.Values
		if d.Tok == token.CONST && typ == nil && len(values) == 0 {
			typ, values = lastType, lastValues
		} else {
			lastType, lastValues = typ, values
		}
		why := spec.Doc
		if why == nil && len(d.Specs) == 1 {
			why = d.Doc
		}
		if why == nil {
			why = spec.Comment
		}
		e.markDocs(spec.Comment)
		for i, n := range spec.Names {
			if n.Name == "_" {
				continue
			}
			var value ast.Expr
			if i < len(values) {
				value = values[i]
			} else if len(values) == 1 {
				value = values[0]
			}
			if lit, ok := value.(*ast.FuncLit); ok && d.Tok == token.VAR {
				e.routine(n.Name, lit.Type, lit.Body, spec, "", nil)
				continue
			}
			c := Constant{Name: n.Name, Value: e.text(value), Line: e.line(n.Pos()),
				IsFinal: d.Tok == token.CONST, Private: !exported(n.Name)}
			if typ != nil {
				c.Type = ptr(e.text(typ))
			}
			if why != nil {
				if first := strings.TrimSpace(strings.SplitN(why.Text(), "\n", 2)[0]); first != "" {
					c.Comment = ptr(first)
				}
			}
			e.constants = append(e.constants, c)
		}
		// Walked once per spec, not per name: `var a, b = f()` calls `f` once.
		if spec.Values != nil {
			for _, v := range spec.Values {
				if _, ok := v.(*ast.FuncLit); ok && d.Tok == token.VAR {
					continue
				}
				if len(spec.Names) == 1 {
					e.declaring = spec.Names[0].Name
				}
				e.walk(v)
				e.declaring = ""
			}
		}
	}
}

// --------------------------------------------------------------- routine --- //

// receiverType is the type a method is declared on, with the pointer and any type
// parameters taken off: a method on `*T` and one on `T` both belong to `T`.
func receiverType(recv *ast.FieldList) string {
	if recv == nil || len(recv.List) == 0 {
		return ""
	}
	t := recv.List[0].Type
	for {
		switch v := t.(type) {
		case *ast.StarExpr:
			t = v.X
		case *ast.ParenExpr:
			t = v.X
		case *ast.IndexExpr:
			t = v.X
		case *ast.IndexListExpr:
			t = v.X
		case *ast.Ident:
			return v.Name
		default:
			return ""
		}
	}
}

func (e *extractor) funcDecl(d *ast.FuncDecl) {
	if d.Doc != nil {
		e.docs[d.Doc] = true
	}
	if d.Body == nil {
		return
	}
	class := receiverType(d.Recv)
	r := e.routine(d.Name.Name, d.Type, d.Body, d, class, d.Doc)
	// A way in: `main` in `package main`, never a method, and only where the rules name it.
	if r != nil && class == "" && e.isMain && e.rules.entryNames[d.Name.Name] {
		e.entrypoints = append(e.entrypoints, Entrypoint{
			Id:   entrypointID(e.path, r.Qualname, "main"),
			Kind: EntrypointKindMain, Name: r.Name, RoutineId: ptr(r.Id),
			Module:   e.module,
			Evidence: r.Name + "() at " + e.path + ":" + strconv.Itoa(r.LineStart),
		})
	}
}

// routine records one named function and walks its body as that routine.
func (e *extractor) routine(name string, ft *ast.FuncType, body *ast.BlockStmt,
	node ast.Node, class string, doc *ast.CommentGroup) *Routine {
	var parent *Routine
	if n := len(e.scope); n > 0 {
		parent = e.scope[n-1]
	}
	var qual string
	switch {
	case parent != nil:
		qual = parent.Qualname + "." + name
	case class != "":
		qual = e.module + "." + class + "." + name
	default:
		qual = e.module + "." + name
	}
	r := &Routine{
		Id: e.identity(qual), Name: name, Qualname: qual, Module: e.module, File: e.path,
		LineStart: e.line(node.Pos()), LineEnd: e.endLine(node),
		BodyHash: hashSource(e.text(body)),
	}
	r.Params = e.params(ft)
	// **Always declared, because Go has no other way to write a function.** A function
	// with no result list returns nothing, and says so by the absence; `None` here would
	// mean *undeclared*, which no Go function is, and `MISSING_RETURN_TYPE` read it that
	// way: 183 of rain's 715 routines "declare no return type", every one of them a
	// function that returns nothing (rule 98). So nothing is spelled as the empty string.
	r.Returns = ptr("")
	if ft.Results != nil && len(ft.Results.List) > 0 {
		r.Returns = ptr(e.text(ft.Results))
	}
	if class != "" {
		r.IsMethod = true
		r.ClassName = ptr(class)
	}
	if parent != nil {
		r.IsNested = true
	}
	// Go's privacy is the case of the first letter, and it is package privacy: an
	// unexported name is invisible outside its package, which is what `private` says.
	if !exported(name) {
		r.Visibility = "private"
	}
	if doc != nil {
		r.Docstring = ptr(strings.TrimSpace(doc.Text()))
	}
	e.routines = append(e.routines, r)

	e.scope = append(e.scope, r)
	saved := e.depth
	e.depth = 0
	if body != nil {
		for _, s := range body.List {
			e.walk(s)
		}
	}
	e.depth = saved
	e.scope = e.scope[:len(e.scope)-1]
	return r
}

func (e *extractor) params(ft *ast.FuncType) List[Param] {
	var out List[Param]
	if ft == nil || ft.Params == nil {
		return out
	}
	for _, f := range ft.Params.List {
		typ := f.Type
		kind := ""
		if el, ok := typ.(*ast.Ellipsis); ok {
			// `xs ...T` is Go's only variadic form.
			kind = "vararg"
			typ = el.Elt
		}
		written := e.text(typ)
		if kind == "vararg" {
			written = "..." + written
		}
		names := f.Names
		if len(names) == 0 {
			// An unnamed parameter has the blank name in all but spelling.
			names = []*ast.Ident{{Name: "_"}}
		}
		for _, n := range names {
			p := Param{Name: n.Name, Type: ptr(written), Kind: kind}
			out = append(out, p)
		}
	}
	return out
}

// ------------------------------------------------------------------ walk --- //

// walk visits everything that is not a declaration: calls, control, strings, and the
// function literals bound to names inside a body.
func (e *extractor) walk(n ast.Node) {
	if n == nil {
		return
	}
	ast.Inspect(n, func(x ast.Node) bool {
		switch v := x.(type) {
		case nil:
			return false
		case *ast.CallExpr:
			e.call(v)
			return false
		case *ast.IfStmt:
			e.ifLadder(v)
			return false
		case *ast.ForStmt:
			e.forStmt(v)
			return false
		case *ast.RangeStmt:
			e.rangeStmt(v)
			return false
		case *ast.SwitchStmt:
			e.switchStmt(v)
			return false
		case *ast.TypeSwitchStmt:
			e.typeSwitch(v)
			return false
		case *ast.SelectStmt:
			e.selectStmt(v)
			return false
		case *ast.CompositeLit:
			return e.command(v)
		case *ast.AssignStmt:
			return e.assign(v)
		case *ast.DeclStmt:
			return e.localDecl(v)
		case *ast.BasicLit:
			if v.Kind == token.STRING {
				e.literal(v)
			}
			return false
		}
		return true
	})
}

// assign makes `h := func() {...}` a routine named `h`, inside a routine only. Returns
// whether the walk should descend into the statement itself.
func (e *extractor) assign(a *ast.AssignStmt) bool {
	if len(e.scope) == 0 || len(a.Lhs) != len(a.Rhs) {
		return true
	}
	named := false
	for i, rhs := range a.Rhs {
		_, ok := rhs.(*ast.FuncLit)
		id, isID := a.Lhs[i].(*ast.Ident)
		named = named || (ok && isID && id.Name != "_")
	}
	if !named {
		return true
	}
	for i, rhs := range a.Rhs {
		lit, ok := rhs.(*ast.FuncLit)
		id, isID := a.Lhs[i].(*ast.Ident)
		if ok && isID && id.Name != "_" {
			e.routine(id.Name, lit.Type, lit.Body, a, "", nil)
			continue
		}
		e.walk(a.Lhs[i])
		e.walk(rhs)
	}
	return false
}

// localDecl makes `var h = func() {...}` inside a body a routine, as `assign` does.
func (e *extractor) localDecl(d *ast.DeclStmt) bool {
	g, ok := d.Decl.(*ast.GenDecl)
	if !ok || g.Tok != token.VAR {
		return true
	}
	for _, s := range g.Specs {
		spec := s.(*ast.ValueSpec)
		for i, v := range spec.Values {
			if lit, ok := v.(*ast.FuncLit); ok && i < len(spec.Names) && spec.Names[i].Name != "_" {
				e.routine(spec.Names[i].Name, lit.Type, lit.Body, spec, "", nil)
				continue
			}
			e.walk(v)
		}
	}
	return false
}

// --------------------------------------------------------------- dotted --- //

// predeclaredTypes are the names that can stand in an index expression as a type
// argument and never as a value. See `dotted`, clause 6.
var predeclaredTypes = map[string]bool{
	"any": true, "bool": true, "byte": true, "comparable": true, "complex64": true,
	"complex128": true, "error": true, "float32": true, "float64": true, "int": true,
	"int8": true, "int16": true, "int32": true, "int64": true, "rune": true, "string": true,
	"uint": true, "uint8": true, "uint16": true, "uint32": true, "uint64": true,
	"uintptr": true,
}

// looksLikeType says whether an index can only be a type argument. Clause 6 says type
// arguments are not part of a name, and clause 3 says a subscript leaves the chain
// unnamed; Go writes both as `x[y]`, and without the checker this reader cannot always
// tell which. So it answers *type* only where the index cannot be a value — a
// predeclared type, or a composite type expression — and *subscript* otherwise. The
// residue is `f[MyType]()`, which reads as unnamed: a call left out of rule matching,
// never a wrong name (rule 1). Its edge still comes from the checker.
func looksLikeType(x ast.Expr) bool {
	switch v := x.(type) {
	case *ast.Ident:
		return predeclaredTypes[v.Name]
	case *ast.ArrayType, *ast.MapType, *ast.ChanType, *ast.FuncType, *ast.InterfaceType,
		*ast.StructType, *ast.StarExpr:
		return true
	}
	return false
}

// dotted is a callee as `ingest/dotted.py`'s contract spells it.
func dotted(x ast.Expr) string {
	switch v := x.(type) {
	case *ast.Ident:
		return v.Name
	case *ast.SelectorExpr:
		base := dotted(v.X)
		if base == "" {
			return ""
		}
		return base + "." + v.Sel.Name
	case *ast.CallExpr:
		// Clause 2: a call in the middle folds to its callee.
		return dotted(v.Fun)
	case *ast.ParenExpr:
		return dotted(v.X)
	case *ast.IndexListExpr:
		// Clause 6: several indices are always type arguments.
		return dotted(v.X)
	case *ast.IndexExpr:
		if looksLikeType(v.Index) {
			return dotted(v.X)
		}
		return ""
	}
	// Clause 3: a literal, a type assertion, a conversion to a composite type, a function
	// literal — no name at the root, and `""` is never matched against a rule.
	return ""
}

// ------------------------------------------------------------------ call --- //

func (e *extractor) call(c *ast.CallExpr) {
	expr := dotted(c.Fun)
	if expr != "" {
		owner := e.owner()
		line := e.line(c.Pos())
		rule := e.rules.matchCall(expr)
		e.recordCall(owner.Id, expr, line, rule != nil, e.callArgs(c))
		if rule != nil {
			hit := BoundaryHit{RoutineId: owner.Id, Kind: BoundaryKind(rule.Kind),
				Direction: Direction(rule.Direction), Target: e.target(c, expr, rule),
				Line: line, Evidence: expr}
			if rule.Salience != "normal" {
				hit.Salience = rule.Salience
			}
			e.boundaries = append(e.boundaries, hit)
		}
		e.maybeNetwork(c, expr, line)
	}
	claimed := e.registration(c, expr)
	// The callee is walked too: `a.b(x).c()` holds the call `a.b`, and `func(){...}()`
	// is an anonymous function whose body belongs to the enclosing routine.
	e.walk(c.Fun)
	for i, a := range c.Args {
		if i != claimed {
			e.walk(a)
		}
	}
}

func (e *extractor) recordCall(callerID, expr string, line int, atBoundary bool,
	args List[CallArg]) {
	key := callerID + "\x00" + expr
	ordinal := e.callOrdinal[key]
	e.callOrdinal[key] = ordinal + 1
	e.calls = append(e.calls, CallSite{
		CallerId: callerID, CalleeExpr: expr, Line: line,
		SiteId: callSiteID(callerID, expr, ordinal),
		// Rule 2: a call that touches a boundary is never also an internal edge.
		AtBoundary: atBoundary, Args: args,
	})
}

func (e *extractor) callArgs(c *ast.CallExpr) List[CallArg] {
	var out List[CallArg]
	for i, a := range c.Args {
		arg := CallArg{Idx: i, Expr: e.text(a)}
		if c.Ellipsis.IsValid() && i == len(c.Args)-1 {
			arg.Splat = true
		}
		out = append(out, arg)
	}
	return out
}

func stringValue(x ast.Expr) (string, bool) {
	lit, ok := x.(*ast.BasicLit)
	if !ok || lit.Kind != token.STRING {
		return "", false
	}
	s, err := strconv.Unquote(lit.Value)
	if err != nil {
		return "", false
	}
	return s, true
}

// target is what a boundary touch touched, by the rule's own strategy.
func (e *extractor) target(c *ast.CallExpr, expr string, rule *BoundaryRule) string {
	if rule.Target == "receiver_tail" {
		parts := strings.Split(expr, ".")
		if len(parts) >= 3 {
			return parts[len(parts)-2]
		}
		return parts[0]
	}
	if rule.TargetArg == nil {
		return ""
	}
	idx := *rule.TargetArg
	if idx < 0 || idx >= len(c.Args) {
		return ""
	}
	if s, ok := stringValue(c.Args[idx]); ok {
		return s
	}
	return e.text(c.Args[idx])
}

func (e *extractor) maybeNetwork(c *ast.CallExpr, expr string, line int) {
	_, lib, ok := e.rules.matchNetwork(expr)
	if !ok {
		return
	}
	nc := NetworkCall{RoutineId: e.ownerID(), Expr: expr, Protocol: lib.Protocol, Line: line,
		IsAsync: lib.Async}
	last := expr[strings.LastIndexByte(expr, '.')+1:]
	if e.rules.isVerb(last) {
		nc.Verb = strings.ToUpper(last)
	}
	// `http.NewRequest(method, url, body)` names its verb and destination as arguments.
	args := c.Args
	if strings.HasPrefix(last, "NewRequest") {
		at := 0
		if last == "NewRequestWithContext" {
			at = 1
		}
		if len(args) > at {
			if s, ok := stringValue(args[at]); ok {
				nc.Verb = strings.ToUpper(s)
			} else {
				nc.Verb = e.text(args[at])
			}
		}
		if len(args) > at+1 {
			args = args[at+1:]
		} else {
			args = nil
		}
	}
	if len(args) > 0 {
		if s, ok := stringValue(args[0]); ok {
			nc.Destination = s
		} else {
			nc.Destination = e.text(args[0])
		}
	}
	e.network = append(e.network, nc)
}

// --------------------------------------------------------------- literal --- //

func (e *extractor) literal(lit *ast.BasicLit) {
	text, err := strconv.Unquote(lit.Value)
	if err != nil {
		text = lit.Value
	}
	n := utf8.RuneCountInString(text)
	if n < literalMin || n > literalMax {
		e.dropped++
		return
	}
	e.literals = append(e.literals, StringLiteral{RoutineId: e.ownerID(),
		Line: e.line(lit.Pos()), Text: text})
}

// --------------------------------------------------------------- control --- //

func (e *extractor) addPoint(n ast.Node, kind ControlKind, header, word string, arms int,
	exits string, once [2]int) ControlPoint {
	routineID := e.owner().Id
	key := routineID + "\x00" + string(kind) + "\x00" + header
	ordinal := e.ctrlOrdinal[key]
	e.ctrlOrdinal[key] = ordinal + 1
	p := ControlPoint{
		PointId:   controlPointID(routineID, string(kind), header, ordinal),
		RoutineId: routineID, Kind: kind, LineStart: e.line(n.Pos()), LineEnd: e.endLine(n),
		Depth: e.depth, Header: header, Exits: exits, Word: word,
		OnceStart: once[0], OnceEnd: once[1],
	}
	if arms != 1 {
		p.Arms = arms
	}
	e.control = append(e.control, p)
	return p
}

func (e *extractor) addArm(p ControlPoint, idx int, kind ArmKind, n ast.Node, header string) {
	e.arms = append(e.arms, ControlArm{PointId: p.PointId, RoutineId: p.RoutineId,
		Idx: idx, Kind: kind, LineStart: e.line(n.Pos()), LineEnd: e.endLine(n),
		Header: header})
}

func (e *extractor) inside(f func()) {
	e.depth++
	defer func() { e.depth-- }()
	f()
}

// onceRange is the lines a loop evaluates once, before its first pass: the evaluated
// part's span minus every line the repeated part also occupies (`extract.ts:onceRange`).
func (e *extractor) onceRange(evaluated, repeated ast.Node) [2]int {
	start, end := e.line(evaluated.Pos()), e.endLine(evaluated)
	if b := e.line(repeated.Pos()); b <= end {
		end = b - 1
	}
	if end >= start {
		return [2]int{start, end}
	}
	return [2]int{0, 0}
}

// ifHeader is the condition as written, with its init statement when it has one:
// `if err := f(); err != nil` is one header, because the init is what the test is about.
func (e *extractor) ifHeader(s *ast.IfStmt) string {
	if s.Init != nil {
		return e.span(s.Init, s.Cond)
	}
	return e.text(s.Cond)
}

func (e *extractor) ifLadder(s *ast.IfStmt) {
	rungs := []*ast.IfStmt{s}
	var tail ast.Stmt
	for cur := s; ; {
		next, ok := cur.Else.(*ast.IfStmt)
		if !ok {
			tail = cur.Else
			break
		}
		rungs = append(rungs, next)
		cur = next
	}
	exits := ""
	if len(rungs) == 1 && tail == nil {
		exits = leavesWith(s.Body)
	}
	kind := ControlKindDecision
	if exits != "" {
		kind = ControlKindGuard
	}
	arms := len(rungs)
	if tail != nil {
		arms++
	}
	p := e.addPoint(s, kind, e.ifHeader(s), "if", arms, exits, [2]int{})
	for i, r := range rungs {
		k := ArmKindIf
		if i > 0 {
			// Go writes the rung as two words, as TypeScript does, and `ArmKind` carries it
			// as written.
			k = ArmKindElseIf
		}
		e.addArm(p, i, k, r.Body, e.ifHeader(r))
	}
	if tail != nil {
		e.addArm(p, len(rungs), ArmKindElse, tail, "")
	}
	e.inside(func() {
		for _, r := range rungs {
			if r.Init != nil {
				e.walk(r.Init)
			}
			e.walk(r.Cond)
			e.walk(r.Body)
		}
		if tail != nil {
			e.walk(tail)
		}
	})
}

// leavesWith is how a one-armed decision leaves, read off its last statement, because
// `if err != nil { return err }` and `if err != nil { panic(err) }` are the same sentence
// and opposite facts.
func leavesWith(body *ast.BlockStmt) string {
	if body == nil || len(body.List) == 0 {
		return ""
	}
	switch last := body.List[len(body.List)-1].(type) {
	case *ast.ReturnStmt:
		return "return"
	case *ast.BranchStmt:
		switch last.Tok {
		case token.BREAK:
			return "break"
		case token.CONTINUE:
			return "continue"
		case token.GOTO:
			return "goto"
		}
	case *ast.ExprStmt:
		if c, ok := last.X.(*ast.CallExpr); ok {
			switch dotted(c.Fun) {
			case "panic":
				return "panic"
			case "os.Exit", "log.Fatal", "log.Fatalf", "log.Fatalln":
				return "exit"
			}
		}
	}
	return ""
}

func (e *extractor) forStmt(s *ast.ForStmt) {
	header := ""
	switch {
	case s.Init != nil || s.Post != nil:
		header = e.text(s.Init) + "; " + e.text(s.Cond) + "; " + e.text(s.Post)
	case s.Cond != nil:
		header = e.text(s.Cond)
	}
	once := [2]int{}
	if s.Init != nil {
		// The initialiser runs once; the test and the post statement repeat.
		once = e.onceRange(s.Init, s.Body)
	}
	p := e.addPoint(s, ControlKindLoop, header, "for", 1, "", once)
	e.addArm(p, 0, ArmKindFor, s.Body, "")
	e.inside(func() {
		if s.Init != nil {
			e.walk(s.Init)
		}
		if s.Cond != nil {
			e.walk(s.Cond)
		}
		if s.Post != nil {
			e.walk(s.Post)
		}
		e.walk(s.Body)
	})
}

func (e *extractor) rangeStmt(s *ast.RangeStmt) {
	header := "range " + e.text(s.X)
	if s.Key != nil {
		lhs := e.text(s.Key)
		if s.Value != nil {
			lhs += ", " + e.text(s.Value)
		}
		header = lhs + " " + s.Tok.String() + " " + header
	}
	// The ranged-over expression is evaluated once.
	p := e.addPoint(s, ControlKindLoop, header, "for", 1, "", e.onceRange(s.X, s.Body))
	e.addArm(p, 0, ArmKindFor, s.Body, "")
	e.inside(func() {
		e.walk(s.X)
		e.walk(s.Body)
	})
}

func (e *extractor) clauses(p ControlPoint, body *ast.BlockStmt) {
	for i, st := range body.List {
		switch c := st.(type) {
		case *ast.CaseClause:
			if c.List == nil {
				e.addArm(p, i, ArmKindDefault, c, "")
				continue
			}
			parts := make([]string, len(c.List))
			for j, x := range c.List {
				parts[j] = e.text(x)
			}
			e.addArm(p, i, ArmKindCase, c, strings.Join(parts, ", "))
		case *ast.CommClause:
			if c.Comm == nil {
				e.addArm(p, i, ArmKindDefault, c, "")
				continue
			}
			e.addArm(p, i, ArmKindCase, c, e.text(c.Comm))
		}
	}
}

func armsOf(body *ast.BlockStmt) int {
	if n := len(body.List); n > 0 {
		return n
	}
	return 1
}

func (e *extractor) switchStmt(s *ast.SwitchStmt) {
	header := e.text(s.Tag)
	if s.Init != nil {
		header = e.text(s.Init) + "; " + header
	}
	p := e.addPoint(s, ControlKindDecision, header, "switch", armsOf(s.Body), "", [2]int{})
	e.clauses(p, s.Body)
	e.inside(func() {
		if s.Init != nil {
			e.walk(s.Init)
		}
		if s.Tag != nil {
			e.walk(s.Tag)
		}
		for _, st := range s.Body.List {
			for _, b := range st.(*ast.CaseClause).Body {
				e.walk(b)
			}
		}
	})
}

func (e *extractor) typeSwitch(s *ast.TypeSwitchStmt) {
	header := e.text(s.Assign)
	if s.Init != nil {
		header = e.text(s.Init) + "; " + header
	}
	p := e.addPoint(s, ControlKindDecision, header, "switch", armsOf(s.Body), "", [2]int{})
	e.clauses(p, s.Body)
	e.inside(func() {
		if s.Init != nil {
			e.walk(s.Init)
		}
		e.walk(s.Assign)
		for _, st := range s.Body.List {
			for _, b := range st.(*ast.CaseClause).Body {
				e.walk(b)
			}
		}
	})
}

// selectStmt is a decision about which channel operation happens first: one arm per
// `case`, and the operations themselves are walked as the arm's own.
func (e *extractor) selectStmt(s *ast.SelectStmt) {
	p := e.addPoint(s, ControlKindDecision, "", "select", armsOf(s.Body), "", [2]int{})
	e.clauses(p, s.Body)
	e.inside(func() {
		for _, st := range s.Body.List {
			c := st.(*ast.CommClause)
			if c.Comm != nil {
				e.walk(c.Comm)
			}
			for _, b := range c.Body {
				e.walk(b)
			}
		}
	})
}

// ------------------------------------------------------------- ways in --- //

// routeShaped says whether a string is written as a route: `/x`, or a verb and a path
// (`GET /x`, Go 1.22's pattern syntax). It is what makes a bare method name safe to match
// for a registration (rule 5): `cache.Get("k", v)` registers nothing.
func routeShaped(s string) bool {
	if strings.HasPrefix(s, "/") {
		return true
	}
	verb, path, ok := strings.Cut(s, " ")
	return ok && verb != "" && strings.ToUpper(verb) == verb && strings.HasPrefix(path, "/")
}

// inlineHandler makes a handler written in place a routine, named by the word that
// registered it, with an ordinal in the name where the same word registers several in one
// scope: the word written at that line, never one invented for it (rule 30), and two of
// them must not read as one name defined twice (`extract.ts:freeHookName`).
func (e *extractor) inlineHandler(word string, lit *ast.FuncLit) *Routine {
	prefix := e.module
	if n := len(e.scope); n > 0 {
		prefix = e.scope[n-1].Qualname
	}
	key := prefix + "\x00" + word
	n := e.handlerOrdinal[key] + 1
	e.handlerOrdinal[key] = n
	name := word
	if n > 1 {
		name = word + "#" + strconv.Itoa(n)
	}
	return e.routine(name, lit.Type, lit.Body, lit, "", nil)
}

func (e *extractor) wayIn(kind, name, evidence string, line int, handler ast.Expr,
	word string) *Entrypoint {
	// Position-free, as every id is (`schema.make_id`): the kind and the name, and an
	// ordinal only where one file registers the same name twice.
	parts := []string{strings.ToLower(kind), name}
	key := strings.Join(parts, "\x00")
	if n := e.handlerOrdinal["ep\x00"+key] + 1; n > 1 {
		parts = append(parts, "#"+strconv.Itoa(n))
		e.handlerOrdinal["ep\x00"+key] = n
	} else {
		e.handlerOrdinal["ep\x00"+key] = 1
	}
	ep := Entrypoint{
		Id:   entrypointID(e.path, parts...),
		Kind: EntrypointKind(kind), Name: name, Module: e.module,
		Evidence: evidence + " at " + e.path + ":" + strconv.Itoa(line),
	}
	if lit, ok := handler.(*ast.FuncLit); ok {
		r := e.inlineHandler(word, lit)
		ep.RoutineId = ptr(r.Id)
	} else if handler != nil {
		ep.TargetExpr = e.text(handler)
	}
	e.entrypoints = append(e.entrypoints, ep)
	return &e.entrypoints[len(e.entrypoints)-1]
}

// registration records a way in declared by a call, and returns the index of the argument
// it walked as a routine of its own, or -1.
func (e *extractor) registration(c *ast.CallExpr, expr string) int {
	if expr == "" || len(c.Args) == 0 {
		return -1
	}
	last := expr[strings.LastIndexByte(expr, '.')+1:]
	for _, reg := range e.rules.Registrations {
		if !contains(reg.Method, last) || reg.RouteArg >= len(c.Args) {
			continue
		}
		route, ok := stringValue(c.Args[reg.RouteArg])
		if !ok || !routeShaped(route) {
			continue
		}
		at := reg.HandlerArg
		if at < 0 {
			at = len(c.Args) + at
		}
		if at < 0 || at >= len(c.Args) || at == reg.RouteArg {
			return -1
		}
		e.wayIn(reg.Kind, route, reg.Evidence, e.line(c.Pos()), c.Args[at], last)
		if _, ok := c.Args[at].(*ast.FuncLit); ok {
			return at
		}
		return -1
	}
	return -1
}

// command records a way in declared by a composite literal. Returns whether the walk
// should descend into the literal itself.
func (e *extractor) command(lit *ast.CompositeLit) bool {
	typ := e.text(lit.Type)
	for _, cmd := range e.rules.Commands {
		if !contains(cmd.Type, typ) {
			continue
		}
		name := ""
		var handler ast.Expr
		word := ""
		fields := map[string]ast.Expr{}
		for _, el := range lit.Elts {
			kv, ok := el.(*ast.KeyValueExpr)
			if !ok {
				continue
			}
			if k, ok := kv.Key.(*ast.Ident); ok {
				fields[k.Name] = kv.Value
			}
		}
		if v, ok := fields[cmd.NameField]; ok {
			if s, ok := stringValue(v); ok {
				// `Use: "serve [flags]"`: the command is the first word.
				if words := strings.Fields(s); len(words) > 0 {
					name = words[0]
				}
			}
		}
		for _, f := range cmd.HandlerFields {
			if v, ok := fields[f]; ok {
				handler, word = v, f
				break
			}
		}
		if name == "" || handler == nil {
			// A command that sets no handler is a group (`rain cc`, whose subcommands are
			// attached with `AddCommand`): a namespace a reader types on the way to a
			// command, not one that does anything. Recorded as a way in it read as one
			// that *leads nowhere*, and `ENTRYPOINT_NO_TARGET` said so four times about
			// rain; every one was this reader and none was rain.
			return true
		}
		ep := e.wayIn(cmd.Kind, name, cmd.Evidence, e.line(lit.Pos()), handler, word)
		if e.declaring != "" && ep.RoutineId != nil {
			e.fieldHandlers[e.declaring+"."+word] = *ep.RoutineId
		}
		for _, el := range lit.Elts {
			if kv, ok := el.(*ast.KeyValueExpr); ok && kv.Value == handler {
				if _, isLit := handler.(*ast.FuncLit); isLit {
					continue
				}
			}
			e.walk(el)
		}
		return false
	}
	return true
}

// linkHandlers links a way in whose handler is a bare identifier to the function of that
// name declared in this file. Anything else keeps its expression: which function
// `s.routes.items` is, is the checker's question, and a guess here would be a wrong way
// in rather than an unlinked one (rule 1).
func (e *extractor) linkHandlers() {
	byQual := map[string]*Routine{}
	for _, r := range e.routines {
		if !r.IsMethod && !r.IsNested {
			byQual[r.Qualname] = r
		}
	}
	for i := range e.entrypoints {
		ep := &e.entrypoints[i]
		if ep.RoutineId != nil || ep.TargetExpr == "" {
			continue
		}
		if r, ok := byQual[e.module+"."+ep.TargetExpr]; ok {
			ep.RoutineId = ptr(r.Id)
		} else if id, ok := e.fieldHandlers[ep.TargetExpr]; ok {
			// `Run: commentsAddCmd.Run`, an alias command (beads' `bd comment`).
			ep.RoutineId = ptr(id)
		}
	}
}
