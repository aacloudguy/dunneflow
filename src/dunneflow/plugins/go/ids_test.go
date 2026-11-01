// The second implementations, held to the host's own answers.
//
// `tests/fixtures/ids/vectors.json` is written by `tools/gen_facts_go.py` from `schema.py`
// and Python's decoder, and `tests/test_go_reader.py` runs this. A test file is not in
// `fingerprint` and is not shipped: it proves the source, and the source is what is built.

package main

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

type vectorFile struct {
	MakeID         [][]json.RawMessage `json:"make_id"`
	DefinitionID   [][]json.RawMessage `json:"definition_id"`
	EntrypointID   [][]json.RawMessage `json:"entrypoint_id"`
	CallSiteID     [][]json.RawMessage `json:"call_site_id"`
	ControlPointID [][]json.RawMessage `json:"control_point_id"`
	HashSource     [][]json.RawMessage `json:"hash_source"`
	Decode         [][]json.RawMessage `json:"decode"`
}

func loadVectors(t *testing.T) vectorFile {
	path := os.Getenv("DUNNEFLOW_ID_VECTORS")
	if path == "" {
		path = filepath.Join("..", "..", "..", "..", "tests", "fixtures", "ids", "vectors.json")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("the vectors are the pin, and %s could not be read: %v", path, err)
	}
	var v vectorFile
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func str(t *testing.T, m json.RawMessage) string {
	var s string
	if err := json.Unmarshal(m, &s); err != nil {
		t.Fatal(err)
	}
	return s
}

func num(t *testing.T, m json.RawMessage) int {
	var n int
	if err := json.Unmarshal(m, &n); err != nil {
		t.Fatal(err)
	}
	return n
}

func strs(t *testing.T, m json.RawMessage) []string {
	var s []string
	if err := json.Unmarshal(m, &s); err != nil {
		t.Fatal(err)
	}
	return s
}

func check(t *testing.T, what, got, want string) {
	t.Helper()
	if got != want {
		t.Errorf("%s: this reader says %s and the host says %s", what, got, want)
	}
}

func TestIDsAreTheHostsIDs(t *testing.T) {
	v := loadVectors(t)
	for _, c := range v.MakeID {
		check(t, "make_id", makeID(strs(t, c[0])...), str(t, c[1]))
	}
	for _, c := range v.DefinitionID {
		check(t, "definition_id",
			definitionID(str(t, c[0]), str(t, c[1]), num(t, c[2])), str(t, c[3]))
	}
	for _, c := range v.EntrypointID {
		check(t, "entrypoint_id", entrypointID(str(t, c[0]), strs(t, c[1])...), str(t, c[2]))
	}
	for _, c := range v.CallSiteID {
		check(t, "call_site_id", callSiteID(str(t, c[0]), str(t, c[1]), num(t, c[2])),
			str(t, c[3]))
	}
	for _, c := range v.ControlPointID {
		check(t, "control_point_id",
			controlPointID(str(t, c[0]), str(t, c[1]), str(t, c[2]), num(t, c[3])),
			str(t, c[4]))
	}
	for _, c := range v.HashSource {
		check(t, "hash_source", hashSource(str(t, c[0])), str(t, c[1]))
	}
}

func TestTextIsReadAsTheHostReadsIt(t *testing.T) {
	for _, c := range loadVectors(t).Decode {
		raw, err := hex.DecodeString(str(t, c[0]))
		if err != nil {
			t.Fatal(err)
		}
		got := normaliseNewlines(decodeReplacing(raw))
		if want := str(t, c[1]); got != want {
			t.Errorf("% x: this reader read %q and the host read %q", raw, got, want)
		}
	}
}
