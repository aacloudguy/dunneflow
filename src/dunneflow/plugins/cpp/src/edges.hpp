// Every call's far end, decided once every file has been parsed.
//
// Chunk 1 of the plan carries only the seam: what each parse found is gathered here, and
// the reader declares `supplies_edges: false` until the decision is written (chunk 3).

#pragma once

#include <functional>
#include <string>
#include <vector>

#include "extract.hpp"
#include "json.hpp"

namespace edges {

constexpr bool SUPPLIES = false;

struct Tree {
    std::vector<extract::Site> sites;
    std::vector<extract::Def> defs;
    std::vector<extract::Over> overs;
    std::vector<std::pair<std::string, std::string>> bases;
    std::vector<std::string> read_beyond;
    long fatal_files = 0, files = 0, skipped_lines = 0;

    void add(extract::Result& r) {
        files++;
        if (r.fatal) fatal_files++;
        skipped_lines += r.skipped_lines;
        for (auto& s : r.sites) sites.push_back(std::move(s));
        for (auto& d : r.defs) defs.push_back(std::move(d));
        for (auto& o : r.overs) overs.push_back(std::move(o));
        for (auto& b : r.bases) bases.push_back(std::move(b));
    }
};

inline void emit(Tree& t, const std::function<void(const std::string&)>& edge,
                 const std::function<void(const std::string&)>& done) {
    (void)t;
    (void)edge;
    done("\"supplied\":0,\"outside\":0,\"unknown\":0");
}

}  // namespace edges
