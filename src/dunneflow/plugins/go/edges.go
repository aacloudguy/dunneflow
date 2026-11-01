// Where each call goes, answered by `go/types` over the whole module. Filled by chunk 3.

package main

type harvest struct {
	edges   []SuppliedEdge
	outside int
	unknown int
	notes   []string
}

func collectEdges(root string, files []string, rules *Rules) harvest {
	_, _, _ = root, files, rules
	return harvest{}
}
