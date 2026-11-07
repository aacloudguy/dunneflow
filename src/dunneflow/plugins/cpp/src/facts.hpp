// `schema.py`'s types, as this reader has to emit them.
//
// GENERATED — DO NOT EDIT. `uv run python tools/gen_facts_cpp.py --write`.
// `tests/test_cpp_reader.py` regenerates it and compares, so a drift between this file and
// `schema.py` fails the suite rather than the map.
//
// A field starts at the schema's default and is written only when it differs from it, so
// leaving it alone sends nothing and the host applies the same default (`codec.encode` does
// the same on the other side). A required string or enum is an empty `std::optional`, and
// writing an empty one throws: a forgotten field fails here, not in the map.
//
// `lang` is absent from `Routine` and `DataStructure` on purpose: it is the host's to write
// (`ingest.stamp_lang`).

#pragma once

#include <cstdint>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "json.hpp"

namespace facts {

// `schema.SCHEMA_VERSION`. A plugin declaring another is refused by name.
constexpr int64_t SCHEMA_VERSION = 20;

inline void required(const char* what) {
    throw std::logic_error(std::string(what) + " is required and was never set");
}

// `schema.ArmKind`, by its wire spelling.
namespace ArmKind {
inline const std::string IF = "if";
inline const std::string ELIF = "elif";
inline const std::string ELSE = "else";
inline const std::string ELSE_IF = "else if";
inline const std::string CASE = "case";
inline const std::string DEFAULT = "default";
inline const std::string TRY = "try";
inline const std::string EXCEPT = "except";
inline const std::string CATCH = "catch";
inline const std::string FINALLY = "finally";
inline const std::string FOR = "for";
inline const std::string WHILE = "while";
inline const std::string DO = "do";
}  // namespace ArmKind

// `schema.BoundaryKind`, by its wire spelling.
namespace BoundaryKind {
inline const std::string ENV = "ENV";
inline const std::string FILE = "FILE";
inline const std::string PROCESS = "PROCESS";
inline const std::string NETWORK = "NETWORK";
inline const std::string DATABASE = "DATABASE";
inline const std::string QUEUE = "QUEUE";
inline const std::string STDIO = "STDIO";
inline const std::string CLOUD_SDK = "CLOUD_SDK";
inline const std::string LLM_API = "LLM_API";
inline const std::string CRYPTO = "CRYPTO";
inline const std::string LOCAL_IPC = "LOCAL_IPC";
}  // namespace BoundaryKind

// `schema.Confidence`, by its wire spelling.
namespace Confidence {
inline const std::string CERTAIN = "CERTAIN";
inline const std::string INFERRED = "INFERRED";
}  // namespace Confidence

// `schema.ControlKind`, by its wire spelling.
namespace ControlKind {
inline const std::string LOOP = "LOOP";
inline const std::string COMPREHENSION = "COMPREHENSION";
inline const std::string DECISION = "DECISION";
inline const std::string GUARD = "GUARD";
inline const std::string HANDLER = "HANDLER";
}  // namespace ControlKind

// `schema.Direction`, by its wire spelling.
namespace Direction {
inline const std::string IN = "IN";
inline const std::string OUT = "OUT";
inline const std::string BOTH = "BOTH";
}  // namespace Direction

// `schema.EntrypointKind`, by its wire spelling.
namespace EntrypointKind {
inline const std::string CLI = "CLI";
inline const std::string MAIN = "MAIN";
inline const std::string MCP_TOOL = "MCP_TOOL";
inline const std::string HTTP_ROUTE = "HTTP_ROUTE";
inline const std::string QUEUE_CONSUMER = "QUEUE_CONSUMER";
inline const std::string SCHEDULED = "SCHEDULED";
inline const std::string SIGNAL = "SIGNAL";
inline const std::string LIBRARY = "LIBRARY";
inline const std::string IPC_COMMAND = "IPC_COMMAND";
}  // namespace EntrypointKind

// `schema.LiteralKind`, by its wire spelling.
namespace LiteralKind {
inline const std::string PLAIN = "PLAIN";
inline const std::string INTERPOLATED = "INTERPOLATED";
}  // namespace LiteralKind

// `schema.MacroOrigin`, by its wire spelling.
namespace MacroOrigin {
inline const std::string TREE = "tree";
inline const std::string OUTSIDE = "outside";
inline const std::string COMMAND_LINE = "command_line";
inline const std::string BUILTIN = "builtin";
inline const std::string UNKNOWN = "unknown";
}  // namespace MacroOrigin

// `schema.MacroPosition`, by its wire spelling.
namespace MacroPosition {
inline const std::string STATEMENT = "statement";
inline const std::string DECLARATION = "declaration";
inline const std::string FILE_SCOPE = "file_scope";
}  // namespace MacroPosition

// `schema.StructureKind`, by its wire spelling.
namespace StructureKind {
inline const std::string DATACLASS = "DATACLASS";
inline const std::string PYDANTIC = "PYDANTIC";
inline const std::string TYPEDDICT = "TYPEDDICT";
inline const std::string NAMEDTUPLE = "NAMEDTUPLE";
inline const std::string ENUM = "ENUM";
inline const std::string CLASS = "CLASS";
inline const std::string INTERFACE = "INTERFACE";
inline const std::string TYPE_ALIAS = "TYPE_ALIAS";
}  // namespace StructureKind

// `schema.TargetKind`, by its wire spelling.
namespace TargetKind {
inline const std::string MODULE_ATTR = "MODULE_ATTR";
inline const std::string FILE = "FILE";
inline const std::string NONE = "NONE";
}  // namespace TargetKind

// `schema.Param`.
struct Param {
    std::optional<std::string> name;
    std::optional<std::string> type;
    std::optional<std::string> default_;
    std::string kind = "positional";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!name) required("Param.name");
        json::field(out, first, "name", *name);
        if (type) json::field(out, first, "type", *type);
        if (default_) json::field(out, first, "default", *default_);
        if (kind != "positional") json::field(out, first, "kind", kind);
        out += '}';
    }
};

// `schema.Comment`.
struct Comment {
    std::optional<std::string> text;
    int64_t line = 0;
    bool leading = false;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!text) required("Comment.text");
        json::field(out, first, "text", *text);
        json::field(out, first, "line", line);
        if (leading != false) json::field(out, first, "leading", leading);
        out += '}';
    }
};

// `schema.Annotation`.
struct Annotation {
    std::optional<std::string> kind;
    std::optional<std::string> value;
    int64_t line = 0;
    std::string text = "";
    std::string confidence = "CERTAIN";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!kind) required("Annotation.kind");
        json::field(out, first, "kind", *kind);
        if (!value) required("Annotation.value");
        json::field(out, first, "value", *value);
        json::field(out, first, "line", line);
        if (text != "") json::field(out, first, "text", text);
        if (confidence != "CERTAIN") json::field(out, first, "confidence", confidence);
        out += '}';
    }
};

// `schema.Routine`.
struct Routine {
    std::optional<std::string> id;
    std::optional<std::string> name;
    std::optional<std::string> qualname;
    std::optional<std::string> module;
    std::optional<std::string> file;
    int64_t line_start = 0;
    int64_t line_end = 0;
    std::vector<Param> params;
    std::optional<std::string> returns;
    std::vector<std::string> decorators;
    std::optional<std::string> docstring;
    std::vector<Comment> comments;
    std::vector<Annotation> annotations;
    bool is_async = false;
    bool is_method = false;
    std::optional<std::string> class_name;
    bool is_nested = false;
    std::string visibility = "public";
    std::string body_hash = "";
    std::string name_by = "";
    std::string body_by = "";
    int64_t opaque_asm = 0;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!id) required("Routine.id");
        json::field(out, first, "id", *id);
        if (!name) required("Routine.name");
        json::field(out, first, "name", *name);
        if (!qualname) required("Routine.qualname");
        json::field(out, first, "qualname", *qualname);
        if (!module) required("Routine.module");
        json::field(out, first, "module", *module);
        if (!file) required("Routine.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line_start", line_start);
        json::field(out, first, "line_end", line_end);
        if (!params.empty()) json::field(out, first, "params", params);
        if (returns) json::field(out, first, "returns", *returns);
        if (!decorators.empty()) json::field(out, first, "decorators", decorators);
        if (docstring) json::field(out, first, "docstring", *docstring);
        if (!comments.empty()) json::field(out, first, "comments", comments);
        if (!annotations.empty()) json::field(out, first, "annotations", annotations);
        if (is_async != false) json::field(out, first, "is_async", is_async);
        if (is_method != false) json::field(out, first, "is_method", is_method);
        if (class_name) json::field(out, first, "class_name", *class_name);
        if (is_nested != false) json::field(out, first, "is_nested", is_nested);
        if (visibility != "public") json::field(out, first, "visibility", visibility);
        if (body_hash != "") json::field(out, first, "body_hash", body_hash);
        if (name_by != "") json::field(out, first, "name_by", name_by);
        if (body_by != "") json::field(out, first, "body_by", body_by);
        if (opaque_asm != 0) json::field(out, first, "opaque_asm", opaque_asm);
        out += '}';
    }
};

// `schema.CallArg`.
struct CallArg {
    int64_t idx = 0;
    std::optional<std::string> expr;
    std::optional<std::string> keyword;
    bool splat = false;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        json::field(out, first, "idx", idx);
        if (!expr) required("CallArg.expr");
        json::field(out, first, "expr", *expr);
        if (keyword) json::field(out, first, "keyword", *keyword);
        if (splat != false) json::field(out, first, "splat", splat);
        out += '}';
    }
};

// `schema.CallSite`.
struct CallSite {
    std::optional<std::string> caller_id;
    std::optional<std::string> callee_expr;
    int64_t line = 0;
    std::optional<std::string> callee_id;
    std::string confidence = "INFERRED";
    bool external = false;
    bool at_boundary = false;
    std::string site_id = "";
    std::vector<CallArg> args;
    bool is_construction = false;
    bool bound_locally = false;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!caller_id) required("CallSite.caller_id");
        json::field(out, first, "caller_id", *caller_id);
        if (!callee_expr) required("CallSite.callee_expr");
        json::field(out, first, "callee_expr", *callee_expr);
        json::field(out, first, "line", line);
        if (callee_id) json::field(out, first, "callee_id", *callee_id);
        if (confidence != "INFERRED") json::field(out, first, "confidence", confidence);
        if (external != false) json::field(out, first, "external", external);
        if (at_boundary != false) json::field(out, first, "at_boundary", at_boundary);
        if (site_id != "") json::field(out, first, "site_id", site_id);
        if (!args.empty()) json::field(out, first, "args", args);
        if (is_construction != false) json::field(out, first, "is_construction", is_construction);
        if (bound_locally != false) json::field(out, first, "bound_locally", bound_locally);
        out += '}';
    }
};

// `schema.BoundaryHit`.
struct BoundaryHit {
    std::optional<std::string> routine_id;
    std::optional<std::string> kind;
    std::optional<std::string> direction;
    std::optional<std::string> target;
    int64_t line = 0;
    std::string evidence = "";
    std::string salience = "normal";
    std::string through_macro = "";
    bool declared = false;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!routine_id) required("BoundaryHit.routine_id");
        json::field(out, first, "routine_id", *routine_id);
        if (!kind) required("BoundaryHit.kind");
        json::field(out, first, "kind", *kind);
        if (!direction) required("BoundaryHit.direction");
        json::field(out, first, "direction", *direction);
        if (!target) required("BoundaryHit.target");
        json::field(out, first, "target", *target);
        json::field(out, first, "line", line);
        if (evidence != "") json::field(out, first, "evidence", evidence);
        if (salience != "normal") json::field(out, first, "salience", salience);
        if (through_macro != "") json::field(out, first, "through_macro", through_macro);
        if (declared != false) json::field(out, first, "declared", declared);
        out += '}';
    }
};

// `schema.Field_`.
struct Field_ {
    std::optional<std::string> name;
    std::optional<std::string> type;
    std::optional<std::string> default_;
    std::optional<std::string> comment;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!name) required("Field_.name");
        json::field(out, first, "name", *name);
        if (type) json::field(out, first, "type", *type);
        if (default_) json::field(out, first, "default", *default_);
        if (comment) json::field(out, first, "comment", *comment);
        out += '}';
    }
};

// `schema.DataStructure`.
struct DataStructure {
    std::optional<std::string> id;
    std::optional<std::string> name;
    std::optional<std::string> kind;
    std::optional<std::string> module;
    std::optional<std::string> file;
    int64_t line = 0;
    std::vector<Field_> fields;
    std::optional<std::string> docstring;
    std::vector<std::string> bases;
    std::vector<Annotation> annotations;
    std::string name_by = "";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!id) required("DataStructure.id");
        json::field(out, first, "id", *id);
        if (!name) required("DataStructure.name");
        json::field(out, first, "name", *name);
        if (!kind) required("DataStructure.kind");
        json::field(out, first, "kind", *kind);
        if (!module) required("DataStructure.module");
        json::field(out, first, "module", *module);
        if (!file) required("DataStructure.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (!fields.empty()) json::field(out, first, "fields", fields);
        if (docstring) json::field(out, first, "docstring", *docstring);
        if (!bases.empty()) json::field(out, first, "bases", bases);
        if (!annotations.empty()) json::field(out, first, "annotations", annotations);
        if (name_by != "") json::field(out, first, "name_by", name_by);
        out += '}';
    }
};

// `schema.Entrypoint`.
struct Entrypoint {
    std::optional<std::string> id;
    std::optional<std::string> kind;
    std::optional<std::string> name;
    std::optional<std::string> routine_id;
    std::string module = "";
    std::string evidence = "";
    std::string group = "";
    std::optional<std::string> parent_id;
    std::string target_expr = "";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!id) required("Entrypoint.id");
        json::field(out, first, "id", *id);
        if (!kind) required("Entrypoint.kind");
        json::field(out, first, "kind", *kind);
        if (!name) required("Entrypoint.name");
        json::field(out, first, "name", *name);
        if (routine_id) json::field(out, first, "routine_id", *routine_id);
        if (module != "") json::field(out, first, "module", module);
        if (evidence != "") json::field(out, first, "evidence", evidence);
        if (group != "") json::field(out, first, "group", group);
        if (parent_id) json::field(out, first, "parent_id", *parent_id);
        if (target_expr != "") json::field(out, first, "target_expr", target_expr);
        out += '}';
    }
};

// `schema.ImportRec`.
struct ImportRec {
    std::optional<std::string> module;
    std::optional<std::string> name;
    std::optional<std::string> alias;
    bool is_from = false;
    int64_t line = 0;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!module) required("ImportRec.module");
        json::field(out, first, "module", *module);
        if (!name) required("ImportRec.name");
        json::field(out, first, "name", *name);
        if (!alias) required("ImportRec.alias");
        json::field(out, first, "alias", *alias);
        json::field(out, first, "is_from", is_from);
        json::field(out, first, "line", line);
        out += '}';
    }
};

// `schema.CliApp`.
struct CliApp {
    std::optional<std::string> id;
    std::optional<std::string> var;
    std::optional<std::string> module;
    std::optional<std::string> file;
    int64_t line = 0;
    std::string title = "";
    std::string factory = "";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!id) required("CliApp.id");
        json::field(out, first, "id", *id);
        if (!var) required("CliApp.var");
        json::field(out, first, "var", *var);
        if (!module) required("CliApp.module");
        json::field(out, first, "module", *module);
        if (!file) required("CliApp.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (title != "") json::field(out, first, "title", title);
        if (factory != "") json::field(out, first, "factory", factory);
        out += '}';
    }
};

// `schema.CliMount`.
struct CliMount {
    std::optional<std::string> parent_var;
    std::optional<std::string> parent_module;
    std::optional<std::string> child_expr;
    std::optional<std::string> file;
    int64_t line = 0;
    std::string name = "";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!parent_var) required("CliMount.parent_var");
        json::field(out, first, "parent_var", *parent_var);
        if (!parent_module) required("CliMount.parent_module");
        json::field(out, first, "parent_module", *parent_module);
        if (!child_expr) required("CliMount.child_expr");
        json::field(out, first, "child_expr", *child_expr);
        if (!file) required("CliMount.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (name != "") json::field(out, first, "name", name);
        out += '}';
    }
};

// `schema.SqlStatement`.
struct SqlStatement {
    std::optional<std::string> routine_id;
    std::optional<std::string> operation;
    std::optional<std::string> direction;
    std::vector<std::string> tables;
    std::optional<std::string> sql;
    int64_t line = 0;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!routine_id) required("SqlStatement.routine_id");
        json::field(out, first, "routine_id", *routine_id);
        if (!operation) required("SqlStatement.operation");
        json::field(out, first, "operation", *operation);
        if (!direction) required("SqlStatement.direction");
        json::field(out, first, "direction", *direction);
        json::field(out, first, "tables", tables);
        if (!sql) required("SqlStatement.sql");
        json::field(out, first, "sql", *sql);
        json::field(out, first, "line", line);
        out += '}';
    }
};

// `schema.NetworkCall`.
struct NetworkCall {
    std::optional<std::string> routine_id;
    std::optional<std::string> expr;
    std::optional<std::string> protocol;
    int64_t line = 0;
    std::string verb = "";
    std::string destination = "";
    std::string port = "";
    bool is_async = false;
    bool awaited = false;
    bool in_async_routine = false;
    std::string timeout = "";
    std::string retries = "";
    std::string tls = "";
    std::string payload = "";
    std::string headers = "";
    std::string topic = "";
    std::string ack = "";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!routine_id) required("NetworkCall.routine_id");
        json::field(out, first, "routine_id", *routine_id);
        if (!expr) required("NetworkCall.expr");
        json::field(out, first, "expr", *expr);
        if (!protocol) required("NetworkCall.protocol");
        json::field(out, first, "protocol", *protocol);
        json::field(out, first, "line", line);
        if (verb != "") json::field(out, first, "verb", verb);
        if (destination != "") json::field(out, first, "destination", destination);
        if (port != "") json::field(out, first, "port", port);
        if (is_async != false) json::field(out, first, "is_async", is_async);
        if (awaited != false) json::field(out, first, "awaited", awaited);
        if (in_async_routine != false) json::field(out, first, "in_async_routine", in_async_routine);
        if (timeout != "") json::field(out, first, "timeout", timeout);
        if (retries != "") json::field(out, first, "retries", retries);
        if (tls != "") json::field(out, first, "tls", tls);
        if (payload != "") json::field(out, first, "payload", payload);
        if (headers != "") json::field(out, first, "headers", headers);
        if (topic != "") json::field(out, first, "topic", topic);
        if (ack != "") json::field(out, first, "ack", ack);
        out += '}';
    }
};

// `schema.ClassDef_`.
struct ClassDef_ {
    std::optional<std::string> name;
    std::optional<std::string> qualname;
    std::optional<std::string> module;
    std::optional<std::string> file;
    int64_t line = 0;
    std::vector<std::string> bases;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!name) required("ClassDef_.name");
        json::field(out, first, "name", *name);
        if (!qualname) required("ClassDef_.qualname");
        json::field(out, first, "qualname", *qualname);
        if (!module) required("ClassDef_.module");
        json::field(out, first, "module", *module);
        if (!file) required("ClassDef_.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (!bases.empty()) json::field(out, first, "bases", bases);
        out += '}';
    }
};

// `schema.TableSchema`.
struct TableSchema {
    std::optional<std::string> name;
    std::optional<std::string> file;
    int64_t line = 0;
    std::vector<std::vector<std::string>> columns;
    bool temporary = false;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!name) required("TableSchema.name");
        json::field(out, first, "name", *name);
        if (!file) required("TableSchema.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (!columns.empty()) json::field(out, first, "columns", columns);
        if (temporary != false) json::field(out, first, "temporary", temporary);
        out += '}';
    }
};

// `schema.IndexSchema`.
struct IndexSchema {
    std::optional<std::string> name;
    std::optional<std::string> table;
    std::optional<std::string> columns;
    std::optional<std::string> file;
    int64_t line = 0;
    bool unique = false;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!name) required("IndexSchema.name");
        json::field(out, first, "name", *name);
        if (!table) required("IndexSchema.table");
        json::field(out, first, "table", *table);
        if (!columns) required("IndexSchema.columns");
        json::field(out, first, "columns", *columns);
        if (!file) required("IndexSchema.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (unique != false) json::field(out, first, "unique", unique);
        out += '}';
    }
};

// `schema.Artefact`.
struct Artefact {
    std::optional<std::string> name;
    std::optional<std::string> stem;
    std::optional<std::string> ext;
    std::optional<std::string> kind;
    std::optional<std::string> routine_id;
    int64_t line = 0;
    std::optional<std::string> literal;
    bool is_pattern = false;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!name) required("Artefact.name");
        json::field(out, first, "name", *name);
        if (!stem) required("Artefact.stem");
        json::field(out, first, "stem", *stem);
        if (!ext) required("Artefact.ext");
        json::field(out, first, "ext", *ext);
        if (!kind) required("Artefact.kind");
        json::field(out, first, "kind", *kind);
        if (!routine_id) required("Artefact.routine_id");
        json::field(out, first, "routine_id", *routine_id);
        json::field(out, first, "line", line);
        if (!literal) required("Artefact.literal");
        json::field(out, first, "literal", *literal);
        if (is_pattern != false) json::field(out, first, "is_pattern", is_pattern);
        out += '}';
    }
};

// `schema.Constant`.
struct Constant {
    std::optional<std::string> name;
    std::optional<std::string> value;
    int64_t line = 0;
    std::optional<std::string> type;
    bool is_final = false;
    std::optional<std::string> comment;
    bool private_ = false;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!name) required("Constant.name");
        json::field(out, first, "name", *name);
        if (!value) required("Constant.value");
        json::field(out, first, "value", *value);
        json::field(out, first, "line", line);
        if (type) json::field(out, first, "type", *type);
        if (is_final != false) json::field(out, first, "is_final", is_final);
        if (comment) json::field(out, first, "comment", *comment);
        if (private_ != false) json::field(out, first, "private", private_);
        out += '}';
    }
};

// `schema.ControlPoint`.
struct ControlPoint {
    std::optional<std::string> point_id;
    std::optional<std::string> routine_id;
    std::optional<std::string> kind;
    int64_t line_start = 0;
    int64_t line_end = 0;
    int64_t depth = 0;
    std::string header = "";
    int64_t arms = 1;
    std::string exits = "";
    std::string word = "";
    int64_t once_start = 0;
    int64_t once_end = 0;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!point_id) required("ControlPoint.point_id");
        json::field(out, first, "point_id", *point_id);
        if (!routine_id) required("ControlPoint.routine_id");
        json::field(out, first, "routine_id", *routine_id);
        if (!kind) required("ControlPoint.kind");
        json::field(out, first, "kind", *kind);
        json::field(out, first, "line_start", line_start);
        json::field(out, first, "line_end", line_end);
        json::field(out, first, "depth", depth);
        if (header != "") json::field(out, first, "header", header);
        if (arms != 1) json::field(out, first, "arms", arms);
        if (exits != "") json::field(out, first, "exits", exits);
        if (word != "") json::field(out, first, "word", word);
        if (once_start != 0) json::field(out, first, "once_start", once_start);
        if (once_end != 0) json::field(out, first, "once_end", once_end);
        out += '}';
    }
};

// `schema.ControlArm`.
struct ControlArm {
    std::optional<std::string> point_id;
    std::optional<std::string> routine_id;
    int64_t idx = 0;
    std::optional<std::string> kind;
    int64_t line_start = 0;
    int64_t line_end = 0;
    std::string header = "";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!point_id) required("ControlArm.point_id");
        json::field(out, first, "point_id", *point_id);
        if (!routine_id) required("ControlArm.routine_id");
        json::field(out, first, "routine_id", *routine_id);
        json::field(out, first, "idx", idx);
        if (!kind) required("ControlArm.kind");
        json::field(out, first, "kind", *kind);
        json::field(out, first, "line_start", line_start);
        json::field(out, first, "line_end", line_end);
        if (header != "") json::field(out, first, "header", header);
        out += '}';
    }
};

// `schema.StringLiteral`.
struct StringLiteral {
    std::optional<std::string> routine_id;
    int64_t line = 0;
    std::optional<std::string> text;
    std::string kind = "PLAIN";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!routine_id) required("StringLiteral.routine_id");
        json::field(out, first, "routine_id", *routine_id);
        json::field(out, first, "line", line);
        if (!text) required("StringLiteral.text");
        json::field(out, first, "text", *text);
        if (kind != "PLAIN") json::field(out, first, "kind", kind);
        out += '}';
    }
};

// `schema.IpcRegistration`.
struct IpcRegistration {
    std::optional<std::string> name;
    int64_t line = 0;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!name) required("IpcRegistration.name");
        json::field(out, first, "name", *name);
        json::field(out, first, "line", line);
        out += '}';
    }
};

// `schema.MacroDef`.
struct MacroDef {
    std::optional<std::string> id;
    std::optional<std::string> name;
    std::optional<std::string> file;
    int64_t line = 0;
    std::optional<std::string> origin;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!id) required("MacroDef.id");
        json::field(out, first, "id", *id);
        if (!name) required("MacroDef.name");
        json::field(out, first, "name", *name);
        if (!file) required("MacroDef.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (!origin) required("MacroDef.origin");
        json::field(out, first, "origin", *origin);
        out += '}';
    }
};

// `schema.MacroSite`.
struct MacroSite {
    std::optional<std::string> def_id;
    std::optional<std::string> name;
    int64_t line = 0;
    std::optional<std::string> position;
    std::optional<std::string> routine_id;
    std::string shadows = "";

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!def_id) required("MacroSite.def_id");
        json::field(out, first, "def_id", *def_id);
        if (!name) required("MacroSite.name");
        json::field(out, first, "name", *name);
        json::field(out, first, "line", line);
        if (!position) required("MacroSite.position");
        json::field(out, first, "position", *position);
        if (routine_id) json::field(out, first, "routine_id", *routine_id);
        if (shadows != "") json::field(out, first, "shadows", shadows);
        out += '}';
    }
};

// `schema.FileFacts`.
struct FileFacts {
    std::optional<std::string> path;
    std::optional<std::string> lang;
    std::optional<std::string> module;
    std::optional<std::string> content_hash;
    std::string doc = "";
    std::vector<Routine> routines;
    std::vector<CallSite> calls;
    std::vector<BoundaryHit> boundaries;
    std::vector<DataStructure> structures;
    std::vector<Entrypoint> entrypoints;
    std::vector<ImportRec> imports;
    std::vector<CliApp> cli_apps;
    std::vector<CliMount> cli_mounts;
    std::vector<SqlStatement> sql;
    std::vector<NetworkCall> network;
    std::vector<ClassDef_> classes;
    std::vector<TableSchema> tables;
    std::vector<IndexSchema> indexes;
    std::vector<Artefact> artefacts;
    std::vector<Constant> constants;
    std::vector<ControlPoint> control;
    std::vector<ControlArm> control_arms;
    std::vector<StringLiteral> literals;
    std::optional<Routine> module_scope;
    int64_t literals_dropped = 0;
    int64_t tests_dropped = 0;
    std::string read_through = "";
    std::vector<IpcRegistration> ipc_registrations;
    std::vector<MacroDef> macro_defs;
    std::vector<MacroSite> macro_sites;
    int64_t macro_directive_uses = 0;
    int64_t skipped_lines = 0;
    std::string first_missing = "";
    std::vector<std::string> errors;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!path) required("FileFacts.path");
        json::field(out, first, "path", *path);
        if (!lang) required("FileFacts.lang");
        json::field(out, first, "lang", *lang);
        if (!module) required("FileFacts.module");
        json::field(out, first, "module", *module);
        if (!content_hash) required("FileFacts.content_hash");
        json::field(out, first, "content_hash", *content_hash);
        if (doc != "") json::field(out, first, "doc", doc);
        if (!routines.empty()) json::field(out, first, "routines", routines);
        if (!calls.empty()) json::field(out, first, "calls", calls);
        if (!boundaries.empty()) json::field(out, first, "boundaries", boundaries);
        if (!structures.empty()) json::field(out, first, "structures", structures);
        if (!entrypoints.empty()) json::field(out, first, "entrypoints", entrypoints);
        if (!imports.empty()) json::field(out, first, "imports", imports);
        if (!cli_apps.empty()) json::field(out, first, "cli_apps", cli_apps);
        if (!cli_mounts.empty()) json::field(out, first, "cli_mounts", cli_mounts);
        if (!sql.empty()) json::field(out, first, "sql", sql);
        if (!network.empty()) json::field(out, first, "network", network);
        if (!classes.empty()) json::field(out, first, "classes", classes);
        if (!tables.empty()) json::field(out, first, "tables", tables);
        if (!indexes.empty()) json::field(out, first, "indexes", indexes);
        if (!artefacts.empty()) json::field(out, first, "artefacts", artefacts);
        if (!constants.empty()) json::field(out, first, "constants", constants);
        if (!control.empty()) json::field(out, first, "control", control);
        if (!control_arms.empty()) json::field(out, first, "control_arms", control_arms);
        if (!literals.empty()) json::field(out, first, "literals", literals);
        if (module_scope) json::field(out, first, "module_scope", *module_scope);
        if (literals_dropped != 0) json::field(out, first, "literals_dropped", literals_dropped);
        if (tests_dropped != 0) json::field(out, first, "tests_dropped", tests_dropped);
        if (read_through != "") json::field(out, first, "read_through", read_through);
        if (!ipc_registrations.empty()) json::field(out, first, "ipc_registrations", ipc_registrations);
        if (!macro_defs.empty()) json::field(out, first, "macro_defs", macro_defs);
        if (!macro_sites.empty()) json::field(out, first, "macro_sites", macro_sites);
        if (macro_directive_uses != 0) json::field(out, first, "macro_directive_uses", macro_directive_uses);
        if (skipped_lines != 0) json::field(out, first, "skipped_lines", skipped_lines);
        if (first_missing != "") json::field(out, first, "first_missing", first_missing);
        if (!errors.empty()) json::field(out, first, "errors", errors);
        out += '}';
    }
};

// `schema.Answer`.
struct Answer {
    std::optional<std::string> file;
    int64_t line = 0;
    std::optional<std::string> name;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!file) required("Answer.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (!name) required("Answer.name");
        json::field(out, first, "name", *name);
        out += '}';
    }
};

// `schema.SuppliedEdge`.
struct SuppliedEdge {
    std::optional<std::string> site_id;
    std::optional<std::string> caller_id;
    std::string file = "";
    int64_t line = 0;
    std::string name = "";
    std::string how = "";
    int64_t candidates = 0;
    std::string constructs = "";
    std::string frontier = "";
    std::string reason = "";
    std::vector<Answer> answers;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!site_id) required("SuppliedEdge.site_id");
        json::field(out, first, "site_id", *site_id);
        if (!caller_id) required("SuppliedEdge.caller_id");
        json::field(out, first, "caller_id", *caller_id);
        if (file != "") json::field(out, first, "file", file);
        if (line != 0) json::field(out, first, "line", line);
        if (name != "") json::field(out, first, "name", name);
        if (how != "") json::field(out, first, "how", how);
        if (candidates != 0) json::field(out, first, "candidates", candidates);
        if (constructs != "") json::field(out, first, "constructs", constructs);
        if (frontier != "") json::field(out, first, "frontier", frontier);
        if (reason != "") json::field(out, first, "reason", reason);
        if (!answers.empty()) json::field(out, first, "answers", answers);
        out += '}';
    }
};

// `schema.SuppliedBinding`.
struct SuppliedBinding {
    std::optional<std::string> entrypoint_id;
    std::string file = "";
    int64_t line = 0;
    std::string name = "";
    std::string why = "";
    std::vector<Answer> answers;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!entrypoint_id) required("SuppliedBinding.entrypoint_id");
        json::field(out, first, "entrypoint_id", *entrypoint_id);
        if (file != "") json::field(out, first, "file", file);
        if (line != 0) json::field(out, first, "line", line);
        if (name != "") json::field(out, first, "name", name);
        if (why != "") json::field(out, first, "why", why);
        if (!answers.empty()) json::field(out, first, "answers", answers);
        out += '}';
    }
};

// `schema.SuppliedUse`.
struct SuppliedUse {
    std::optional<std::string> file;
    int64_t line = 0;
    std::optional<std::string> name;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!file) required("SuppliedUse.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (!name) required("SuppliedUse.name");
        json::field(out, first, "name", *name);
        out += '}';
    }
};

// `schema.SuppliedMacroCallee`.
struct SuppliedMacroCallee {
    std::optional<std::string> file;
    int64_t line = 0;
    std::optional<std::string> def_id;
    std::optional<std::string> routine_id;
    std::string callee = "";
    std::string target_file = "";
    int64_t target_line = 0;
    std::string target_name = "";
    int64_t candidates = 0;
    bool indirect = false;
    int64_t count = 1;
    std::vector<BoundaryHit> hits;

    void write_json(std::string& out) const {
        out += '{';
        bool first = true;
        if (!file) required("SuppliedMacroCallee.file");
        json::field(out, first, "file", *file);
        json::field(out, first, "line", line);
        if (!def_id) required("SuppliedMacroCallee.def_id");
        json::field(out, first, "def_id", *def_id);
        if (!routine_id) required("SuppliedMacroCallee.routine_id");
        json::field(out, first, "routine_id", *routine_id);
        if (callee != "") json::field(out, first, "callee", callee);
        if (target_file != "") json::field(out, first, "target_file", target_file);
        if (target_line != 0) json::field(out, first, "target_line", target_line);
        if (target_name != "") json::field(out, first, "target_name", target_name);
        if (candidates != 0) json::field(out, first, "candidates", candidates);
        if (indirect != false) json::field(out, first, "indirect", indirect);
        if (count != 1) json::field(out, first, "count", count);
        if (!hits.empty()) json::field(out, first, "hits", hits);
        out += '}';
    }
};

}  // namespace facts
