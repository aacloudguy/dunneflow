/**
 * `schema.py`'s types, as this reader has to emit them.
 *
 * **GENERATED — do not edit.** `uv run python tools/gen_facts_ts.py --write`, or
 * `npm run schema`. `tests/test_typescript.py` regenerates it and compares, so a drift
 * between this file and `schema.py` fails the suite rather than the map.
 *
 * Transcribing it by hand was tried and was wrong inside an hour: the reader filled a
 * `NetworkCall.library` field that does not exist, the codec dropped it and named the drop
 * in `FileFacts.errors`, and `WalkStats` counts a file with an error as a **failed** file —
 * so every TypeScript file holding a network call would have been reported unreadable, in a
 * map that otherwise looked perfect. Generated, it is a compile error.
 *
 * A field left at its default is omitted on the wire, which is what `codec.encode` does on
 * the other side: Society's 43,926 `CallArg`s each carrying `"splat":false` is most of a
 * payload. So a field with a default is optional here and the reader writes only what it
 * set.
 *
 * `lang` is absent from `Routine` and `DataStructure` on purpose — it is the host's to
 * write (`ingest.stamp_lang`), and a reader that sent it would be offering a second answer
 * to a question the file has already answered.
 */

/** `schema.SCHEMA_VERSION`. A plugin declaring another number is refused by name. */
export const SCHEMA_VERSION = 20;

export type ArmKind = "if" | "elif" | "else" | "else if" | "case" | "default" | "try" | "except" | "catch" | "finally" | "for" | "while" | "do";

export type BoundaryKind = "ENV" | "FILE" | "PROCESS" | "NETWORK" | "DATABASE" | "QUEUE" | "STDIO" | "CLOUD_SDK" | "LLM_API" | "CRYPTO" | "LOCAL_IPC";

export type Confidence = "CERTAIN" | "INFERRED";

export type ControlKind = "LOOP" | "COMPREHENSION" | "DECISION" | "GUARD" | "HANDLER";

export type Direction = "IN" | "OUT" | "BOTH";

export type EntrypointKind = "CLI" | "MAIN" | "MCP_TOOL" | "HTTP_ROUTE" | "QUEUE_CONSUMER" | "SCHEDULED" | "SIGNAL" | "LIBRARY" | "IPC_COMMAND";

export type LiteralKind = "PLAIN" | "INTERPOLATED";

export type MacroOrigin = "tree" | "outside" | "command_line" | "builtin" | "unknown";

export type MacroPosition = "statement" | "declaration" | "file_scope";

export type StructureKind = "DATACLASS" | "PYDANTIC" | "TYPEDDICT" | "NAMEDTUPLE" | "ENUM" | "CLASS" | "INTERFACE" | "TYPE_ALIAS";

export type TargetKind = "MODULE_ATTR" | "FILE" | "NONE";

export interface Routine {
  id: string;
  name: string;
  qualname: string;
  module: string;
  file: string;
  line_start: number;
  line_end: number;
  params?: Param[];
  returns?: string | null;
  decorators?: string[];
  docstring?: string | null;
  comments?: Comment[];
  annotations?: Annotation[];
  is_async?: boolean;
  is_method?: boolean;
  class_name?: string | null;
  is_nested?: boolean;
  visibility?: "public" | "private";
  body_hash?: string;
  name_by?: string;
  body_by?: string;
  opaque_asm?: number;
}

export interface Param {
  name: string;
  type?: string | null;
  default?: string | null;
  kind?: "positional_only" | "positional" | "vararg" | "keyword" | "kwarg";
}

export interface Comment {
  text: string;
  line: number;
  leading?: boolean;
}

export interface Annotation {
  kind: string;
  value: string;
  line: number;
  text?: string;
  confidence?: Confidence;
}

export interface CallSite {
  caller_id: string;
  callee_expr: string;
  line: number;
  callee_id?: string | null;
  confidence?: Confidence;
  external?: boolean;
  at_boundary?: boolean;
  site_id?: string;
  args?: CallArg[];
  is_construction?: boolean;
  bound_locally?: boolean;
}

export interface CallArg {
  idx: number;
  expr: string;
  keyword?: string | null;
  splat?: boolean;
}

export interface BoundaryHit {
  routine_id: string;
  kind: BoundaryKind;
  direction: Direction;
  target: string;
  line: number;
  evidence?: string;
  salience?: string;
  through_macro?: string;
  declared?: boolean;
}

export interface DataStructure {
  id: string;
  name: string;
  kind: StructureKind;
  module: string;
  file: string;
  line: number;
  fields?: Field_[];
  docstring?: string | null;
  bases?: string[];
  annotations?: Annotation[];
  name_by?: string;
}

export interface Field_ {
  name: string;
  type?: string | null;
  default?: string | null;
  comment?: string | null;
}

export interface Entrypoint {
  id: string;
  kind: EntrypointKind;
  name: string;
  routine_id?: string | null;
  module?: string;
  evidence?: string;
  group?: string;
  parent_id?: string | null;
  target_expr?: string;
}

export interface ImportRec {
  module: string;
  name: string;
  alias: string;
  is_from: boolean;
  line: number;
}

export interface CliApp {
  id: string;
  var: string;
  module: string;
  file: string;
  line: number;
  title?: string;
  factory?: string;
}

export interface CliMount {
  parent_var: string;
  parent_module: string;
  child_expr: string;
  file: string;
  line: number;
  name?: string;
}

export interface SqlStatement {
  routine_id: string;
  operation: string;
  direction: string;
  tables: string[];
  sql: string;
  line: number;
}

export interface NetworkCall {
  routine_id: string;
  expr: string;
  protocol: string;
  line: number;
  verb?: string;
  destination?: string;
  port?: string;
  is_async?: boolean;
  awaited?: boolean;
  in_async_routine?: boolean;
  timeout?: string;
  retries?: string;
  tls?: string;
  payload?: string;
  headers?: string;
  topic?: string;
  ack?: string;
}

export interface ClassDef_ {
  name: string;
  qualname: string;
  module: string;
  file: string;
  line: number;
  bases?: string[];
}

export interface TableSchema {
  name: string;
  file: string;
  line: number;
  columns?: string[][];
  temporary?: boolean;
}

export interface IndexSchema {
  name: string;
  table: string;
  columns: string;
  file: string;
  line: number;
  unique?: boolean;
}

export interface Artefact {
  name: string;
  stem: string;
  ext: string;
  kind: string;
  routine_id: string;
  line: number;
  literal: string;
  is_pattern?: boolean;
}

export interface Constant {
  name: string;
  value: string;
  line: number;
  type?: string | null;
  is_final?: boolean;
  comment?: string | null;
  private?: boolean;
}

export interface ControlPoint {
  point_id: string;
  routine_id: string;
  kind: ControlKind;
  line_start: number;
  line_end: number;
  depth: number;
  header?: string;
  arms?: number;
  exits?: string;
  word?: string;
  once_start?: number;
  once_end?: number;
}

export interface ControlArm {
  point_id: string;
  routine_id: string;
  idx: number;
  kind: ArmKind;
  line_start: number;
  line_end: number;
  header?: string;
}

export interface StringLiteral {
  routine_id: string;
  line: number;
  text: string;
  kind?: LiteralKind;
}

export interface IpcRegistration {
  name: string;
  line: number;
}

export interface MacroDef {
  id: string;
  name: string;
  file: string;
  line: number;
  origin: MacroOrigin;
}

export interface MacroSite {
  def_id: string;
  name: string;
  line: number;
  position: MacroPosition;
  routine_id?: string | null;
  shadows?: string;
}

export interface FileFacts {
  path: string;
  lang: string;
  module: string;
  content_hash: string;
  doc?: string;
  routines?: Routine[];
  calls?: CallSite[];
  boundaries?: BoundaryHit[];
  structures?: DataStructure[];
  entrypoints?: Entrypoint[];
  imports?: ImportRec[];
  cli_apps?: CliApp[];
  cli_mounts?: CliMount[];
  sql?: SqlStatement[];
  network?: NetworkCall[];
  classes?: ClassDef_[];
  tables?: TableSchema[];
  indexes?: IndexSchema[];
  artefacts?: Artefact[];
  constants?: Constant[];
  control?: ControlPoint[];
  control_arms?: ControlArm[];
  literals?: StringLiteral[];
  module_scope?: Routine | null;
  literals_dropped?: number;
  tests_dropped?: number;
  read_through?: string;
  ipc_registrations?: IpcRegistration[];
  macro_defs?: MacroDef[];
  macro_sites?: MacroSite[];
  macro_directive_uses?: number;
  skipped_lines?: number;
  first_missing?: string;
  errors?: string[];
}

export interface Answer {
  file: string;
  line: number;
  name: string;
}

export interface SuppliedEdge {
  site_id: string;
  caller_id: string;
  file?: string;
  line?: number;
  name?: string;
  how?: string;
  candidates?: number;
  constructs?: string;
  frontier?: string;
  reason?: "" | "outside" | "untyped" | "dynamic" | "bound" | "unfollowed" | "expanded";
  answers?: Answer[];
}
