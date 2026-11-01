// The language's rules, as `detectors/go.yaml` declares them and the host sends them.
//
// They arrive with the session and are never baked in: a reader carrying its own copy of
// the YAML is a second answer that stops moving the moment somebody edits the file, and
// that file is in Go's extraction stamp so that an edit re-reads every Go file (rule 51).

package main

import "encoding/json"

// BoundaryRule is one entry under `boundaries:`, matched against a call's dotted form.
type BoundaryRule struct {
	Kind      string   `json:"kind"`
	Direction string   `json:"direction"`
	Salience  string   `json:"salience"`
	Exact     []string `json:"exact"`
	Prefix    []string `json:"prefix"`
	Method    []string `json:"method"`
	Subscript []string `json:"subscript"`
	Contains  []string `json:"contains"`
	TargetArg *int     `json:"target_arg"`
}

// Rules is the rules document. Keys this reader does not read are ignored by design: the
// document is the host's, and a key added for another purpose is not this reader's to
// refuse.
type Rules struct {
	Boundaries []BoundaryRule `json:"boundaries"`
	EntryNames []string       `json:"entry_names"`
	Builtins   []string       `json:"builtins"`
}

func parseRules(raw any) Rules {
	var r Rules
	if raw == nil {
		return r
	}
	b, err := json.Marshal(raw)
	if err != nil {
		note("the rules document could not be re-encoded: %v", err)
		return r
	}
	if err := json.Unmarshal(b, &r); err != nil {
		note("the rules document is not the shape this reader reads: %v", err)
	}
	return r
}
