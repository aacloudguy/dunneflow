// The Go reader, on the far side of a pipe.
//
// `plugins/typescript/src/main.ts` is the worked example this follows, and the two agree
// on every rule that matters:
//
// **stdout carries protocol and nothing else.** Every diagnostic goes to stderr, which the
// host drains into a ring buffer and never parses. A stray `fmt.Println` here is a frame
// the host cannot read, and it refuses the language once and loudly rather than skipping
// six hundred files quietly.
//
// **Every reply echoes the request's `id`.** The host correlates on it.
//
// **A file that will not parse is `facts` with an error, and a file that made this
// reader panic is `failed`**: two different facts, and only the second lets the host
// write the record, because a reader that has just crashed on a file is not the right
// authority on what that file is.
//
// `open` takes the whole file set because a type checker over a subset answers wrongly
// rather than partially, and `edges` is the one frame that streams.

package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime/debug"
	"strings"
)

const (
	protocol = 1
	lang     = "go"
	// version is `plugin.json`'s, and the handshake refuses the language if they differ.
	version = "0.1.0"
)

type frame map[string]any

type reader struct {
	out   *bufio.Writer
	root  string
	files []string
	rules Rules
}

func (r *reader) send(f frame) {
	b, err := json.Marshal(f)
	if err != nil {
		// A frame this reader built and cannot encode is a defect here, and the host must
		// still get an answer to the id it is waiting on.
		b, _ = json.Marshal(frame{"t": "error", "id": f["id"],
			"reason": "could not encode a reply: " + err.Error()})
	}
	r.out.Write(b)
	r.out.WriteByte('\n')
	r.out.Flush()
}

// note is the other channel: evidence, never a control signal.
func note(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
}

func (r *reader) hello() frame {
	return frame{
		"t": "ready", "lang": lang, "version": version, "protocol": protocol,
		"schema_version": SchemaVersion,
		"capabilities":   frame{"supplies_edges": true, "reports_literals": true},
	}
}

func (r *reader) open(f frame) frame {
	r.root, _ = f["root"].(string)
	r.files = r.files[:0]
	if raw, ok := f["files"].([]any); ok {
		for _, x := range raw {
			if s, ok := x.(string); ok {
				r.files = append(r.files, s)
			}
		}
	}
	diagnostics := []string{}
	r.rules = parseRules(f["rules"])
	if len(r.rules.Boundaries) == 0 {
		// Not an error and not silent: a run with no rules is a map with no boundaries,
		// which looks exactly like a program that touches nothing (rule 49).
		note("no boundary rules arrived with this session; the map will report none")
		diagnostics = append(diagnostics, "no boundary rules arrived with this session")
	}
	return frame{"t": "opened", "files": len(r.files), "diagnostics": diagnostics}
}

// relPath is the stored spelling of a path: relative to the analysed root, with forward
// slashes on every platform (rule 93).
func (r *reader) relPath(abs string) string {
	rel, err := filepath.Rel(r.root, abs)
	if err != nil || rel == "." || strings.HasPrefix(rel, "..") {
		return filepath.ToSlash(abs)
	}
	return filepath.ToSlash(rel)
}

func (r *reader) extract(f frame) (reply frame) {
	path, _ := f["path"].(string)
	abs, err := filepath.Abs(path)
	if err != nil {
		abs = path
	}
	source, err := readSource(abs)
	if err != nil {
		// Nothing was read badly; nothing was read. A reader may describe that.
		return frame{"t": "failed", "reason": "could not be read: " + err.Error()}
	}
	defer func() {
		if p := recover(); p != nil {
			reply = frame{"t": "failed",
				"reason": fmt.Sprintf("%v\n%s", p, strings.TrimSpace(string(debug.Stack())))}
		}
	}()
	facts := extractFile(r.relPath(abs), source, &r.rules)
	// Echoed rather than assumed: the hash of what was actually read.
	return frame{"t": "facts", "hash": hashSource(source), "facts": facts}
}

// edges streams every call's far end. One frame per edge, because a module's answer is
// tens of thousands of them and one line holding all of them has no bound.
func (r *reader) edges(id any) {
	h := collectEdges(r.root, r.files, &r.rules)
	supplied := 0
	for _, e := range h.edges {
		if e.File != "" {
			supplied++
		}
		r.send(frame{"t": "edge", "id": id, "edge": e})
	}
	for _, n := range h.notes {
		note("%s", n)
	}
	r.send(frame{"t": "edges_done", "id": id, "supplied": supplied,
		"unresolved": h.outside + h.unknown, "outside": h.outside, "unknown": h.unknown})
}

func main() {
	r := &reader{out: bufio.NewWriter(os.Stdout)}
	in := bufio.NewReaderSize(os.Stdin, 1<<20)
	for {
		line, err := in.ReadBytes('\n')
		if len(strings.TrimSpace(string(line))) > 0 {
			r.handle(line)
		}
		if err == io.EOF {
			return
		}
		if err != nil {
			note("stdin: %v", err)
			return
		}
	}
}

func (r *reader) handle(line []byte) {
	var f frame
	if err := json.Unmarshal(line, &f); err != nil {
		note("unreadable frame: %.120s", line)
		return
	}
	id := f["id"]
	t, _ := f["t"].(string)
	defer func() {
		if p := recover(); p != nil {
			r.send(frame{"t": "error", "id": id,
				"reason": fmt.Sprintf("%v\n%s", p, strings.TrimSpace(string(debug.Stack())))})
		}
	}()
	switch t {
	case "close":
		r.send(frame{"t": "closed", "id": id})
		os.Exit(0)
	case "edges":
		r.edges(id)
		return
	}
	var reply frame
	switch t {
	case "hello":
		reply = r.hello()
	case "open":
		reply = r.open(f)
	case "extract":
		reply = r.extract(f)
	default:
		reply = frame{"t": "error", "reason": "unknown frame " + t}
	}
	reply["id"] = id
	r.send(reply)
}
