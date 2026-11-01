// Go's fifth of the probe tree: a way in, a boundary, a loop and a branch.

package main

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

const retries = 3

// Setting is one line of a config file.
type Setting struct {
	Key   string
	Value string
}

// loadConfig reads a config file, one line at a time.
func loadConfig(path string) []Setting {
	out := []Setting{}
	file, err := os.Open(path)
	if err != nil {
		return out
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		out = append(out, Setting{strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])})
	}
	return out
}

func root() string {
	if r := os.Getenv("PROBE_ROOT"); r != "" {
		return r
	}
	return "."
}

func main() {
	settings := loadConfig(root() + "/probe.cfg")
	fmt.Printf("%d settings\n", len(settings))
}
