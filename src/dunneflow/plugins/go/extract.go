// What one Go file is: the facts `schema.FileFacts` holds, read from its syntax tree.

package main

import (
	"go/parser"
	"go/scanner"
	"go/token"
	"strings"
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

// extractFile reads one file. A file that will not parse comes back as facts carrying
// the error, which is the shape the in-process readers produce, so it is cached and not
// retried and `WalkStats` counts it as every other unreadable file.
func extractFile(rel, source string, rules *Rules) FileFacts {
	ff := FileFacts{Path: rel, Lang: lang, Module: moduleName(rel),
		ContentHash: hashSource(source)}
	fset := token.NewFileSet()
	_, err := parser.ParseFile(fset, rel, source, parser.ParseComments|parser.AllErrors)
	if err != nil {
		ff.Errors = append(ff.Errors, parseErrors(err)...)
	}
	_ = rules
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
