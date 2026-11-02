// The language's rules, as `detectors/go.yaml` declares them and the host sends them.
//
// They arrive with the session and are never baked in: a reader carrying its own copy of
// the YAML is a second answer that stops moving the moment somebody edits the file, and
// that file is in Go's extraction stamp so that an edit re-reads every Go file (rule 51).
// The matching is `BoundaryRule.matches_call` and `RuleSet.network_profile`, transcribed,
// as `plugins/typescript/src/rules.ts` transcribes them.

package main

import (
	"encoding/json"
	"sort"
	"strings"
)

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
	Target    string   `json:"target"`
	// `detectors.ArgCondition`: the rule applies only for some values of one argument.
	WhenArg *ArgCondition `json:"when_arg"`
	// Said on whatever rule matches instead, when `WhenArg` could not decide.
	Undecided string `json:"undecided"`
	// A fixed phrase after the evidence: `c.WriteMsgUnix — can pass file descriptors`.
	Note string `json:"note"`
	// Where the target argument is a composite literal, the field to read the target
	// from: `&net.UnixAddr{Name: p}` is `p`.
	TargetField string `json:"target_field"`
}

// ArgCondition is `when_arg`. Go has no keyword arguments, so only the position is read.
type ArgCondition struct {
	Index *int     `json:"index"`
	In    []string `json:"in"`
	NotIn []string `json:"not_in"`
}

// argValue is one argument as a rule sees it: a string literal's contents, otherwise its
// source text, and whether it was a literal at all.
type argValue struct {
	text    string
	literal bool
}

// decide is `ArgCondition.decide`: yes, no, or (false, false) for undecided. An absent
// argument decides no; a literal or a `not_in` entry decides no; anything else -- a
// variable, a call -- is undecided, and never matches (rule 49).
func (a *ArgCondition) decide(args []argValue) (yes bool, known bool) {
	if a.Index == nil || *a.Index < 0 || *a.Index >= len(args) {
		return false, true
	}
	v := args[*a.Index]
	if contains(a.In, v.text) {
		return true, true
	}
	if v.literal || contains(a.NotIn, v.text) {
		return false, true
	}
	return false, false
}

// Signature is one entry under `signatures:`: a parameter or result type that names a
// boundary before any body touches it.
type Signature struct {
	Type      string `json:"type"`
	Kind      string `json:"kind"`
	Direction string `json:"direction"`
	Note      string `json:"note"`
}

type netLibrary struct {
	Protocol string `json:"protocol"`
	Async    bool   `json:"async"`
}

// Registration is a way in declared by a call: `mux.HandleFunc("/x", h)`.
type Registration struct {
	Kind       string   `json:"kind"`
	Method     []string `json:"method"`
	RouteArg   int      `json:"route_arg"`
	HandlerArg int      `json:"handler_arg"`
	Evidence   string   `json:"evidence"`
}

// Command is a way in declared by a composite literal: `&cobra.Command{Use: "serve"}`.
type Command struct {
	Kind          string   `json:"kind"`
	Type          []string `json:"type"`
	NameField     string   `json:"name_field"`
	HandlerFields []string `json:"handler_fields"`
	Evidence      string   `json:"evidence"`
}

// Rules is the rules document. Keys this reader does not read are ignored by design: the
// document is the host's, and a key added for another purpose is not this reader's to
// refuse.
type Rules struct {
	Boundaries []BoundaryRule `json:"boundaries"`
	EntryNames []string       `json:"entry_names"`
	Builtins   []string       `json:"builtins"`
	// Reader-specific keys, on TypeScript's `routes` precedent: a language's own way of
	// declaring a way in is data in its rules file.
	Registrations []Registration `json:"registrations"`
	Commands      []Command      `json:"commands"`
	Signatures    []Signature    `json:"signatures"`
	Network       struct {
		Libraries map[string]netLibrary `json:"libraries"`
		Verbs     []string              `json:"verbs"`
		// A call that cannot be made without a timeout, and the index of the argument
		// that carries it (`network.timed`, as `rust.yaml` declares it).
		Timed map[string]int `json:"timed"`
	} `json:"network"`

	// Longest prefix first, as `load_rules` sorts them.
	netPrefixes []string
	entryNames  map[string]bool
}

func parseRules(raw any) Rules {
	var r Rules
	if raw != nil {
		b, err := json.Marshal(raw)
		if err != nil {
			note("the rules document could not be re-encoded: %v", err)
		} else if err := json.Unmarshal(b, &r); err != nil {
			note("the rules document is not the shape this reader reads: %v", err)
		}
	}
	for i := range r.Boundaries {
		b := &r.Boundaries[i]
		if b.Direction == "" {
			b.Direction = "BOTH"
		}
		if b.Salience == "" {
			b.Salience = "normal"
		}
		switch b.Target {
		case "", "arg", "receiver_tail":
		default:
			// Refused rather than defaulted, as `rules.ts` refuses it: a strategy nobody
			// reads is a boundary row naming the wrong thing every time (rule 49).
			note("detectors/go.yaml declares target: %s; this reader reads arg and "+
				"receiver_tail, and reads the rule as arg", b.Target)
			b.Target = "arg"
		}
	}
	for p := range r.Network.Libraries {
		r.netPrefixes = append(r.netPrefixes, p)
	}
	sort.Slice(r.netPrefixes, func(i, j int) bool {
		a, b := r.netPrefixes[i], r.netPrefixes[j]
		if len(a) != len(b) {
			return len(a) > len(b)
		}
		return a < b
	})
	r.entryNames = map[string]bool{}
	for _, n := range r.EntryNames {
		r.entryNames[n] = true
	}
	return r
}

func contains(xs []string, s string) bool {
	for _, x := range xs {
		if x == s {
			return true
		}
	}
	return false
}

// matchesCall is `BoundaryRule.matches_call`: the four tests and nothing else.
func (b *BoundaryRule) matchesCall(dotted string) bool {
	if dotted == "" {
		return false
	}
	if contains(b.Exact, dotted) {
		return true
	}
	for _, p := range b.Prefix {
		if strings.HasPrefix(dotted, p) {
			return true
		}
	}
	for _, c := range b.Contains {
		if strings.Contains(dotted, c) {
			return true
		}
	}
	if len(b.Method) > 0 {
		// A bare name is a plain function call, not a method on something.
		if i := strings.LastIndexByte(dotted, '.'); i >= 0 && contains(b.Method, dotted[i+1:]) {
			return true
		}
	}
	return false
}

// matchCall is the first matching rule, so order in the YAML is meaningful. A rule
// conditioned on an argument is decided on `args`; one that cannot be decided does not
// match, and its `undecided` sentence is returned as the blind spot of the rule that does.
func (r *Rules) matchCall(dotted string, args []argValue) (*BoundaryRule, string) {
	var blind []string
	for i := range r.Boundaries {
		b := &r.Boundaries[i]
		if !b.matchesCall(dotted) {
			continue
		}
		if b.WhenArg != nil {
			yes, known := b.WhenArg.decide(args)
			if !known && b.Undecided != "" {
				blind = append(blind, b.Undecided)
			}
			if !yes {
				continue
			}
		}
		return b, strings.Join(blind, "; ")
	}
	return nil, strings.Join(blind, "; ")
}

// matchNetwork is `RuleSet.network_profile`, including the clause that makes a bare key
// exact: a key with a dot is a prefix and a key without one is a name (rule 5).
func (r *Rules) matchNetwork(dotted string) (string, netLibrary, bool) {
	if dotted == "" {
		return "", netLibrary{}, false
	}
	for _, p := range r.netPrefixes {
		if dotted == p || (strings.Contains(p, ".") && strings.HasPrefix(dotted, p)) {
			return p, r.Network.Libraries[p], true
		}
	}
	return "", netLibrary{}, false
}

func (r *Rules) isVerb(word string) bool {
	for _, v := range r.Network.Verbs {
		if strings.EqualFold(v, word) {
			return true
		}
	}
	return false
}
