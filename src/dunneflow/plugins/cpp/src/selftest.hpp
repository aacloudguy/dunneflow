// The pins. `vectors.json` is the host's answer to every function in `ids.hpp` and to
// `text::decode`, written from `schema.py` and from Python's own decoder by
// `tools/gen_facts_go.py`.
//
// There is no test framework, because the reader takes no dependency it does not need. So
// this is a mode of the reader itself (`--self-test <vectors.json>`), which pytest runs
// through the binary the host built. The exit status is the number of disagreements, each
// named on stderr. A tampered vector was seen to fail before any was believed (rule 59).

#pragma once

#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>

#include "ids.hpp"
#include "json.hpp"
#include "text.hpp"

namespace selftest {

inline int failures = 0;

inline void check(const std::string& what, const std::string& got, const std::string& wanted) {
    if (got != wanted) {
        failures++;
        std::fprintf(stderr, "DISAGREES %s: got %s, wanted %s\n", what.c_str(), got.c_str(), wanted.c_str());
    }
}

inline const json::Array& rows(const json::Value& v, const char* key) {
    const json::Array& r = v[key].list();
    if (r.empty()) {
        failures++;
        std::fprintf(stderr, "DISAGREES %s: no vectors at all, which checks nothing (rule 37)\n", key);
    }
    return r;
}

inline std::string escaped(const std::string& s) {
    std::string out;
    json::write_string(out, s);
    return out;
}

inline int run(const char* path) {
    std::ifstream f(path, std::ios::binary);
    std::stringstream ss;
    ss << f.rdbuf();
    json::Value v = json::parse(ss.str());
    int n = 0;
    for (const auto& r : rows(v, "make_id")) {
        auto l = r.list();
        check("make_id", ids::make_id(l[0].strings()), l[1].str());
        n++;
    }
    for (const auto& r : rows(v, "definition_id")) {
        auto l = r.list();
        check("definition_id " + l[1].str(), ids::definition_id(l[0].str(), l[1].str(), l[2].integer()), l[3].str());
        n++;
    }
    for (const auto& r : rows(v, "entrypoint_id")) {
        auto l = r.list();
        check("entrypoint_id", ids::entrypoint_id(l[0].str(), l[1].strings()), l[2].str());
        n++;
    }
    for (const auto& r : rows(v, "call_site_id")) {
        auto l = r.list();
        check("call_site_id " + l[1].str(), ids::call_site_id(l[0].str(), l[1].str(), l[2].integer()), l[3].str());
        n++;
    }
    for (const auto& r : rows(v, "control_point_id")) {
        auto l = r.list();
        check("control_point_id " + l[1].str(),
              ids::control_point_id(l[0].str(), l[1].str(), l[2].str(), l[3].integer()), l[4].str());
        n++;
    }
    for (const auto& r : rows(v, "hash_source")) {
        auto l = r.list();
        check("hash_source", ids::hash_source(l[0].str()), l[1].str());
        n++;
    }
    for (const auto& r : rows(v, "decode")) {
        auto l = r.list();
        std::string hex = l[0].str(), bytes;
        for (size_t i = 0; i + 1 < hex.size(); i += 2)
            bytes += static_cast<char>(std::stoi(hex.substr(i, 2), nullptr, 16));
        check("decode " + hex, escaped(text::decode(bytes)), escaped(l[1].str()));
        n++;
    }
    std::fprintf(stderr, "%d vectors, %d disagreeing\n", n, failures);
    return failures;
}

}  // namespace selftest
