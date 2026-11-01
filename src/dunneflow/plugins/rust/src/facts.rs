// `schema.py`'s types, as this reader has to emit them.
//
// GENERATED — DO NOT EDIT. `uv run python tools/gen_facts_rs.py --write`.
// `tests/test_rust_reader.py` regenerates it and compares, so a drift between this file
// and `schema.py` fails the suite rather than the map.
//
// A field with a default is written only when it is not its Rust zero, and leaving it
// unset means the schema's default: the key is absent and the host applies it, as
// `codec.encode` does on the other side. A required field is always written.
//
// `lang` is absent from `Routine` and `DataStructure` on purpose: it is the host's to
// write (`ingest.stamp_lang`).

#![allow(dead_code, unused_imports, clippy::all)]

use crate::json::{write_str, ToJson};
use std::collections::BTreeMap;

/// `schema.SCHEMA_VERSION`. A plugin declaring another is refused by name.
pub const SCHEMA_VERSION: i64 = 17;

/// `schema.ArmKind`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum ArmKind {
    #[default]
    If,
    Elif,
    Else,
    ElseIf,
    Case,
    Default,
    Try,
    Except,
    Catch,
    Finally,
    For,
    While,
    Do,
}

impl ArmKind {
    /// The schema's own spelling, which is the wire's.
    pub fn as_str(self) -> &'static str {
        match self {
            ArmKind::If => "if",
            ArmKind::Elif => "elif",
            ArmKind::Else => "else",
            ArmKind::ElseIf => "else if",
            ArmKind::Case => "case",
            ArmKind::Default => "default",
            ArmKind::Try => "try",
            ArmKind::Except => "except",
            ArmKind::Catch => "catch",
            ArmKind::Finally => "finally",
            ArmKind::For => "for",
            ArmKind::While => "while",
            ArmKind::Do => "do",
        }
    }
}

impl ToJson for ArmKind {
    fn write_json(&self, out: &mut String) {
        write_str(out, self.as_str());
    }
}

/// `schema.BoundaryKind`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum BoundaryKind {
    #[default]
    Env,
    File,
    Process,
    Network,
    Database,
    Queue,
    Stdio,
    CloudSdk,
    LlmApi,
    Crypto,
}

impl BoundaryKind {
    /// The schema's own spelling, which is the wire's.
    pub fn as_str(self) -> &'static str {
        match self {
            BoundaryKind::Env => "ENV",
            BoundaryKind::File => "FILE",
            BoundaryKind::Process => "PROCESS",
            BoundaryKind::Network => "NETWORK",
            BoundaryKind::Database => "DATABASE",
            BoundaryKind::Queue => "QUEUE",
            BoundaryKind::Stdio => "STDIO",
            BoundaryKind::CloudSdk => "CLOUD_SDK",
            BoundaryKind::LlmApi => "LLM_API",
            BoundaryKind::Crypto => "CRYPTO",
        }
    }
}

impl ToJson for BoundaryKind {
    fn write_json(&self, out: &mut String) {
        write_str(out, self.as_str());
    }
}

/// `schema.Confidence`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum Confidence {
    #[default]
    Certain,
    Inferred,
}

impl Confidence {
    /// The schema's own spelling, which is the wire's.
    pub fn as_str(self) -> &'static str {
        match self {
            Confidence::Certain => "CERTAIN",
            Confidence::Inferred => "INFERRED",
        }
    }
}

impl ToJson for Confidence {
    fn write_json(&self, out: &mut String) {
        write_str(out, self.as_str());
    }
}

/// `schema.ControlKind`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum ControlKind {
    #[default]
    Loop,
    Comprehension,
    Decision,
    Guard,
    Handler,
}

impl ControlKind {
    /// The schema's own spelling, which is the wire's.
    pub fn as_str(self) -> &'static str {
        match self {
            ControlKind::Loop => "LOOP",
            ControlKind::Comprehension => "COMPREHENSION",
            ControlKind::Decision => "DECISION",
            ControlKind::Guard => "GUARD",
            ControlKind::Handler => "HANDLER",
        }
    }
}

impl ToJson for ControlKind {
    fn write_json(&self, out: &mut String) {
        write_str(out, self.as_str());
    }
}

/// `schema.Direction`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum Direction {
    #[default]
    In,
    Out,
    Both,
}

impl Direction {
    /// The schema's own spelling, which is the wire's.
    pub fn as_str(self) -> &'static str {
        match self {
            Direction::In => "IN",
            Direction::Out => "OUT",
            Direction::Both => "BOTH",
        }
    }
}

impl ToJson for Direction {
    fn write_json(&self, out: &mut String) {
        write_str(out, self.as_str());
    }
}

/// `schema.EntrypointKind`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum EntrypointKind {
    #[default]
    Cli,
    Main,
    McpTool,
    HttpRoute,
    QueueConsumer,
    Scheduled,
    Signal,
    Library,
}

impl EntrypointKind {
    /// The schema's own spelling, which is the wire's.
    pub fn as_str(self) -> &'static str {
        match self {
            EntrypointKind::Cli => "CLI",
            EntrypointKind::Main => "MAIN",
            EntrypointKind::McpTool => "MCP_TOOL",
            EntrypointKind::HttpRoute => "HTTP_ROUTE",
            EntrypointKind::QueueConsumer => "QUEUE_CONSUMER",
            EntrypointKind::Scheduled => "SCHEDULED",
            EntrypointKind::Signal => "SIGNAL",
            EntrypointKind::Library => "LIBRARY",
        }
    }
}

impl ToJson for EntrypointKind {
    fn write_json(&self, out: &mut String) {
        write_str(out, self.as_str());
    }
}

/// `schema.LiteralKind`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum LiteralKind {
    #[default]
    Plain,
    Interpolated,
}

impl LiteralKind {
    /// The schema's own spelling, which is the wire's.
    pub fn as_str(self) -> &'static str {
        match self {
            LiteralKind::Plain => "PLAIN",
            LiteralKind::Interpolated => "INTERPOLATED",
        }
    }
}

impl ToJson for LiteralKind {
    fn write_json(&self, out: &mut String) {
        write_str(out, self.as_str());
    }
}

/// `schema.StructureKind`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum StructureKind {
    #[default]
    Dataclass,
    Pydantic,
    Typeddict,
    Namedtuple,
    Enum,
    Class,
    Interface,
    TypeAlias,
}

impl StructureKind {
    /// The schema's own spelling, which is the wire's.
    pub fn as_str(self) -> &'static str {
        match self {
            StructureKind::Dataclass => "DATACLASS",
            StructureKind::Pydantic => "PYDANTIC",
            StructureKind::Typeddict => "TYPEDDICT",
            StructureKind::Namedtuple => "NAMEDTUPLE",
            StructureKind::Enum => "ENUM",
            StructureKind::Class => "CLASS",
            StructureKind::Interface => "INTERFACE",
            StructureKind::TypeAlias => "TYPE_ALIAS",
        }
    }
}

impl ToJson for StructureKind {
    fn write_json(&self, out: &mut String) {
        write_str(out, self.as_str());
    }
}

/// `schema.TargetKind`.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum TargetKind {
    #[default]
    ModuleAttr,
    File,
    None,
}

impl TargetKind {
    /// The schema's own spelling, which is the wire's.
    pub fn as_str(self) -> &'static str {
        match self {
            TargetKind::ModuleAttr => "MODULE_ATTR",
            TargetKind::File => "FILE",
            TargetKind::None => "NONE",
        }
    }
}

impl ToJson for TargetKind {
    fn write_json(&self, out: &mut String) {
        write_str(out, self.as_str());
    }
}

/// `schema.Routine`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Routine {
    pub id: String,
    pub name: String,
    pub qualname: String,
    pub module: String,
    pub file: String,
    pub line_start: i64,
    pub line_end: i64,
    pub params: Vec<Param>,
    pub returns: Option<String>,
    pub decorators: Vec<String>,
    pub docstring: Option<String>,
    pub comments: Vec<Comment>,
    pub annotations: Vec<Annotation>,
    pub is_async: bool,
    pub is_method: bool,
    pub class_name: Option<String>,
    pub is_nested: bool,
    pub visibility: String,
    pub body_hash: String,
}

impl ToJson for Routine {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "id", &self.id);
        crate::json::field(out, &mut first, "name", &self.name);
        crate::json::field(out, &mut first, "qualname", &self.qualname);
        crate::json::field(out, &mut first, "module", &self.module);
        crate::json::field(out, &mut first, "file", &self.file);
        crate::json::field(out, &mut first, "line_start", &self.line_start);
        crate::json::field(out, &mut first, "line_end", &self.line_end);
        if self.params != zero.params {
            crate::json::field(out, &mut first, "params", &self.params);
        }
        if self.returns != zero.returns {
            crate::json::field(out, &mut first, "returns", &self.returns);
        }
        if self.decorators != zero.decorators {
            crate::json::field(out, &mut first, "decorators", &self.decorators);
        }
        if self.docstring != zero.docstring {
            crate::json::field(out, &mut first, "docstring", &self.docstring);
        }
        if self.comments != zero.comments {
            crate::json::field(out, &mut first, "comments", &self.comments);
        }
        if self.annotations != zero.annotations {
            crate::json::field(out, &mut first, "annotations", &self.annotations);
        }
        if self.is_async != zero.is_async {
            crate::json::field(out, &mut first, "is_async", &self.is_async);
        }
        if self.is_method != zero.is_method {
            crate::json::field(out, &mut first, "is_method", &self.is_method);
        }
        if self.class_name != zero.class_name {
            crate::json::field(out, &mut first, "class_name", &self.class_name);
        }
        if self.is_nested != zero.is_nested {
            crate::json::field(out, &mut first, "is_nested", &self.is_nested);
        }
        if self.visibility != zero.visibility {
            crate::json::field(out, &mut first, "visibility", &self.visibility);
        }
        if self.body_hash != zero.body_hash {
            crate::json::field(out, &mut first, "body_hash", &self.body_hash);
        }
        out.push('}');
    }
}

/// `schema.Param`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Param {
    pub name: String,
    pub r#type: Option<String>,
    pub default: Option<String>,
    pub kind: String,
}

impl ToJson for Param {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "name", &self.name);
        if self.r#type != zero.r#type {
            crate::json::field(out, &mut first, "type", &self.r#type);
        }
        if self.default != zero.default {
            crate::json::field(out, &mut first, "default", &self.default);
        }
        if self.kind != zero.kind {
            crate::json::field(out, &mut first, "kind", &self.kind);
        }
        out.push('}');
    }
}

/// `schema.Comment`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Comment {
    pub text: String,
    pub line: i64,
    pub leading: bool,
}

impl ToJson for Comment {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "text", &self.text);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.leading != zero.leading {
            crate::json::field(out, &mut first, "leading", &self.leading);
        }
        out.push('}');
    }
}

/// `schema.Annotation`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Annotation {
    pub kind: String,
    pub value: String,
    pub line: i64,
    pub text: String,
    pub confidence: Confidence,
}

impl ToJson for Annotation {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "kind", &self.kind);
        crate::json::field(out, &mut first, "value", &self.value);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.text != zero.text {
            crate::json::field(out, &mut first, "text", &self.text);
        }
        if self.confidence != zero.confidence {
            crate::json::field(out, &mut first, "confidence", &self.confidence);
        }
        out.push('}');
    }
}

/// `schema.CallSite`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct CallSite {
    pub caller_id: String,
    pub callee_expr: String,
    pub line: i64,
    pub callee_id: Option<String>,
    pub confidence: Confidence,
    pub external: bool,
    pub at_boundary: bool,
    pub site_id: String,
    pub args: Vec<CallArg>,
    pub is_construction: bool,
    pub bound_locally: bool,
}

impl ToJson for CallSite {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "caller_id", &self.caller_id);
        crate::json::field(out, &mut first, "callee_expr", &self.callee_expr);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.callee_id != zero.callee_id {
            crate::json::field(out, &mut first, "callee_id", &self.callee_id);
        }
        if self.confidence != zero.confidence {
            crate::json::field(out, &mut first, "confidence", &self.confidence);
        }
        if self.external != zero.external {
            crate::json::field(out, &mut first, "external", &self.external);
        }
        if self.at_boundary != zero.at_boundary {
            crate::json::field(out, &mut first, "at_boundary", &self.at_boundary);
        }
        if self.site_id != zero.site_id {
            crate::json::field(out, &mut first, "site_id", &self.site_id);
        }
        if self.args != zero.args {
            crate::json::field(out, &mut first, "args", &self.args);
        }
        if self.is_construction != zero.is_construction {
            crate::json::field(out, &mut first, "is_construction", &self.is_construction);
        }
        if self.bound_locally != zero.bound_locally {
            crate::json::field(out, &mut first, "bound_locally", &self.bound_locally);
        }
        out.push('}');
    }
}

/// `schema.CallArg`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct CallArg {
    pub idx: i64,
    pub expr: String,
    pub keyword: Option<String>,
    pub splat: bool,
}

impl ToJson for CallArg {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "idx", &self.idx);
        crate::json::field(out, &mut first, "expr", &self.expr);
        if self.keyword != zero.keyword {
            crate::json::field(out, &mut first, "keyword", &self.keyword);
        }
        if self.splat != zero.splat {
            crate::json::field(out, &mut first, "splat", &self.splat);
        }
        out.push('}');
    }
}

/// `schema.BoundaryHit`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct BoundaryHit {
    pub routine_id: String,
    pub kind: BoundaryKind,
    pub direction: Direction,
    pub target: String,
    pub line: i64,
    pub evidence: String,
    pub salience: String,
}

impl ToJson for BoundaryHit {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "routine_id", &self.routine_id);
        crate::json::field(out, &mut first, "kind", &self.kind);
        crate::json::field(out, &mut first, "direction", &self.direction);
        crate::json::field(out, &mut first, "target", &self.target);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.evidence != zero.evidence {
            crate::json::field(out, &mut first, "evidence", &self.evidence);
        }
        if self.salience != zero.salience {
            crate::json::field(out, &mut first, "salience", &self.salience);
        }
        out.push('}');
    }
}

/// `schema.DataStructure`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct DataStructure {
    pub id: String,
    pub name: String,
    pub kind: StructureKind,
    pub module: String,
    pub file: String,
    pub line: i64,
    pub fields: Vec<Field_>,
    pub docstring: Option<String>,
    pub bases: Vec<String>,
    pub annotations: Vec<Annotation>,
}

impl ToJson for DataStructure {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "id", &self.id);
        crate::json::field(out, &mut first, "name", &self.name);
        crate::json::field(out, &mut first, "kind", &self.kind);
        crate::json::field(out, &mut first, "module", &self.module);
        crate::json::field(out, &mut first, "file", &self.file);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.fields != zero.fields {
            crate::json::field(out, &mut first, "fields", &self.fields);
        }
        if self.docstring != zero.docstring {
            crate::json::field(out, &mut first, "docstring", &self.docstring);
        }
        if self.bases != zero.bases {
            crate::json::field(out, &mut first, "bases", &self.bases);
        }
        if self.annotations != zero.annotations {
            crate::json::field(out, &mut first, "annotations", &self.annotations);
        }
        out.push('}');
    }
}

/// `schema.Field_`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Field_ {
    pub name: String,
    pub r#type: Option<String>,
    pub default: Option<String>,
    pub comment: Option<String>,
}

impl ToJson for Field_ {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "name", &self.name);
        if self.r#type != zero.r#type {
            crate::json::field(out, &mut first, "type", &self.r#type);
        }
        if self.default != zero.default {
            crate::json::field(out, &mut first, "default", &self.default);
        }
        if self.comment != zero.comment {
            crate::json::field(out, &mut first, "comment", &self.comment);
        }
        out.push('}');
    }
}

/// `schema.Entrypoint`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Entrypoint {
    pub id: String,
    pub kind: EntrypointKind,
    pub name: String,
    pub routine_id: Option<String>,
    pub module: String,
    pub evidence: String,
    pub group: String,
    pub parent_id: Option<String>,
    pub target_expr: String,
}

impl ToJson for Entrypoint {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "id", &self.id);
        crate::json::field(out, &mut first, "kind", &self.kind);
        crate::json::field(out, &mut first, "name", &self.name);
        if self.routine_id != zero.routine_id {
            crate::json::field(out, &mut first, "routine_id", &self.routine_id);
        }
        if self.module != zero.module {
            crate::json::field(out, &mut first, "module", &self.module);
        }
        if self.evidence != zero.evidence {
            crate::json::field(out, &mut first, "evidence", &self.evidence);
        }
        if self.group != zero.group {
            crate::json::field(out, &mut first, "group", &self.group);
        }
        if self.parent_id != zero.parent_id {
            crate::json::field(out, &mut first, "parent_id", &self.parent_id);
        }
        if self.target_expr != zero.target_expr {
            crate::json::field(out, &mut first, "target_expr", &self.target_expr);
        }
        out.push('}');
    }
}

/// `schema.ImportRec`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ImportRec {
    pub module: String,
    pub name: String,
    pub alias: String,
    pub is_from: bool,
    pub line: i64,
}

impl ToJson for ImportRec {
    fn write_json(&self, out: &mut String) {
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "module", &self.module);
        crate::json::field(out, &mut first, "name", &self.name);
        crate::json::field(out, &mut first, "alias", &self.alias);
        crate::json::field(out, &mut first, "is_from", &self.is_from);
        crate::json::field(out, &mut first, "line", &self.line);
        out.push('}');
    }
}

/// `schema.CliApp`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct CliApp {
    pub id: String,
    pub var: String,
    pub module: String,
    pub file: String,
    pub line: i64,
    pub title: String,
    pub factory: String,
}

impl ToJson for CliApp {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "id", &self.id);
        crate::json::field(out, &mut first, "var", &self.var);
        crate::json::field(out, &mut first, "module", &self.module);
        crate::json::field(out, &mut first, "file", &self.file);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.title != zero.title {
            crate::json::field(out, &mut first, "title", &self.title);
        }
        if self.factory != zero.factory {
            crate::json::field(out, &mut first, "factory", &self.factory);
        }
        out.push('}');
    }
}

/// `schema.CliMount`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct CliMount {
    pub parent_var: String,
    pub parent_module: String,
    pub child_expr: String,
    pub file: String,
    pub line: i64,
    pub name: String,
}

impl ToJson for CliMount {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "parent_var", &self.parent_var);
        crate::json::field(out, &mut first, "parent_module", &self.parent_module);
        crate::json::field(out, &mut first, "child_expr", &self.child_expr);
        crate::json::field(out, &mut first, "file", &self.file);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.name != zero.name {
            crate::json::field(out, &mut first, "name", &self.name);
        }
        out.push('}');
    }
}

/// `schema.SqlStatement`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct SqlStatement {
    pub routine_id: String,
    pub operation: String,
    pub direction: String,
    pub tables: Vec<String>,
    pub sql: String,
    pub line: i64,
}

impl ToJson for SqlStatement {
    fn write_json(&self, out: &mut String) {
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "routine_id", &self.routine_id);
        crate::json::field(out, &mut first, "operation", &self.operation);
        crate::json::field(out, &mut first, "direction", &self.direction);
        crate::json::field(out, &mut first, "tables", &self.tables);
        crate::json::field(out, &mut first, "sql", &self.sql);
        crate::json::field(out, &mut first, "line", &self.line);
        out.push('}');
    }
}

/// `schema.NetworkCall`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct NetworkCall {
    pub routine_id: String,
    pub expr: String,
    pub protocol: String,
    pub line: i64,
    pub verb: String,
    pub destination: String,
    pub port: String,
    pub is_async: bool,
    pub awaited: bool,
    pub in_async_routine: bool,
    pub timeout: String,
    pub retries: String,
    pub tls: String,
    pub payload: String,
    pub headers: String,
    pub topic: String,
    pub ack: String,
}

impl ToJson for NetworkCall {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "routine_id", &self.routine_id);
        crate::json::field(out, &mut first, "expr", &self.expr);
        crate::json::field(out, &mut first, "protocol", &self.protocol);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.verb != zero.verb {
            crate::json::field(out, &mut first, "verb", &self.verb);
        }
        if self.destination != zero.destination {
            crate::json::field(out, &mut first, "destination", &self.destination);
        }
        if self.port != zero.port {
            crate::json::field(out, &mut first, "port", &self.port);
        }
        if self.is_async != zero.is_async {
            crate::json::field(out, &mut first, "is_async", &self.is_async);
        }
        if self.awaited != zero.awaited {
            crate::json::field(out, &mut first, "awaited", &self.awaited);
        }
        if self.in_async_routine != zero.in_async_routine {
            crate::json::field(out, &mut first, "in_async_routine", &self.in_async_routine);
        }
        if self.timeout != zero.timeout {
            crate::json::field(out, &mut first, "timeout", &self.timeout);
        }
        if self.retries != zero.retries {
            crate::json::field(out, &mut first, "retries", &self.retries);
        }
        if self.tls != zero.tls {
            crate::json::field(out, &mut first, "tls", &self.tls);
        }
        if self.payload != zero.payload {
            crate::json::field(out, &mut first, "payload", &self.payload);
        }
        if self.headers != zero.headers {
            crate::json::field(out, &mut first, "headers", &self.headers);
        }
        if self.topic != zero.topic {
            crate::json::field(out, &mut first, "topic", &self.topic);
        }
        if self.ack != zero.ack {
            crate::json::field(out, &mut first, "ack", &self.ack);
        }
        out.push('}');
    }
}

/// `schema.ClassDef_`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ClassDef_ {
    pub name: String,
    pub qualname: String,
    pub module: String,
    pub file: String,
    pub line: i64,
    pub bases: Vec<String>,
}

impl ToJson for ClassDef_ {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "name", &self.name);
        crate::json::field(out, &mut first, "qualname", &self.qualname);
        crate::json::field(out, &mut first, "module", &self.module);
        crate::json::field(out, &mut first, "file", &self.file);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.bases != zero.bases {
            crate::json::field(out, &mut first, "bases", &self.bases);
        }
        out.push('}');
    }
}

/// `schema.TableSchema`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct TableSchema {
    pub name: String,
    pub file: String,
    pub line: i64,
    pub columns: Vec<[String; 3]>,
    pub temporary: bool,
}

impl ToJson for TableSchema {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "name", &self.name);
        crate::json::field(out, &mut first, "file", &self.file);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.columns != zero.columns {
            crate::json::field(out, &mut first, "columns", &self.columns);
        }
        if self.temporary != zero.temporary {
            crate::json::field(out, &mut first, "temporary", &self.temporary);
        }
        out.push('}');
    }
}

/// `schema.IndexSchema`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct IndexSchema {
    pub name: String,
    pub table: String,
    pub columns: String,
    pub file: String,
    pub line: i64,
    pub unique: bool,
}

impl ToJson for IndexSchema {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "name", &self.name);
        crate::json::field(out, &mut first, "table", &self.table);
        crate::json::field(out, &mut first, "columns", &self.columns);
        crate::json::field(out, &mut first, "file", &self.file);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.unique != zero.unique {
            crate::json::field(out, &mut first, "unique", &self.unique);
        }
        out.push('}');
    }
}

/// `schema.Artefact`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Artefact {
    pub name: String,
    pub stem: String,
    pub ext: String,
    pub kind: String,
    pub routine_id: String,
    pub line: i64,
    pub literal: String,
    pub is_pattern: bool,
}

impl ToJson for Artefact {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "name", &self.name);
        crate::json::field(out, &mut first, "stem", &self.stem);
        crate::json::field(out, &mut first, "ext", &self.ext);
        crate::json::field(out, &mut first, "kind", &self.kind);
        crate::json::field(out, &mut first, "routine_id", &self.routine_id);
        crate::json::field(out, &mut first, "line", &self.line);
        crate::json::field(out, &mut first, "literal", &self.literal);
        if self.is_pattern != zero.is_pattern {
            crate::json::field(out, &mut first, "is_pattern", &self.is_pattern);
        }
        out.push('}');
    }
}

/// `schema.Constant`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Constant {
    pub name: String,
    pub value: String,
    pub line: i64,
    pub r#type: Option<String>,
    pub is_final: bool,
    pub comment: Option<String>,
    pub private: bool,
}

impl ToJson for Constant {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "name", &self.name);
        crate::json::field(out, &mut first, "value", &self.value);
        crate::json::field(out, &mut first, "line", &self.line);
        if self.r#type != zero.r#type {
            crate::json::field(out, &mut first, "type", &self.r#type);
        }
        if self.is_final != zero.is_final {
            crate::json::field(out, &mut first, "is_final", &self.is_final);
        }
        if self.comment != zero.comment {
            crate::json::field(out, &mut first, "comment", &self.comment);
        }
        if self.private != zero.private {
            crate::json::field(out, &mut first, "private", &self.private);
        }
        out.push('}');
    }
}

/// `schema.ControlPoint`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ControlPoint {
    pub point_id: String,
    pub routine_id: String,
    pub kind: ControlKind,
    pub line_start: i64,
    pub line_end: i64,
    pub depth: i64,
    pub header: String,
    pub arms: i64,
    pub exits: String,
    pub word: String,
    pub once_start: i64,
    pub once_end: i64,
}

impl ToJson for ControlPoint {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "point_id", &self.point_id);
        crate::json::field(out, &mut first, "routine_id", &self.routine_id);
        crate::json::field(out, &mut first, "kind", &self.kind);
        crate::json::field(out, &mut first, "line_start", &self.line_start);
        crate::json::field(out, &mut first, "line_end", &self.line_end);
        crate::json::field(out, &mut first, "depth", &self.depth);
        if self.header != zero.header {
            crate::json::field(out, &mut first, "header", &self.header);
        }
        if self.arms != zero.arms {
            crate::json::field(out, &mut first, "arms", &self.arms);
        }
        if self.exits != zero.exits {
            crate::json::field(out, &mut first, "exits", &self.exits);
        }
        if self.word != zero.word {
            crate::json::field(out, &mut first, "word", &self.word);
        }
        if self.once_start != zero.once_start {
            crate::json::field(out, &mut first, "once_start", &self.once_start);
        }
        if self.once_end != zero.once_end {
            crate::json::field(out, &mut first, "once_end", &self.once_end);
        }
        out.push('}');
    }
}

/// `schema.ControlArm`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct ControlArm {
    pub point_id: String,
    pub routine_id: String,
    pub idx: i64,
    pub kind: ArmKind,
    pub line_start: i64,
    pub line_end: i64,
    pub header: String,
}

impl ToJson for ControlArm {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "point_id", &self.point_id);
        crate::json::field(out, &mut first, "routine_id", &self.routine_id);
        crate::json::field(out, &mut first, "idx", &self.idx);
        crate::json::field(out, &mut first, "kind", &self.kind);
        crate::json::field(out, &mut first, "line_start", &self.line_start);
        crate::json::field(out, &mut first, "line_end", &self.line_end);
        if self.header != zero.header {
            crate::json::field(out, &mut first, "header", &self.header);
        }
        out.push('}');
    }
}

/// `schema.StringLiteral`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct StringLiteral {
    pub routine_id: String,
    pub line: i64,
    pub text: String,
    pub kind: LiteralKind,
}

impl ToJson for StringLiteral {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "routine_id", &self.routine_id);
        crate::json::field(out, &mut first, "line", &self.line);
        crate::json::field(out, &mut first, "text", &self.text);
        if self.kind != zero.kind {
            crate::json::field(out, &mut first, "kind", &self.kind);
        }
        out.push('}');
    }
}

/// `schema.FileFacts`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct FileFacts {
    pub path: String,
    pub lang: String,
    pub module: String,
    pub content_hash: String,
    pub doc: String,
    pub routines: Vec<Routine>,
    pub calls: Vec<CallSite>,
    pub boundaries: Vec<BoundaryHit>,
    pub structures: Vec<DataStructure>,
    pub entrypoints: Vec<Entrypoint>,
    pub imports: Vec<ImportRec>,
    pub cli_apps: Vec<CliApp>,
    pub cli_mounts: Vec<CliMount>,
    pub sql: Vec<SqlStatement>,
    pub network: Vec<NetworkCall>,
    pub classes: Vec<ClassDef_>,
    pub tables: Vec<TableSchema>,
    pub indexes: Vec<IndexSchema>,
    pub artefacts: Vec<Artefact>,
    pub constants: Vec<Constant>,
    pub control: Vec<ControlPoint>,
    pub control_arms: Vec<ControlArm>,
    pub literals: Vec<StringLiteral>,
    pub module_scope: Option<Routine>,
    pub literals_dropped: i64,
    pub tests_dropped: i64,
    pub errors: Vec<String>,
}

impl ToJson for FileFacts {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "path", &self.path);
        crate::json::field(out, &mut first, "lang", &self.lang);
        crate::json::field(out, &mut first, "module", &self.module);
        crate::json::field(out, &mut first, "content_hash", &self.content_hash);
        if self.doc != zero.doc {
            crate::json::field(out, &mut first, "doc", &self.doc);
        }
        if self.routines != zero.routines {
            crate::json::field(out, &mut first, "routines", &self.routines);
        }
        if self.calls != zero.calls {
            crate::json::field(out, &mut first, "calls", &self.calls);
        }
        if self.boundaries != zero.boundaries {
            crate::json::field(out, &mut first, "boundaries", &self.boundaries);
        }
        if self.structures != zero.structures {
            crate::json::field(out, &mut first, "structures", &self.structures);
        }
        if self.entrypoints != zero.entrypoints {
            crate::json::field(out, &mut first, "entrypoints", &self.entrypoints);
        }
        if self.imports != zero.imports {
            crate::json::field(out, &mut first, "imports", &self.imports);
        }
        if self.cli_apps != zero.cli_apps {
            crate::json::field(out, &mut first, "cli_apps", &self.cli_apps);
        }
        if self.cli_mounts != zero.cli_mounts {
            crate::json::field(out, &mut first, "cli_mounts", &self.cli_mounts);
        }
        if self.sql != zero.sql {
            crate::json::field(out, &mut first, "sql", &self.sql);
        }
        if self.network != zero.network {
            crate::json::field(out, &mut first, "network", &self.network);
        }
        if self.classes != zero.classes {
            crate::json::field(out, &mut first, "classes", &self.classes);
        }
        if self.tables != zero.tables {
            crate::json::field(out, &mut first, "tables", &self.tables);
        }
        if self.indexes != zero.indexes {
            crate::json::field(out, &mut first, "indexes", &self.indexes);
        }
        if self.artefacts != zero.artefacts {
            crate::json::field(out, &mut first, "artefacts", &self.artefacts);
        }
        if self.constants != zero.constants {
            crate::json::field(out, &mut first, "constants", &self.constants);
        }
        if self.control != zero.control {
            crate::json::field(out, &mut first, "control", &self.control);
        }
        if self.control_arms != zero.control_arms {
            crate::json::field(out, &mut first, "control_arms", &self.control_arms);
        }
        if self.literals != zero.literals {
            crate::json::field(out, &mut first, "literals", &self.literals);
        }
        if self.module_scope != zero.module_scope {
            crate::json::field(out, &mut first, "module_scope", &self.module_scope);
        }
        if self.literals_dropped != zero.literals_dropped {
            crate::json::field(out, &mut first, "literals_dropped", &self.literals_dropped);
        }
        if self.tests_dropped != zero.tests_dropped {
            crate::json::field(out, &mut first, "tests_dropped", &self.tests_dropped);
        }
        if self.errors != zero.errors {
            crate::json::field(out, &mut first, "errors", &self.errors);
        }
        out.push('}');
    }
}

/// `schema.SuppliedEdge`.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct SuppliedEdge {
    pub site_id: String,
    pub caller_id: String,
    pub file: String,
    pub line: i64,
    pub name: String,
    pub how: String,
    pub candidates: i64,
}

impl ToJson for SuppliedEdge {
    fn write_json(&self, out: &mut String) {
        let zero = Self::default();
        out.push('{');
        let mut first = true;
        crate::json::field(out, &mut first, "site_id", &self.site_id);
        crate::json::field(out, &mut first, "caller_id", &self.caller_id);
        if self.file != zero.file {
            crate::json::field(out, &mut first, "file", &self.file);
        }
        if self.line != zero.line {
            crate::json::field(out, &mut first, "line", &self.line);
        }
        if self.name != zero.name {
            crate::json::field(out, &mut first, "name", &self.name);
        }
        if self.how != zero.how {
            crate::json::field(out, &mut first, "how", &self.how);
        }
        if self.candidates != zero.candidates {
            crate::json::field(out, &mut first, "candidates", &self.candidates);
        }
        out.push('}');
    }
}
