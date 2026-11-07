// `schema.py`'s types, as this reader has to emit them.
//
// GENERATED — DO NOT EDIT. `uv run python tools/gen_facts_java.py --write`.
// `tests/test_java_reader.py` regenerates it and compares, so a drift between this file
// and `schema.py` fails the suite rather than the map.
//
// A field starts at the schema's default and is written only when it differs from it, so
// leaving it alone sends nothing and the host applies the same default (`codec.encode`
// does the same on the other side). A required object, string or enum starts as `null`,
// and writing a `null` one throws: a forgotten field fails here, not in the map.
//
// `lang` is absent from `Routine` and `DataStructure` on purpose: it is the host's to
// write (`ingest.stamp_lang`).

package dunneflow.reader;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@SuppressWarnings("unused")
public final class Facts {
    private Facts() {}

    /** `schema.SCHEMA_VERSION`. A plugin declaring another is refused by name. */
    public static final long SCHEMA_VERSION = 20;

    /** `schema.ArmKind`. */
    public enum ArmKind implements Json.Writable {
        IF("if"),
        ELIF("elif"),
        ELSE("else"),
        ELSE_IF("else if"),
        CASE("case"),
        DEFAULT("default"),
        TRY("try"),
        EXCEPT("except"),
        CATCH("catch"),
        FINALLY("finally"),
        FOR("for"),
        WHILE("while"),
        DO("do");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        ArmKind(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.BoundaryKind`. */
    public enum BoundaryKind implements Json.Writable {
        ENV("ENV"),
        FILE("FILE"),
        PROCESS("PROCESS"),
        NETWORK("NETWORK"),
        DATABASE("DATABASE"),
        QUEUE("QUEUE"),
        STDIO("STDIO"),
        CLOUD_SDK("CLOUD_SDK"),
        LLM_API("LLM_API"),
        CRYPTO("CRYPTO"),
        LOCAL_IPC("LOCAL_IPC");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        BoundaryKind(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.Confidence`. */
    public enum Confidence implements Json.Writable {
        CERTAIN("CERTAIN"),
        INFERRED("INFERRED");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        Confidence(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.ControlKind`. */
    public enum ControlKind implements Json.Writable {
        LOOP("LOOP"),
        COMPREHENSION("COMPREHENSION"),
        DECISION("DECISION"),
        GUARD("GUARD"),
        HANDLER("HANDLER");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        ControlKind(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.Direction`. */
    public enum Direction implements Json.Writable {
        IN("IN"),
        OUT("OUT"),
        BOTH("BOTH");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        Direction(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.EntrypointKind`. */
    public enum EntrypointKind implements Json.Writable {
        CLI("CLI"),
        MAIN("MAIN"),
        MCP_TOOL("MCP_TOOL"),
        HTTP_ROUTE("HTTP_ROUTE"),
        QUEUE_CONSUMER("QUEUE_CONSUMER"),
        SCHEDULED("SCHEDULED"),
        SIGNAL("SIGNAL"),
        LIBRARY("LIBRARY"),
        IPC_COMMAND("IPC_COMMAND");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        EntrypointKind(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.LiteralKind`. */
    public enum LiteralKind implements Json.Writable {
        PLAIN("PLAIN"),
        INTERPOLATED("INTERPOLATED");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        LiteralKind(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.MacroOrigin`. */
    public enum MacroOrigin implements Json.Writable {
        TREE("tree"),
        OUTSIDE("outside"),
        COMMAND_LINE("command_line"),
        BUILTIN("builtin"),
        UNKNOWN("unknown");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        MacroOrigin(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.MacroPosition`. */
    public enum MacroPosition implements Json.Writable {
        STATEMENT("statement"),
        DECLARATION("declaration"),
        FILE_SCOPE("file_scope");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        MacroPosition(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.StructureKind`. */
    public enum StructureKind implements Json.Writable {
        DATACLASS("DATACLASS"),
        PYDANTIC("PYDANTIC"),
        TYPEDDICT("TYPEDDICT"),
        NAMEDTUPLE("NAMEDTUPLE"),
        ENUM("ENUM"),
        CLASS("CLASS"),
        INTERFACE("INTERFACE"),
        TYPE_ALIAS("TYPE_ALIAS");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        StructureKind(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.TargetKind`. */
    public enum TargetKind implements Json.Writable {
        MODULE_ATTR("MODULE_ATTR"),
        FILE("FILE"),
        NONE("NONE");

        /** The schema's own spelling, which is the wire's. */
        public final String wire;

        TargetKind(String wire) {
            this.wire = wire;
        }

        @Override
        public void writeJson(StringBuilder out) {
            Json.writeString(out, wire);
        }
    }

    /** `schema.Routine`. */
    public static final class Routine implements Json.Writable {
        public String id = null;
        public String name = null;
        public String qualname = null;
        public String module = null;
        public String file = null;
        public long line_start;
        public long line_end;
        public List<Param> params = new ArrayList<>();
        public String returns = null;
        public List<String> decorators = new ArrayList<>();
        public String docstring = null;
        public List<Comment> comments = new ArrayList<>();
        public List<Annotation> annotations = new ArrayList<>();
        public boolean is_async = false;
        public boolean is_method = false;
        public String class_name = null;
        public boolean is_nested = false;
        public String visibility = "public";
        public String body_hash = "";
        public String name_by = "";
        public String body_by = "";
        public long opaque_asm = 0L;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (id == null) {
                throw new IllegalStateException("Routine.id is required and was never set");
            }
            Json.field(out, first, "id", id);
            if (name == null) {
                throw new IllegalStateException("Routine.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (qualname == null) {
                throw new IllegalStateException("Routine.qualname is required and was never set");
            }
            Json.field(out, first, "qualname", qualname);
            if (module == null) {
                throw new IllegalStateException("Routine.module is required and was never set");
            }
            Json.field(out, first, "module", module);
            if (file == null) {
                throw new IllegalStateException("Routine.file is required and was never set");
            }
            Json.field(out, first, "file", file);
            Json.field(out, first, "line_start", line_start);
            Json.field(out, first, "line_end", line_end);
            if (!params.isEmpty()) {
                Json.field(out, first, "params", params);
            }
            if (!Objects.equals(returns, null)) {
                Json.field(out, first, "returns", returns);
            }
            if (!decorators.isEmpty()) {
                Json.field(out, first, "decorators", decorators);
            }
            if (!Objects.equals(docstring, null)) {
                Json.field(out, first, "docstring", docstring);
            }
            if (!comments.isEmpty()) {
                Json.field(out, first, "comments", comments);
            }
            if (!annotations.isEmpty()) {
                Json.field(out, first, "annotations", annotations);
            }
            if (is_async != false) {
                Json.field(out, first, "is_async", is_async);
            }
            if (is_method != false) {
                Json.field(out, first, "is_method", is_method);
            }
            if (!Objects.equals(class_name, null)) {
                Json.field(out, first, "class_name", class_name);
            }
            if (is_nested != false) {
                Json.field(out, first, "is_nested", is_nested);
            }
            if (!Objects.equals(visibility, "public")) {
                Json.field(out, first, "visibility", visibility);
            }
            if (!Objects.equals(body_hash, "")) {
                Json.field(out, first, "body_hash", body_hash);
            }
            if (!Objects.equals(name_by, "")) {
                Json.field(out, first, "name_by", name_by);
            }
            if (!Objects.equals(body_by, "")) {
                Json.field(out, first, "body_by", body_by);
            }
            if (opaque_asm != 0L) {
                Json.field(out, first, "opaque_asm", opaque_asm);
            }
            out.append('}');
        }
    }

    /** `schema.Param`. */
    public static final class Param implements Json.Writable {
        public String name = null;
        public String type = null;
        public String default_ = null;
        public String kind = "positional";

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (name == null) {
                throw new IllegalStateException("Param.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (!Objects.equals(type, null)) {
                Json.field(out, first, "type", type);
            }
            if (!Objects.equals(default_, null)) {
                Json.field(out, first, "default", default_);
            }
            if (!Objects.equals(kind, "positional")) {
                Json.field(out, first, "kind", kind);
            }
            out.append('}');
        }
    }

    /** `schema.Comment`. */
    public static final class Comment implements Json.Writable {
        public String text = null;
        public long line;
        public boolean leading = false;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (text == null) {
                throw new IllegalStateException("Comment.text is required and was never set");
            }
            Json.field(out, first, "text", text);
            Json.field(out, first, "line", line);
            if (leading != false) {
                Json.field(out, first, "leading", leading);
            }
            out.append('}');
        }
    }

    /** `schema.Annotation`. */
    public static final class Annotation implements Json.Writable {
        public String kind = null;
        public String value = null;
        public long line;
        public String text = "";
        public Confidence confidence = Confidence.CERTAIN;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (kind == null) {
                throw new IllegalStateException("Annotation.kind is required and was never set");
            }
            Json.field(out, first, "kind", kind);
            if (value == null) {
                throw new IllegalStateException("Annotation.value is required and was never set");
            }
            Json.field(out, first, "value", value);
            Json.field(out, first, "line", line);
            if (!Objects.equals(text, "")) {
                Json.field(out, first, "text", text);
            }
            if (!Objects.equals(confidence, Confidence.CERTAIN)) {
                Json.field(out, first, "confidence", confidence);
            }
            out.append('}');
        }
    }

    /** `schema.CallSite`. */
    public static final class CallSite implements Json.Writable {
        public String caller_id = null;
        public String callee_expr = null;
        public long line;
        public String callee_id = null;
        public Confidence confidence = Confidence.INFERRED;
        public boolean external = false;
        public boolean at_boundary = false;
        public String site_id = "";
        public List<CallArg> args = new ArrayList<>();
        public boolean is_construction = false;
        public boolean bound_locally = false;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (caller_id == null) {
                throw new IllegalStateException("CallSite.caller_id is required and was never set");
            }
            Json.field(out, first, "caller_id", caller_id);
            if (callee_expr == null) {
                throw new IllegalStateException("CallSite.callee_expr is required and was never set");
            }
            Json.field(out, first, "callee_expr", callee_expr);
            Json.field(out, first, "line", line);
            if (!Objects.equals(callee_id, null)) {
                Json.field(out, first, "callee_id", callee_id);
            }
            if (!Objects.equals(confidence, Confidence.INFERRED)) {
                Json.field(out, first, "confidence", confidence);
            }
            if (external != false) {
                Json.field(out, first, "external", external);
            }
            if (at_boundary != false) {
                Json.field(out, first, "at_boundary", at_boundary);
            }
            if (!Objects.equals(site_id, "")) {
                Json.field(out, first, "site_id", site_id);
            }
            if (!args.isEmpty()) {
                Json.field(out, first, "args", args);
            }
            if (is_construction != false) {
                Json.field(out, first, "is_construction", is_construction);
            }
            if (bound_locally != false) {
                Json.field(out, first, "bound_locally", bound_locally);
            }
            out.append('}');
        }
    }

    /** `schema.CallArg`. */
    public static final class CallArg implements Json.Writable {
        public long idx;
        public String expr = null;
        public String keyword = null;
        public boolean splat = false;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            Json.field(out, first, "idx", idx);
            if (expr == null) {
                throw new IllegalStateException("CallArg.expr is required and was never set");
            }
            Json.field(out, first, "expr", expr);
            if (!Objects.equals(keyword, null)) {
                Json.field(out, first, "keyword", keyword);
            }
            if (splat != false) {
                Json.field(out, first, "splat", splat);
            }
            out.append('}');
        }
    }

    /** `schema.BoundaryHit`. */
    public static final class BoundaryHit implements Json.Writable {
        public String routine_id = null;
        public BoundaryKind kind = null;
        public Direction direction = null;
        public String target = null;
        public long line;
        public String evidence = "";
        public String salience = "normal";
        public String through_macro = "";
        public boolean declared = false;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (routine_id == null) {
                throw new IllegalStateException("BoundaryHit.routine_id is required and was never set");
            }
            Json.field(out, first, "routine_id", routine_id);
            if (kind == null) {
                throw new IllegalStateException("BoundaryHit.kind is required and was never set");
            }
            Json.field(out, first, "kind", kind);
            if (direction == null) {
                throw new IllegalStateException("BoundaryHit.direction is required and was never set");
            }
            Json.field(out, first, "direction", direction);
            if (target == null) {
                throw new IllegalStateException("BoundaryHit.target is required and was never set");
            }
            Json.field(out, first, "target", target);
            Json.field(out, first, "line", line);
            if (!Objects.equals(evidence, "")) {
                Json.field(out, first, "evidence", evidence);
            }
            if (!Objects.equals(salience, "normal")) {
                Json.field(out, first, "salience", salience);
            }
            if (!Objects.equals(through_macro, "")) {
                Json.field(out, first, "through_macro", through_macro);
            }
            if (declared != false) {
                Json.field(out, first, "declared", declared);
            }
            out.append('}');
        }
    }

    /** `schema.DataStructure`. */
    public static final class DataStructure implements Json.Writable {
        public String id = null;
        public String name = null;
        public StructureKind kind = null;
        public String module = null;
        public String file = null;
        public long line;
        public List<Field_> fields = new ArrayList<>();
        public String docstring = null;
        public List<String> bases = new ArrayList<>();
        public List<Annotation> annotations = new ArrayList<>();
        public String name_by = "";

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (id == null) {
                throw new IllegalStateException("DataStructure.id is required and was never set");
            }
            Json.field(out, first, "id", id);
            if (name == null) {
                throw new IllegalStateException("DataStructure.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (kind == null) {
                throw new IllegalStateException("DataStructure.kind is required and was never set");
            }
            Json.field(out, first, "kind", kind);
            if (module == null) {
                throw new IllegalStateException("DataStructure.module is required and was never set");
            }
            Json.field(out, first, "module", module);
            if (file == null) {
                throw new IllegalStateException("DataStructure.file is required and was never set");
            }
            Json.field(out, first, "file", file);
            Json.field(out, first, "line", line);
            if (!fields.isEmpty()) {
                Json.field(out, first, "fields", fields);
            }
            if (!Objects.equals(docstring, null)) {
                Json.field(out, first, "docstring", docstring);
            }
            if (!bases.isEmpty()) {
                Json.field(out, first, "bases", bases);
            }
            if (!annotations.isEmpty()) {
                Json.field(out, first, "annotations", annotations);
            }
            if (!Objects.equals(name_by, "")) {
                Json.field(out, first, "name_by", name_by);
            }
            out.append('}');
        }
    }

    /** `schema.Field_`. */
    public static final class Field_ implements Json.Writable {
        public String name = null;
        public String type = null;
        public String default_ = null;
        public String comment = null;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (name == null) {
                throw new IllegalStateException("Field_.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (!Objects.equals(type, null)) {
                Json.field(out, first, "type", type);
            }
            if (!Objects.equals(default_, null)) {
                Json.field(out, first, "default", default_);
            }
            if (!Objects.equals(comment, null)) {
                Json.field(out, first, "comment", comment);
            }
            out.append('}');
        }
    }

    /** `schema.Entrypoint`. */
    public static final class Entrypoint implements Json.Writable {
        public String id = null;
        public EntrypointKind kind = null;
        public String name = null;
        public String routine_id = null;
        public String module = "";
        public String evidence = "";
        public String group = "";
        public String parent_id = null;
        public String target_expr = "";

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (id == null) {
                throw new IllegalStateException("Entrypoint.id is required and was never set");
            }
            Json.field(out, first, "id", id);
            if (kind == null) {
                throw new IllegalStateException("Entrypoint.kind is required and was never set");
            }
            Json.field(out, first, "kind", kind);
            if (name == null) {
                throw new IllegalStateException("Entrypoint.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (!Objects.equals(routine_id, null)) {
                Json.field(out, first, "routine_id", routine_id);
            }
            if (!Objects.equals(module, "")) {
                Json.field(out, first, "module", module);
            }
            if (!Objects.equals(evidence, "")) {
                Json.field(out, first, "evidence", evidence);
            }
            if (!Objects.equals(group, "")) {
                Json.field(out, first, "group", group);
            }
            if (!Objects.equals(parent_id, null)) {
                Json.field(out, first, "parent_id", parent_id);
            }
            if (!Objects.equals(target_expr, "")) {
                Json.field(out, first, "target_expr", target_expr);
            }
            out.append('}');
        }
    }

    /** `schema.ImportRec`. */
    public static final class ImportRec implements Json.Writable {
        public String module = null;
        public String name = null;
        public String alias = null;
        public boolean is_from;
        public long line;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (module == null) {
                throw new IllegalStateException("ImportRec.module is required and was never set");
            }
            Json.field(out, first, "module", module);
            if (name == null) {
                throw new IllegalStateException("ImportRec.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (alias == null) {
                throw new IllegalStateException("ImportRec.alias is required and was never set");
            }
            Json.field(out, first, "alias", alias);
            Json.field(out, first, "is_from", is_from);
            Json.field(out, first, "line", line);
            out.append('}');
        }
    }

    /** `schema.CliApp`. */
    public static final class CliApp implements Json.Writable {
        public String id = null;
        public String var_ = null;
        public String module = null;
        public String file = null;
        public long line;
        public String title = "";
        public String factory = "";

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (id == null) {
                throw new IllegalStateException("CliApp.id is required and was never set");
            }
            Json.field(out, first, "id", id);
            if (var_ == null) {
                throw new IllegalStateException("CliApp.var is required and was never set");
            }
            Json.field(out, first, "var", var_);
            if (module == null) {
                throw new IllegalStateException("CliApp.module is required and was never set");
            }
            Json.field(out, first, "module", module);
            if (file == null) {
                throw new IllegalStateException("CliApp.file is required and was never set");
            }
            Json.field(out, first, "file", file);
            Json.field(out, first, "line", line);
            if (!Objects.equals(title, "")) {
                Json.field(out, first, "title", title);
            }
            if (!Objects.equals(factory, "")) {
                Json.field(out, first, "factory", factory);
            }
            out.append('}');
        }
    }

    /** `schema.CliMount`. */
    public static final class CliMount implements Json.Writable {
        public String parent_var = null;
        public String parent_module = null;
        public String child_expr = null;
        public String file = null;
        public long line;
        public String name = "";

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (parent_var == null) {
                throw new IllegalStateException("CliMount.parent_var is required and was never set");
            }
            Json.field(out, first, "parent_var", parent_var);
            if (parent_module == null) {
                throw new IllegalStateException("CliMount.parent_module is required and was never set");
            }
            Json.field(out, first, "parent_module", parent_module);
            if (child_expr == null) {
                throw new IllegalStateException("CliMount.child_expr is required and was never set");
            }
            Json.field(out, first, "child_expr", child_expr);
            if (file == null) {
                throw new IllegalStateException("CliMount.file is required and was never set");
            }
            Json.field(out, first, "file", file);
            Json.field(out, first, "line", line);
            if (!Objects.equals(name, "")) {
                Json.field(out, first, "name", name);
            }
            out.append('}');
        }
    }

    /** `schema.SqlStatement`. */
    public static final class SqlStatement implements Json.Writable {
        public String routine_id = null;
        public String operation = null;
        public String direction = null;
        public List<String> tables = new ArrayList<>();
        public String sql = null;
        public long line;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (routine_id == null) {
                throw new IllegalStateException("SqlStatement.routine_id is required and was never set");
            }
            Json.field(out, first, "routine_id", routine_id);
            if (operation == null) {
                throw new IllegalStateException("SqlStatement.operation is required and was never set");
            }
            Json.field(out, first, "operation", operation);
            if (direction == null) {
                throw new IllegalStateException("SqlStatement.direction is required and was never set");
            }
            Json.field(out, first, "direction", direction);
            Json.field(out, first, "tables", tables);
            if (sql == null) {
                throw new IllegalStateException("SqlStatement.sql is required and was never set");
            }
            Json.field(out, first, "sql", sql);
            Json.field(out, first, "line", line);
            out.append('}');
        }
    }

    /** `schema.NetworkCall`. */
    public static final class NetworkCall implements Json.Writable {
        public String routine_id = null;
        public String expr = null;
        public String protocol = null;
        public long line;
        public String verb = "";
        public String destination = "";
        public String port = "";
        public boolean is_async = false;
        public boolean awaited = false;
        public boolean in_async_routine = false;
        public String timeout = "";
        public String retries = "";
        public String tls = "";
        public String payload = "";
        public String headers = "";
        public String topic = "";
        public String ack = "";

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (routine_id == null) {
                throw new IllegalStateException("NetworkCall.routine_id is required and was never set");
            }
            Json.field(out, first, "routine_id", routine_id);
            if (expr == null) {
                throw new IllegalStateException("NetworkCall.expr is required and was never set");
            }
            Json.field(out, first, "expr", expr);
            if (protocol == null) {
                throw new IllegalStateException("NetworkCall.protocol is required and was never set");
            }
            Json.field(out, first, "protocol", protocol);
            Json.field(out, first, "line", line);
            if (!Objects.equals(verb, "")) {
                Json.field(out, first, "verb", verb);
            }
            if (!Objects.equals(destination, "")) {
                Json.field(out, first, "destination", destination);
            }
            if (!Objects.equals(port, "")) {
                Json.field(out, first, "port", port);
            }
            if (is_async != false) {
                Json.field(out, first, "is_async", is_async);
            }
            if (awaited != false) {
                Json.field(out, first, "awaited", awaited);
            }
            if (in_async_routine != false) {
                Json.field(out, first, "in_async_routine", in_async_routine);
            }
            if (!Objects.equals(timeout, "")) {
                Json.field(out, first, "timeout", timeout);
            }
            if (!Objects.equals(retries, "")) {
                Json.field(out, first, "retries", retries);
            }
            if (!Objects.equals(tls, "")) {
                Json.field(out, first, "tls", tls);
            }
            if (!Objects.equals(payload, "")) {
                Json.field(out, first, "payload", payload);
            }
            if (!Objects.equals(headers, "")) {
                Json.field(out, first, "headers", headers);
            }
            if (!Objects.equals(topic, "")) {
                Json.field(out, first, "topic", topic);
            }
            if (!Objects.equals(ack, "")) {
                Json.field(out, first, "ack", ack);
            }
            out.append('}');
        }
    }

    /** `schema.ClassDef_`. */
    public static final class ClassDef_ implements Json.Writable {
        public String name = null;
        public String qualname = null;
        public String module = null;
        public String file = null;
        public long line;
        public List<String> bases = new ArrayList<>();

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (name == null) {
                throw new IllegalStateException("ClassDef_.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (qualname == null) {
                throw new IllegalStateException("ClassDef_.qualname is required and was never set");
            }
            Json.field(out, first, "qualname", qualname);
            if (module == null) {
                throw new IllegalStateException("ClassDef_.module is required and was never set");
            }
            Json.field(out, first, "module", module);
            if (file == null) {
                throw new IllegalStateException("ClassDef_.file is required and was never set");
            }
            Json.field(out, first, "file", file);
            Json.field(out, first, "line", line);
            if (!bases.isEmpty()) {
                Json.field(out, first, "bases", bases);
            }
            out.append('}');
        }
    }

    /** `schema.TableSchema`. */
    public static final class TableSchema implements Json.Writable {
        public String name = null;
        public String file = null;
        public long line;
        public List<List<String>> columns = new ArrayList<>();
        public boolean temporary = false;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (name == null) {
                throw new IllegalStateException("TableSchema.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (file == null) {
                throw new IllegalStateException("TableSchema.file is required and was never set");
            }
            Json.field(out, first, "file", file);
            Json.field(out, first, "line", line);
            if (!columns.isEmpty()) {
                Json.field(out, first, "columns", columns);
            }
            if (temporary != false) {
                Json.field(out, first, "temporary", temporary);
            }
            out.append('}');
        }
    }

    /** `schema.IndexSchema`. */
    public static final class IndexSchema implements Json.Writable {
        public String name = null;
        public String table = null;
        public String columns = null;
        public String file = null;
        public long line;
        public boolean unique = false;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (name == null) {
                throw new IllegalStateException("IndexSchema.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (table == null) {
                throw new IllegalStateException("IndexSchema.table is required and was never set");
            }
            Json.field(out, first, "table", table);
            if (columns == null) {
                throw new IllegalStateException("IndexSchema.columns is required and was never set");
            }
            Json.field(out, first, "columns", columns);
            if (file == null) {
                throw new IllegalStateException("IndexSchema.file is required and was never set");
            }
            Json.field(out, first, "file", file);
            Json.field(out, first, "line", line);
            if (unique != false) {
                Json.field(out, first, "unique", unique);
            }
            out.append('}');
        }
    }

    /** `schema.Artefact`. */
    public static final class Artefact implements Json.Writable {
        public String name = null;
        public String stem = null;
        public String ext = null;
        public String kind = null;
        public String routine_id = null;
        public long line;
        public String literal = null;
        public boolean is_pattern = false;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (name == null) {
                throw new IllegalStateException("Artefact.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (stem == null) {
                throw new IllegalStateException("Artefact.stem is required and was never set");
            }
            Json.field(out, first, "stem", stem);
            if (ext == null) {
                throw new IllegalStateException("Artefact.ext is required and was never set");
            }
            Json.field(out, first, "ext", ext);
            if (kind == null) {
                throw new IllegalStateException("Artefact.kind is required and was never set");
            }
            Json.field(out, first, "kind", kind);
            if (routine_id == null) {
                throw new IllegalStateException("Artefact.routine_id is required and was never set");
            }
            Json.field(out, first, "routine_id", routine_id);
            Json.field(out, first, "line", line);
            if (literal == null) {
                throw new IllegalStateException("Artefact.literal is required and was never set");
            }
            Json.field(out, first, "literal", literal);
            if (is_pattern != false) {
                Json.field(out, first, "is_pattern", is_pattern);
            }
            out.append('}');
        }
    }

    /** `schema.Constant`. */
    public static final class Constant implements Json.Writable {
        public String name = null;
        public String value = null;
        public long line;
        public String type = null;
        public boolean is_final = false;
        public String comment = null;
        public boolean private_ = false;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (name == null) {
                throw new IllegalStateException("Constant.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (value == null) {
                throw new IllegalStateException("Constant.value is required and was never set");
            }
            Json.field(out, first, "value", value);
            Json.field(out, first, "line", line);
            if (!Objects.equals(type, null)) {
                Json.field(out, first, "type", type);
            }
            if (is_final != false) {
                Json.field(out, first, "is_final", is_final);
            }
            if (!Objects.equals(comment, null)) {
                Json.field(out, first, "comment", comment);
            }
            if (private_ != false) {
                Json.field(out, first, "private", private_);
            }
            out.append('}');
        }
    }

    /** `schema.ControlPoint`. */
    public static final class ControlPoint implements Json.Writable {
        public String point_id = null;
        public String routine_id = null;
        public ControlKind kind = null;
        public long line_start;
        public long line_end;
        public long depth;
        public String header = "";
        public long arms = 1L;
        public String exits = "";
        public String word = "";
        public long once_start = 0L;
        public long once_end = 0L;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (point_id == null) {
                throw new IllegalStateException("ControlPoint.point_id is required and was never set");
            }
            Json.field(out, first, "point_id", point_id);
            if (routine_id == null) {
                throw new IllegalStateException("ControlPoint.routine_id is required and was never set");
            }
            Json.field(out, first, "routine_id", routine_id);
            if (kind == null) {
                throw new IllegalStateException("ControlPoint.kind is required and was never set");
            }
            Json.field(out, first, "kind", kind);
            Json.field(out, first, "line_start", line_start);
            Json.field(out, first, "line_end", line_end);
            Json.field(out, first, "depth", depth);
            if (!Objects.equals(header, "")) {
                Json.field(out, first, "header", header);
            }
            if (arms != 1L) {
                Json.field(out, first, "arms", arms);
            }
            if (!Objects.equals(exits, "")) {
                Json.field(out, first, "exits", exits);
            }
            if (!Objects.equals(word, "")) {
                Json.field(out, first, "word", word);
            }
            if (once_start != 0L) {
                Json.field(out, first, "once_start", once_start);
            }
            if (once_end != 0L) {
                Json.field(out, first, "once_end", once_end);
            }
            out.append('}');
        }
    }

    /** `schema.ControlArm`. */
    public static final class ControlArm implements Json.Writable {
        public String point_id = null;
        public String routine_id = null;
        public long idx;
        public ArmKind kind = null;
        public long line_start;
        public long line_end;
        public String header = "";

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (point_id == null) {
                throw new IllegalStateException("ControlArm.point_id is required and was never set");
            }
            Json.field(out, first, "point_id", point_id);
            if (routine_id == null) {
                throw new IllegalStateException("ControlArm.routine_id is required and was never set");
            }
            Json.field(out, first, "routine_id", routine_id);
            Json.field(out, first, "idx", idx);
            if (kind == null) {
                throw new IllegalStateException("ControlArm.kind is required and was never set");
            }
            Json.field(out, first, "kind", kind);
            Json.field(out, first, "line_start", line_start);
            Json.field(out, first, "line_end", line_end);
            if (!Objects.equals(header, "")) {
                Json.field(out, first, "header", header);
            }
            out.append('}');
        }
    }

    /** `schema.StringLiteral`. */
    public static final class StringLiteral implements Json.Writable {
        public String routine_id = null;
        public long line;
        public String text = null;
        public LiteralKind kind = LiteralKind.PLAIN;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (routine_id == null) {
                throw new IllegalStateException("StringLiteral.routine_id is required and was never set");
            }
            Json.field(out, first, "routine_id", routine_id);
            Json.field(out, first, "line", line);
            if (text == null) {
                throw new IllegalStateException("StringLiteral.text is required and was never set");
            }
            Json.field(out, first, "text", text);
            if (!Objects.equals(kind, LiteralKind.PLAIN)) {
                Json.field(out, first, "kind", kind);
            }
            out.append('}');
        }
    }

    /** `schema.IpcRegistration`. */
    public static final class IpcRegistration implements Json.Writable {
        public String name = null;
        public long line;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (name == null) {
                throw new IllegalStateException("IpcRegistration.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            Json.field(out, first, "line", line);
            out.append('}');
        }
    }

    /** `schema.MacroDef`. */
    public static final class MacroDef implements Json.Writable {
        public String id = null;
        public String name = null;
        public String file = null;
        public long line;
        public MacroOrigin origin = null;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (id == null) {
                throw new IllegalStateException("MacroDef.id is required and was never set");
            }
            Json.field(out, first, "id", id);
            if (name == null) {
                throw new IllegalStateException("MacroDef.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            if (file == null) {
                throw new IllegalStateException("MacroDef.file is required and was never set");
            }
            Json.field(out, first, "file", file);
            Json.field(out, first, "line", line);
            if (origin == null) {
                throw new IllegalStateException("MacroDef.origin is required and was never set");
            }
            Json.field(out, first, "origin", origin);
            out.append('}');
        }
    }

    /** `schema.MacroSite`. */
    public static final class MacroSite implements Json.Writable {
        public String def_id = null;
        public String name = null;
        public long line;
        public MacroPosition position = null;
        public String routine_id = null;
        public String shadows = "";

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (def_id == null) {
                throw new IllegalStateException("MacroSite.def_id is required and was never set");
            }
            Json.field(out, first, "def_id", def_id);
            if (name == null) {
                throw new IllegalStateException("MacroSite.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            Json.field(out, first, "line", line);
            if (position == null) {
                throw new IllegalStateException("MacroSite.position is required and was never set");
            }
            Json.field(out, first, "position", position);
            if (!Objects.equals(routine_id, null)) {
                Json.field(out, first, "routine_id", routine_id);
            }
            if (!Objects.equals(shadows, "")) {
                Json.field(out, first, "shadows", shadows);
            }
            out.append('}');
        }
    }

    /** `schema.FileFacts`. */
    public static final class FileFacts implements Json.Writable {
        public String path = null;
        public String lang = null;
        public String module = null;
        public String content_hash = null;
        public String doc = "";
        public List<Routine> routines = new ArrayList<>();
        public List<CallSite> calls = new ArrayList<>();
        public List<BoundaryHit> boundaries = new ArrayList<>();
        public List<DataStructure> structures = new ArrayList<>();
        public List<Entrypoint> entrypoints = new ArrayList<>();
        public List<ImportRec> imports = new ArrayList<>();
        public List<CliApp> cli_apps = new ArrayList<>();
        public List<CliMount> cli_mounts = new ArrayList<>();
        public List<SqlStatement> sql = new ArrayList<>();
        public List<NetworkCall> network = new ArrayList<>();
        public List<ClassDef_> classes = new ArrayList<>();
        public List<TableSchema> tables = new ArrayList<>();
        public List<IndexSchema> indexes = new ArrayList<>();
        public List<Artefact> artefacts = new ArrayList<>();
        public List<Constant> constants = new ArrayList<>();
        public List<ControlPoint> control = new ArrayList<>();
        public List<ControlArm> control_arms = new ArrayList<>();
        public List<StringLiteral> literals = new ArrayList<>();
        public Routine module_scope = null;
        public long literals_dropped = 0L;
        public long tests_dropped = 0L;
        public String read_through = "";
        public List<IpcRegistration> ipc_registrations = new ArrayList<>();
        public List<MacroDef> macro_defs = new ArrayList<>();
        public List<MacroSite> macro_sites = new ArrayList<>();
        public long macro_directive_uses = 0L;
        public long skipped_lines = 0L;
        public String first_missing = "";
        public List<String> errors = new ArrayList<>();

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (path == null) {
                throw new IllegalStateException("FileFacts.path is required and was never set");
            }
            Json.field(out, first, "path", path);
            if (lang == null) {
                throw new IllegalStateException("FileFacts.lang is required and was never set");
            }
            Json.field(out, first, "lang", lang);
            if (module == null) {
                throw new IllegalStateException("FileFacts.module is required and was never set");
            }
            Json.field(out, first, "module", module);
            if (content_hash == null) {
                throw new IllegalStateException("FileFacts.content_hash is required and was never set");
            }
            Json.field(out, first, "content_hash", content_hash);
            if (!Objects.equals(doc, "")) {
                Json.field(out, first, "doc", doc);
            }
            if (!routines.isEmpty()) {
                Json.field(out, first, "routines", routines);
            }
            if (!calls.isEmpty()) {
                Json.field(out, first, "calls", calls);
            }
            if (!boundaries.isEmpty()) {
                Json.field(out, first, "boundaries", boundaries);
            }
            if (!structures.isEmpty()) {
                Json.field(out, first, "structures", structures);
            }
            if (!entrypoints.isEmpty()) {
                Json.field(out, first, "entrypoints", entrypoints);
            }
            if (!imports.isEmpty()) {
                Json.field(out, first, "imports", imports);
            }
            if (!cli_apps.isEmpty()) {
                Json.field(out, first, "cli_apps", cli_apps);
            }
            if (!cli_mounts.isEmpty()) {
                Json.field(out, first, "cli_mounts", cli_mounts);
            }
            if (!sql.isEmpty()) {
                Json.field(out, first, "sql", sql);
            }
            if (!network.isEmpty()) {
                Json.field(out, first, "network", network);
            }
            if (!classes.isEmpty()) {
                Json.field(out, first, "classes", classes);
            }
            if (!tables.isEmpty()) {
                Json.field(out, first, "tables", tables);
            }
            if (!indexes.isEmpty()) {
                Json.field(out, first, "indexes", indexes);
            }
            if (!artefacts.isEmpty()) {
                Json.field(out, first, "artefacts", artefacts);
            }
            if (!constants.isEmpty()) {
                Json.field(out, first, "constants", constants);
            }
            if (!control.isEmpty()) {
                Json.field(out, first, "control", control);
            }
            if (!control_arms.isEmpty()) {
                Json.field(out, first, "control_arms", control_arms);
            }
            if (!literals.isEmpty()) {
                Json.field(out, first, "literals", literals);
            }
            if (!Objects.equals(module_scope, null)) {
                Json.field(out, first, "module_scope", module_scope);
            }
            if (literals_dropped != 0L) {
                Json.field(out, first, "literals_dropped", literals_dropped);
            }
            if (tests_dropped != 0L) {
                Json.field(out, first, "tests_dropped", tests_dropped);
            }
            if (!Objects.equals(read_through, "")) {
                Json.field(out, first, "read_through", read_through);
            }
            if (!ipc_registrations.isEmpty()) {
                Json.field(out, first, "ipc_registrations", ipc_registrations);
            }
            if (!macro_defs.isEmpty()) {
                Json.field(out, first, "macro_defs", macro_defs);
            }
            if (!macro_sites.isEmpty()) {
                Json.field(out, first, "macro_sites", macro_sites);
            }
            if (macro_directive_uses != 0L) {
                Json.field(out, first, "macro_directive_uses", macro_directive_uses);
            }
            if (skipped_lines != 0L) {
                Json.field(out, first, "skipped_lines", skipped_lines);
            }
            if (!Objects.equals(first_missing, "")) {
                Json.field(out, first, "first_missing", first_missing);
            }
            if (!errors.isEmpty()) {
                Json.field(out, first, "errors", errors);
            }
            out.append('}');
        }
    }

    /** `schema.Answer`. */
    public static final class Answer implements Json.Writable {
        public String file = null;
        public long line;
        public String name = null;

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (file == null) {
                throw new IllegalStateException("Answer.file is required and was never set");
            }
            Json.field(out, first, "file", file);
            Json.field(out, first, "line", line);
            if (name == null) {
                throw new IllegalStateException("Answer.name is required and was never set");
            }
            Json.field(out, first, "name", name);
            out.append('}');
        }
    }

    /** `schema.SuppliedEdge`. */
    public static final class SuppliedEdge implements Json.Writable {
        public String site_id = null;
        public String caller_id = null;
        public String file = "";
        public long line = 0L;
        public String name = "";
        public String how = "";
        public long candidates = 0L;
        public String constructs = "";
        public String frontier = "";
        public String reason = "";
        public List<Answer> answers = new ArrayList<>();

        @Override
        public void writeJson(StringBuilder out) {
            out.append('{');
            boolean[] first = {true};
            if (site_id == null) {
                throw new IllegalStateException("SuppliedEdge.site_id is required and was never set");
            }
            Json.field(out, first, "site_id", site_id);
            if (caller_id == null) {
                throw new IllegalStateException("SuppliedEdge.caller_id is required and was never set");
            }
            Json.field(out, first, "caller_id", caller_id);
            if (!Objects.equals(file, "")) {
                Json.field(out, first, "file", file);
            }
            if (line != 0L) {
                Json.field(out, first, "line", line);
            }
            if (!Objects.equals(name, "")) {
                Json.field(out, first, "name", name);
            }
            if (!Objects.equals(how, "")) {
                Json.field(out, first, "how", how);
            }
            if (candidates != 0L) {
                Json.field(out, first, "candidates", candidates);
            }
            if (!Objects.equals(constructs, "")) {
                Json.field(out, first, "constructs", constructs);
            }
            if (!Objects.equals(frontier, "")) {
                Json.field(out, first, "frontier", frontier);
            }
            if (!Objects.equals(reason, "")) {
                Json.field(out, first, "reason", reason);
            }
            if (!answers.isEmpty()) {
                Json.field(out, first, "answers", answers);
            }
            out.append('}');
        }
    }

}
