// JSON, both ways, written out: the standard library has none and this reader vendors
// nothing but libclang's headers (design rule 14).
//
// **`write_string` is the one place a string is escaped.** Every frame, every fact and
// every self-test comparison goes through it, so the wire's escaping is decided once.
// Non-ASCII is written as UTF-8 and never as `\u` escapes: the text is already valid UTF-8
// (`text.hpp` saw to that), and the host's decoder reads either.

#pragma once

#include <cstdint>
#include <cstdio>
#include <map>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

namespace json {

// --------------------------------------------------------------------- writing --- //

inline void write_string(std::string& out, const std::string& s) {
    out += '"';
    for (unsigned char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            case '\b': out += "\\b"; break;
            case '\f': out += "\\f"; break;
            default:
                if (c < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof buf, "\\u%04x", c);
                    out += buf;
                } else {
                    out += static_cast<char>(c);
                }
        }
    }
    out += '"';
}

inline void write(std::string& out, const std::string& s) { write_string(out, s); }
inline void write(std::string& out, const char* s) { write_string(out, s); }
inline void write(std::string& out, bool b) { out += b ? "true" : "false"; }
inline void write(std::string& out, int64_t n) { out += std::to_string(n); }
inline void write(std::string& out, int n) { out += std::to_string(n); }
inline void write(std::string& out, double d) {
    char buf[32];
    std::snprintf(buf, sizeof buf, "%.17g", d);
    out += buf;
}

template <typename T>
auto write(std::string& out, const T& record) -> decltype(record.write_json(out)) {
    record.write_json(out);
}

template <typename T>
void write(std::string& out, const std::optional<T>& v) {
    if (v) {
        write(out, *v);
    } else {
        out += "null";
    }
}

template <typename T>
void write(std::string& out, const std::vector<T>& xs) {
    out += '[';
    bool first = true;
    for (const auto& x : xs) {
        if (!first) out += ',';
        first = false;
        write(out, x);
    }
    out += ']';
}

template <typename T>
void write(std::string& out, const std::map<std::string, T>& m) {
    out += '{';
    bool first = true;
    for (const auto& [k, v] : m) {
        if (!first) out += ',';
        first = false;
        write_string(out, k);
        out += ':';
        write(out, v);
    }
    out += '}';
}

template <typename T>
void field(std::string& out, bool& first, const char* name, const T& v) {
    if (!first) out += ',';
    first = false;
    write_string(out, name);
    out += ':';
    write(out, v);
}

// --------------------------------------------------------------------- reading --- //

struct Value;
using Array = std::vector<Value>;
using Object = std::map<std::string, Value>;

// One parsed value. Numbers are kept as doubles and as integers when they are whole, which
// is every number the protocol sends (ids, counts, indices).
struct Value {
    enum Kind { Null, Bool, Number, String, List, Map } kind = Null;
    bool b = false;
    double n = 0;
    int64_t i = 0;
    std::string s;
    std::shared_ptr<Array> a;
    std::shared_ptr<Object> o;

    bool is_null() const { return kind == Null; }
    bool is_string() const { return kind == String; }
    bool is_list() const { return kind == List; }
    bool is_map() const { return kind == Map; }

    // The member, or a null value: a key the host did not send reads as absent.
    const Value& operator[](const std::string& key) const {
        static const Value none;
        if (kind != Map) return none;
        auto it = o->find(key);
        return it == o->end() ? none : it->second;
    }
    const Array& list() const {
        static const Array none;
        return kind == List ? *a : none;
    }
    const Object& map() const {
        static const Object none;
        return kind == Map ? *o : none;
    }
    std::string str(const std::string& fallback = "") const {
        return kind == String ? s : fallback;
    }
    int64_t integer(int64_t fallback = 0) const { return kind == Number ? i : fallback; }
    bool boolean(bool fallback = false) const { return kind == Bool ? b : fallback; }
    std::vector<std::string> strings() const {
        std::vector<std::string> out;
        for (const auto& v : list())
            if (v.is_string()) out.push_back(v.s);
        return out;
    }
};

class Parser {
public:
    explicit Parser(const std::string& text) : t_(text) {}

    Value parse() {
        Value v = value();
        ws();
        if (p_ != t_.size()) fail("trailing characters");
        return v;
    }

private:
    const std::string& t_;
    size_t p_ = 0;

    [[noreturn]] void fail(const char* why) {
        throw std::runtime_error(std::string("JSON: ") + why + " at offset " + std::to_string(p_));
    }
    void ws() {
        while (p_ < t_.size() && (t_[p_] == ' ' || t_[p_] == '\t' || t_[p_] == '\n' || t_[p_] == '\r')) p_++;
    }
    bool eat(char c) {
        ws();
        if (p_ < t_.size() && t_[p_] == c) {
            p_++;
            return true;
        }
        return false;
    }
    void expect(char c) {
        if (!eat(c)) fail("unexpected character");
    }
    void word(const char* w) {
        for (const char* q = w; *q; q++, p_++)
            if (p_ >= t_.size() || t_[p_] != *q) fail("bad literal");
    }

    Value value() {
        ws();
        if (p_ >= t_.size()) fail("unexpected end");
        Value v;
        char c = t_[p_];
        if (c == '{') {
            p_++;
            v.kind = Value::Map;
            v.o = std::make_shared<Object>();
            if (eat('}')) return v;
            do {
                ws();
                std::string k = string();
                expect(':');
                (*v.o)[k] = value();
            } while (eat(','));
            expect('}');
        } else if (c == '[') {
            p_++;
            v.kind = Value::List;
            v.a = std::make_shared<Array>();
            if (eat(']')) return v;
            do {
                v.a->push_back(value());
            } while (eat(','));
            expect(']');
        } else if (c == '"') {
            v.kind = Value::String;
            v.s = string();
        } else if (c == 't') {
            word("true");
            v.kind = Value::Bool;
            v.b = true;
        } else if (c == 'f') {
            word("false");
            v.kind = Value::Bool;
        } else if (c == 'n') {
            word("null");
        } else {
            size_t start = p_;
            bool whole = true;
            if (t_[p_] == '-') p_++;
            while (p_ < t_.size() && (isdigit(static_cast<unsigned char>(t_[p_])) || t_[p_] == '.' ||
                                      t_[p_] == 'e' || t_[p_] == 'E' || t_[p_] == '+' || t_[p_] == '-')) {
                if (!isdigit(static_cast<unsigned char>(t_[p_]))) whole = false;
                p_++;
            }
            if (p_ == start) fail("unexpected character");
            std::string num = t_.substr(start, p_ - start);
            v.kind = Value::Number;
            v.n = std::stod(num);
            v.i = whole ? std::stoll(num) : static_cast<int64_t>(v.n);
        }
        return v;
    }

    static void utf8(std::string& out, uint32_t cp) {
        if (cp < 0x80) {
            out += static_cast<char>(cp);
        } else if (cp < 0x800) {
            out += static_cast<char>(0xC0 | (cp >> 6));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else if (cp < 0x10000) {
            out += static_cast<char>(0xE0 | (cp >> 12));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        } else {
            out += static_cast<char>(0xF0 | (cp >> 18));
            out += static_cast<char>(0x80 | ((cp >> 12) & 0x3F));
            out += static_cast<char>(0x80 | ((cp >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (cp & 0x3F));
        }
    }

    uint32_t hex4() {
        if (p_ + 4 > t_.size()) fail("short \\u escape");
        uint32_t v = static_cast<uint32_t>(std::stoul(t_.substr(p_, 4), nullptr, 16));
        p_ += 4;
        return v;
    }

    std::string string() {
        if (p_ >= t_.size() || t_[p_] != '"') fail("expected a string");
        p_++;
        std::string out;
        while (p_ < t_.size() && t_[p_] != '"') {
            char c = t_[p_++];
            if (c != '\\') {
                out += c;
                continue;
            }
            if (p_ >= t_.size()) fail("unterminated escape");
            char e = t_[p_++];
            switch (e) {
                case '"': out += '"'; break;
                case '\\': out += '\\'; break;
                case '/': out += '/'; break;
                case 'b': out += '\b'; break;
                case 'f': out += '\f'; break;
                case 'n': out += '\n'; break;
                case 'r': out += '\r'; break;
                case 't': out += '\t'; break;
                case 'u': {
                    uint32_t cp = hex4();
                    if (cp >= 0xD800 && cp <= 0xDBFF && p_ + 6 <= t_.size() && t_[p_] == '\\' && t_[p_ + 1] == 'u') {
                        size_t save = p_;
                        p_ += 2;
                        uint32_t lo = hex4();
                        if (lo >= 0xDC00 && lo <= 0xDFFF) {
                            cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                        } else {
                            p_ = save;
                        }
                    }
                    // A lone surrogate cannot be UTF-8; Python's json would carry it, and
                    // nothing the host sends holds one. It is written as U+FFFD.
                    if (cp >= 0xD800 && cp <= 0xDFFF) cp = 0xFFFD;
                    utf8(out, cp);
                    break;
                }
                default: fail("bad escape");
            }
        }
        if (p_ >= t_.size()) fail("unterminated string");
        p_++;
        return out;
    }
};

inline Value parse(const std::string& text) { return Parser(text).parse(); }

}  // namespace json
