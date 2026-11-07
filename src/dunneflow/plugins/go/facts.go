// `schema.py`'s types, as this reader has to emit them.
//
// GENERATED — DO NOT EDIT. `uv run python tools/gen_facts_go.py --write`.
// `tests/test_go_reader.py` regenerates it and compares, so a drift between this file and
// `schema.py` fails the suite rather than the map.
//
// A field with a default carries `omitempty`, and leaving it unset means the schema's
// default: the key is absent and the host applies it, as `codec.encode` does on the other
// side. Every list is `List[T]`, which never encodes as `null`.
//
// `lang` is absent from `Routine` and `DataStructure` on purpose: it is the host's to
// write (`ingest.stamp_lang`).

package main

import "encoding/json"

// SchemaVersion is `schema.SCHEMA_VERSION`. A plugin declaring another is refused by name.
const SchemaVersion = 20

// List is a slice that encodes as `[]` when it is nil, because the codec refuses `null`
// where it expects a list.
type List[T any] []T

// MarshalJSON writes `[]` for a nil list.
func (l List[T]) MarshalJSON() ([]byte, error) {
	if l == nil {
		return []byte("[]"), nil
	}
	return json.Marshal([]T(l))
}

// ArmKind is `schema.ArmKind`.
type ArmKind string

// The members of ArmKind.
const (
	ArmKindIf      ArmKind = "if"
	ArmKindElif    ArmKind = "elif"
	ArmKindElse    ArmKind = "else"
	ArmKindElseIf  ArmKind = "else if"
	ArmKindCase    ArmKind = "case"
	ArmKindDefault ArmKind = "default"
	ArmKindTry     ArmKind = "try"
	ArmKindExcept  ArmKind = "except"
	ArmKindCatch   ArmKind = "catch"
	ArmKindFinally ArmKind = "finally"
	ArmKindFor     ArmKind = "for"
	ArmKindWhile   ArmKind = "while"
	ArmKindDo      ArmKind = "do"
)

// BoundaryKind is `schema.BoundaryKind`.
type BoundaryKind string

// The members of BoundaryKind.
const (
	BoundaryKindEnv      BoundaryKind = "ENV"
	BoundaryKindFile     BoundaryKind = "FILE"
	BoundaryKindProcess  BoundaryKind = "PROCESS"
	BoundaryKindNetwork  BoundaryKind = "NETWORK"
	BoundaryKindDatabase BoundaryKind = "DATABASE"
	BoundaryKindQueue    BoundaryKind = "QUEUE"
	BoundaryKindStdio    BoundaryKind = "STDIO"
	BoundaryKindCloudSdk BoundaryKind = "CLOUD_SDK"
	BoundaryKindLlmApi   BoundaryKind = "LLM_API"
	BoundaryKindCrypto   BoundaryKind = "CRYPTO"
	BoundaryKindLocalIpc BoundaryKind = "LOCAL_IPC"
)

// Confidence is `schema.Confidence`.
type Confidence string

// The members of Confidence.
const (
	ConfidenceCertain  Confidence = "CERTAIN"
	ConfidenceInferred Confidence = "INFERRED"
)

// ControlKind is `schema.ControlKind`.
type ControlKind string

// The members of ControlKind.
const (
	ControlKindLoop          ControlKind = "LOOP"
	ControlKindComprehension ControlKind = "COMPREHENSION"
	ControlKindDecision      ControlKind = "DECISION"
	ControlKindGuard         ControlKind = "GUARD"
	ControlKindHandler       ControlKind = "HANDLER"
)

// Direction is `schema.Direction`.
type Direction string

// The members of Direction.
const (
	DirectionIn   Direction = "IN"
	DirectionOut  Direction = "OUT"
	DirectionBoth Direction = "BOTH"
)

// EntrypointKind is `schema.EntrypointKind`.
type EntrypointKind string

// The members of EntrypointKind.
const (
	EntrypointKindCli           EntrypointKind = "CLI"
	EntrypointKindMain          EntrypointKind = "MAIN"
	EntrypointKindMcpTool       EntrypointKind = "MCP_TOOL"
	EntrypointKindHttpRoute     EntrypointKind = "HTTP_ROUTE"
	EntrypointKindQueueConsumer EntrypointKind = "QUEUE_CONSUMER"
	EntrypointKindScheduled     EntrypointKind = "SCHEDULED"
	EntrypointKindSignal        EntrypointKind = "SIGNAL"
	EntrypointKindLibrary       EntrypointKind = "LIBRARY"
	EntrypointKindIpcCommand    EntrypointKind = "IPC_COMMAND"
)

// LiteralKind is `schema.LiteralKind`.
type LiteralKind string

// The members of LiteralKind.
const (
	LiteralKindPlain        LiteralKind = "PLAIN"
	LiteralKindInterpolated LiteralKind = "INTERPOLATED"
)

// MacroOrigin is `schema.MacroOrigin`.
type MacroOrigin string

// The members of MacroOrigin.
const (
	MacroOriginTree        MacroOrigin = "tree"
	MacroOriginOutside     MacroOrigin = "outside"
	MacroOriginCommandLine MacroOrigin = "command_line"
	MacroOriginBuiltin     MacroOrigin = "builtin"
	MacroOriginUnknown     MacroOrigin = "unknown"
)

// MacroPosition is `schema.MacroPosition`.
type MacroPosition string

// The members of MacroPosition.
const (
	MacroPositionStatement   MacroPosition = "statement"
	MacroPositionDeclaration MacroPosition = "declaration"
	MacroPositionFileScope   MacroPosition = "file_scope"
)

// StructureKind is `schema.StructureKind`.
type StructureKind string

// The members of StructureKind.
const (
	StructureKindDataclass  StructureKind = "DATACLASS"
	StructureKindPydantic   StructureKind = "PYDANTIC"
	StructureKindTypeddict  StructureKind = "TYPEDDICT"
	StructureKindNamedtuple StructureKind = "NAMEDTUPLE"
	StructureKindEnum       StructureKind = "ENUM"
	StructureKindClass      StructureKind = "CLASS"
	StructureKindInterface  StructureKind = "INTERFACE"
	StructureKindTypeAlias  StructureKind = "TYPE_ALIAS"
)

// TargetKind is `schema.TargetKind`.
type TargetKind string

// The members of TargetKind.
const (
	TargetKindModuleAttr TargetKind = "MODULE_ATTR"
	TargetKindFile       TargetKind = "FILE"
	TargetKindNone       TargetKind = "NONE"
)

// Routine is `schema.Routine`.
type Routine struct {
	Id          string           `json:"id"`
	Name        string           `json:"name"`
	Qualname    string           `json:"qualname"`
	Module      string           `json:"module"`
	File        string           `json:"file"`
	LineStart   int              `json:"line_start"`
	LineEnd     int              `json:"line_end"`
	Params      List[Param]      `json:"params,omitempty"`
	Returns     *string          `json:"returns,omitempty"`
	Decorators  List[string]     `json:"decorators,omitempty"`
	Docstring   *string          `json:"docstring,omitempty"`
	Comments    List[Comment]    `json:"comments,omitempty"`
	Annotations List[Annotation] `json:"annotations,omitempty"`
	IsAsync     bool             `json:"is_async,omitempty"`
	IsMethod    bool             `json:"is_method,omitempty"`
	ClassName   *string          `json:"class_name,omitempty"`
	IsNested    bool             `json:"is_nested,omitempty"`
	Visibility  string           `json:"visibility,omitempty"`
	BodyHash    string           `json:"body_hash,omitempty"`
	NameBy      string           `json:"name_by,omitempty"`
	BodyBy      string           `json:"body_by,omitempty"`
	OpaqueAsm   int              `json:"opaque_asm,omitempty"`
}

// Param is `schema.Param`.
type Param struct {
	Name    string  `json:"name"`
	Type    *string `json:"type,omitempty"`
	Default *string `json:"default,omitempty"`
	Kind    string  `json:"kind,omitempty"`
}

// Comment is `schema.Comment`.
type Comment struct {
	Text    string `json:"text"`
	Line    int    `json:"line"`
	Leading bool   `json:"leading,omitempty"`
}

// Annotation is `schema.Annotation`.
type Annotation struct {
	Kind       string     `json:"kind"`
	Value      string     `json:"value"`
	Line       int        `json:"line"`
	Text       string     `json:"text,omitempty"`
	Confidence Confidence `json:"confidence,omitempty"`
}

// CallSite is `schema.CallSite`.
type CallSite struct {
	CallerId       string        `json:"caller_id"`
	CalleeExpr     string        `json:"callee_expr"`
	Line           int           `json:"line"`
	CalleeId       *string       `json:"callee_id,omitempty"`
	Confidence     Confidence    `json:"confidence,omitempty"`
	External       bool          `json:"external,omitempty"`
	AtBoundary     bool          `json:"at_boundary,omitempty"`
	SiteId         string        `json:"site_id,omitempty"`
	Args           List[CallArg] `json:"args,omitempty"`
	IsConstruction bool          `json:"is_construction,omitempty"`
	BoundLocally   bool          `json:"bound_locally,omitempty"`
}

// CallArg is `schema.CallArg`.
type CallArg struct {
	Idx     int     `json:"idx"`
	Expr    string  `json:"expr"`
	Keyword *string `json:"keyword,omitempty"`
	Splat   bool    `json:"splat,omitempty"`
}

// BoundaryHit is `schema.BoundaryHit`.
type BoundaryHit struct {
	RoutineId    string       `json:"routine_id"`
	Kind         BoundaryKind `json:"kind"`
	Direction    Direction    `json:"direction"`
	Target       string       `json:"target"`
	Line         int          `json:"line"`
	Evidence     string       `json:"evidence,omitempty"`
	Salience     string       `json:"salience,omitempty"`
	ThroughMacro string       `json:"through_macro,omitempty"`
	Declared     bool         `json:"declared,omitempty"`
}

// DataStructure is `schema.DataStructure`.
type DataStructure struct {
	Id          string           `json:"id"`
	Name        string           `json:"name"`
	Kind        StructureKind    `json:"kind"`
	Module      string           `json:"module"`
	File        string           `json:"file"`
	Line        int              `json:"line"`
	Fields      List[Field]      `json:"fields,omitempty"`
	Docstring   *string          `json:"docstring,omitempty"`
	Bases       List[string]     `json:"bases,omitempty"`
	Annotations List[Annotation] `json:"annotations,omitempty"`
	NameBy      string           `json:"name_by,omitempty"`
}

// Field is `schema.Field_`.
type Field struct {
	Name    string  `json:"name"`
	Type    *string `json:"type,omitempty"`
	Default *string `json:"default,omitempty"`
	Comment *string `json:"comment,omitempty"`
}

// Entrypoint is `schema.Entrypoint`.
type Entrypoint struct {
	Id         string         `json:"id"`
	Kind       EntrypointKind `json:"kind"`
	Name       string         `json:"name"`
	RoutineId  *string        `json:"routine_id,omitempty"`
	Module     string         `json:"module,omitempty"`
	Evidence   string         `json:"evidence,omitempty"`
	Group      string         `json:"group,omitempty"`
	ParentId   *string        `json:"parent_id,omitempty"`
	TargetExpr string         `json:"target_expr,omitempty"`
}

// ImportRec is `schema.ImportRec`.
type ImportRec struct {
	Module string `json:"module"`
	Name   string `json:"name"`
	Alias  string `json:"alias"`
	IsFrom bool   `json:"is_from"`
	Line   int    `json:"line"`
}

// CliApp is `schema.CliApp`.
type CliApp struct {
	Id      string `json:"id"`
	Var     string `json:"var"`
	Module  string `json:"module"`
	File    string `json:"file"`
	Line    int    `json:"line"`
	Title   string `json:"title,omitempty"`
	Factory string `json:"factory,omitempty"`
}

// CliMount is `schema.CliMount`.
type CliMount struct {
	ParentVar    string `json:"parent_var"`
	ParentModule string `json:"parent_module"`
	ChildExpr    string `json:"child_expr"`
	File         string `json:"file"`
	Line         int    `json:"line"`
	Name         string `json:"name,omitempty"`
}

// SqlStatement is `schema.SqlStatement`.
type SqlStatement struct {
	RoutineId string       `json:"routine_id"`
	Operation string       `json:"operation"`
	Direction string       `json:"direction"`
	Tables    List[string] `json:"tables"`
	Sql       string       `json:"sql"`
	Line      int          `json:"line"`
}

// NetworkCall is `schema.NetworkCall`.
type NetworkCall struct {
	RoutineId      string `json:"routine_id"`
	Expr           string `json:"expr"`
	Protocol       string `json:"protocol"`
	Line           int    `json:"line"`
	Verb           string `json:"verb,omitempty"`
	Destination    string `json:"destination,omitempty"`
	Port           string `json:"port,omitempty"`
	IsAsync        bool   `json:"is_async,omitempty"`
	Awaited        bool   `json:"awaited,omitempty"`
	InAsyncRoutine bool   `json:"in_async_routine,omitempty"`
	Timeout        string `json:"timeout,omitempty"`
	Retries        string `json:"retries,omitempty"`
	Tls            string `json:"tls,omitempty"`
	Payload        string `json:"payload,omitempty"`
	Headers        string `json:"headers,omitempty"`
	Topic          string `json:"topic,omitempty"`
	Ack            string `json:"ack,omitempty"`
}

// ClassDef is `schema.ClassDef_`.
type ClassDef struct {
	Name     string       `json:"name"`
	Qualname string       `json:"qualname"`
	Module   string       `json:"module"`
	File     string       `json:"file"`
	Line     int          `json:"line"`
	Bases    List[string] `json:"bases,omitempty"`
}

// TableSchema is `schema.TableSchema`.
type TableSchema struct {
	Name      string          `json:"name"`
	File      string          `json:"file"`
	Line      int             `json:"line"`
	Columns   List[[3]string] `json:"columns,omitempty"`
	Temporary bool            `json:"temporary,omitempty"`
}

// IndexSchema is `schema.IndexSchema`.
type IndexSchema struct {
	Name    string `json:"name"`
	Table   string `json:"table"`
	Columns string `json:"columns"`
	File    string `json:"file"`
	Line    int    `json:"line"`
	Unique  bool   `json:"unique,omitempty"`
}

// Artefact is `schema.Artefact`.
type Artefact struct {
	Name      string `json:"name"`
	Stem      string `json:"stem"`
	Ext       string `json:"ext"`
	Kind      string `json:"kind"`
	RoutineId string `json:"routine_id"`
	Line      int    `json:"line"`
	Literal   string `json:"literal"`
	IsPattern bool   `json:"is_pattern,omitempty"`
}

// Constant is `schema.Constant`.
type Constant struct {
	Name    string  `json:"name"`
	Value   string  `json:"value"`
	Line    int     `json:"line"`
	Type    *string `json:"type,omitempty"`
	IsFinal bool    `json:"is_final,omitempty"`
	Comment *string `json:"comment,omitempty"`
	Private bool    `json:"private,omitempty"`
}

// ControlPoint is `schema.ControlPoint`.
type ControlPoint struct {
	PointId   string      `json:"point_id"`
	RoutineId string      `json:"routine_id"`
	Kind      ControlKind `json:"kind"`
	LineStart int         `json:"line_start"`
	LineEnd   int         `json:"line_end"`
	Depth     int         `json:"depth"`
	Header    string      `json:"header,omitempty"`
	Arms      int         `json:"arms,omitempty"`
	Exits     string      `json:"exits,omitempty"`
	Word      string      `json:"word,omitempty"`
	OnceStart int         `json:"once_start,omitempty"`
	OnceEnd   int         `json:"once_end,omitempty"`
}

// ControlArm is `schema.ControlArm`.
type ControlArm struct {
	PointId   string  `json:"point_id"`
	RoutineId string  `json:"routine_id"`
	Idx       int     `json:"idx"`
	Kind      ArmKind `json:"kind"`
	LineStart int     `json:"line_start"`
	LineEnd   int     `json:"line_end"`
	Header    string  `json:"header,omitempty"`
}

// StringLiteral is `schema.StringLiteral`.
type StringLiteral struct {
	RoutineId string      `json:"routine_id"`
	Line      int         `json:"line"`
	Text      string      `json:"text"`
	Kind      LiteralKind `json:"kind,omitempty"`
}

// IpcRegistration is `schema.IpcRegistration`.
type IpcRegistration struct {
	Name string `json:"name"`
	Line int    `json:"line"`
}

// MacroDef is `schema.MacroDef`.
type MacroDef struct {
	Id     string      `json:"id"`
	Name   string      `json:"name"`
	File   string      `json:"file"`
	Line   int         `json:"line"`
	Origin MacroOrigin `json:"origin"`
}

// MacroSite is `schema.MacroSite`.
type MacroSite struct {
	DefId     string        `json:"def_id"`
	Name      string        `json:"name"`
	Line      int           `json:"line"`
	Position  MacroPosition `json:"position"`
	RoutineId *string       `json:"routine_id,omitempty"`
	Shadows   string        `json:"shadows,omitempty"`
}

// FileFacts is `schema.FileFacts`.
type FileFacts struct {
	Path               string                `json:"path"`
	Lang               string                `json:"lang"`
	Module             string                `json:"module"`
	ContentHash        string                `json:"content_hash"`
	Doc                string                `json:"doc,omitempty"`
	Routines           List[Routine]         `json:"routines,omitempty"`
	Calls              List[CallSite]        `json:"calls,omitempty"`
	Boundaries         List[BoundaryHit]     `json:"boundaries,omitempty"`
	Structures         List[DataStructure]   `json:"structures,omitempty"`
	Entrypoints        List[Entrypoint]      `json:"entrypoints,omitempty"`
	Imports            List[ImportRec]       `json:"imports,omitempty"`
	CliApps            List[CliApp]          `json:"cli_apps,omitempty"`
	CliMounts          List[CliMount]        `json:"cli_mounts,omitempty"`
	Sql                List[SqlStatement]    `json:"sql,omitempty"`
	Network            List[NetworkCall]     `json:"network,omitempty"`
	Classes            List[ClassDef]        `json:"classes,omitempty"`
	Tables             List[TableSchema]     `json:"tables,omitempty"`
	Indexes            List[IndexSchema]     `json:"indexes,omitempty"`
	Artefacts          List[Artefact]        `json:"artefacts,omitempty"`
	Constants          List[Constant]        `json:"constants,omitempty"`
	Control            List[ControlPoint]    `json:"control,omitempty"`
	ControlArms        List[ControlArm]      `json:"control_arms,omitempty"`
	Literals           List[StringLiteral]   `json:"literals,omitempty"`
	ModuleScope        *Routine              `json:"module_scope,omitempty"`
	LiteralsDropped    int                   `json:"literals_dropped,omitempty"`
	TestsDropped       int                   `json:"tests_dropped,omitempty"`
	ReadThrough        string                `json:"read_through,omitempty"`
	IpcRegistrations   List[IpcRegistration] `json:"ipc_registrations,omitempty"`
	MacroDefs          List[MacroDef]        `json:"macro_defs,omitempty"`
	MacroSites         List[MacroSite]       `json:"macro_sites,omitempty"`
	MacroDirectiveUses int                   `json:"macro_directive_uses,omitempty"`
	SkippedLines       int                   `json:"skipped_lines,omitempty"`
	FirstMissing       string                `json:"first_missing,omitempty"`
	Errors             List[string]          `json:"errors,omitempty"`
}

// Answer is `schema.Answer`.
type Answer struct {
	File string `json:"file"`
	Line int    `json:"line"`
	Name string `json:"name"`
}

// SuppliedEdge is `schema.SuppliedEdge`.
type SuppliedEdge struct {
	SiteId     string       `json:"site_id"`
	CallerId   string       `json:"caller_id"`
	File       string       `json:"file,omitempty"`
	Line       int          `json:"line,omitempty"`
	Name       string       `json:"name,omitempty"`
	How        string       `json:"how,omitempty"`
	Candidates int          `json:"candidates,omitempty"`
	Constructs string       `json:"constructs,omitempty"`
	Frontier   string       `json:"frontier,omitempty"`
	Reason     string       `json:"reason,omitempty"`
	Answers    List[Answer] `json:"answers,omitempty"`
}
