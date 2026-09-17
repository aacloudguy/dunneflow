/**
 * `detectors/typescript.yaml`, as the host sent it, matched the way the host matches it.
 *
 * **The file does not live here and must not.** It arrives in the `open` frame
 * (`detectors.rules_document`), because a plugin carrying its own copy is a second answer
 * that stops moving the moment somebody edits the YAML — and `detectors/*.yaml` is in the
 * core extraction key precisely so that an edit re-reads every language. What crosses the
 * wire is the document as written; what is here is `detectors.BoundaryRule.matches_call`,
 * transcribed, and it is transcribed rather than shared for the one reason rule 51 admits:
 * a process boundary is the place a rule cannot be moved to.
 *
 * So the transcription is kept to the four tests and nothing else, and `test_typescript.py`
 * puts the same dotted names through both implementations.
 */

export interface BoundaryRule {
  kind: string;
  direction: string;
  salience: string;
  exact: Set<string>;
  prefix: string[];
  method: Set<string>;
  subscript: Set<string>;
  contains: string[];
  targetArg: number | null;
}

export interface NetLibrary {
  prefix: string;
  protocol: string;
  isAsync: boolean;
}

/**
 * A framework that declares its ways in by **where a file sits**.
 *
 * No decorator, no registration call, no export name — Next.js routes on the path, so the
 * path is the declaration. What is declared here is which directories start a route tree,
 * which filenames are a page and which a handler, and which segments are not URL.
 */
export interface RouteRule {
  framework: string;
  kind: string;
  roots: string[];
  pages: Set<string>;
  handlers: Set<string>;
  verbs: Set<string>;
  stripGroups: boolean;
  evidence: string;
}

export interface RuleSet {
  boundaries: BoundaryRule[];
  subscriptIndex: Map<string, BoundaryRule>;
  netLibraries: NetLibrary[];
  netVerbs: Set<string>;
  netKwargs: Map<string, Set<string>>;
  routes: RouteRule[];
}

function asArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((v) => String(v)) : [];
}

export function parseRules(doc: unknown): RuleSet {
  const data = (doc ?? {}) as Record<string, unknown>;
  const boundaries: BoundaryRule[] = [];
  const subscriptIndex = new Map<string, BoundaryRule>();

  for (const raw of (data["boundaries"] as Record<string, unknown>[]) ?? []) {
    const rule: BoundaryRule = {
      kind: String(raw["kind"]),
      direction: String(raw["direction"] ?? "BOTH"),
      salience: String(raw["salience"] ?? "normal"),
      exact: new Set(asArray(raw["exact"])),
      prefix: asArray(raw["prefix"]),
      method: new Set(asArray(raw["method"])),
      subscript: new Set(asArray(raw["subscript"])),
      contains: asArray(raw["contains"]),
      targetArg: raw["target_arg"] === undefined || raw["target_arg"] === null
        ? null
        : Number(raw["target_arg"]),
    };
    boundaries.push(rule);
    for (const s of rule.subscript) subscriptIndex.set(s, rule);
  }

  const network = (data["network"] as Record<string, unknown>) ?? {};
  const libs = (network["libraries"] as Record<string, Record<string, unknown>>) ?? {};
  const netLibraries: NetLibrary[] = Object.entries(libs)
    .map(([prefix, v]) => ({
      prefix,
      protocol: String(v["protocol"] ?? "?"),
      isAsync: Boolean(v["async"] ?? false),
    }))
    // Longest prefix wins, exactly as `load_rules` sorts them, so `axios.` and a bare
    // `fetch` can both be declared without one shadowing the other.
    .sort((a, b) => b.prefix.length - a.prefix.length);

  const netKwargs = new Map<string, Set<string>>();
  for (const [k, v] of Object.entries(
    (network["kwargs"] as Record<string, unknown>) ?? {},
  )) {
    netKwargs.set(k, new Set(asArray(v)));
  }

  const routes: RouteRule[] = ((data["routes"] as Record<string, unknown>[]) ?? []).map(
    (raw) => ({
      framework: String(raw["framework"] ?? ""),
      kind: String(raw["kind"] ?? "HTTP_ROUTE"),
      // Longest first, so `src/app` is matched before `app` and a route tree under `src/`
      // cannot be read as two roots, one of them starting three segments in.
      roots: asArray(raw["roots"]).sort((a, b) => b.length - a.length),
      pages: new Set(asArray(raw["pages"])),
      handlers: new Set(asArray(raw["handlers"])),
      verbs: new Set(asArray(raw["verbs"])),
      stripGroups: raw["strip_groups"] !== false,
      evidence: String(raw["evidence"] ?? raw["framework"] ?? ""),
    }),
  );

  return {
    boundaries,
    subscriptIndex,
    netLibraries,
    netVerbs: new Set(asArray(network["verbs"])),
    netKwargs,
    routes,
  };
}

/** `BoundaryRule.matches_call`, transcribed. The four tests and nothing else. */
export function matchesCall(rule: BoundaryRule, dotted: string): boolean {
  if (!dotted) return false;
  if (rule.exact.has(dotted)) return true;
  if (rule.prefix.some((p) => dotted.startsWith(p))) return true;
  if (rule.contains.some((c) => dotted.includes(c))) return true;
  if (rule.method.size) {
    const last = dotted.slice(dotted.lastIndexOf(".") + 1);
    // A bare name is a plain function call, not a method on something.
    if (dotted.includes(".") && rule.method.has(last)) return true;
  }
  return false;
}

/** First matching rule wins, so order in the YAML is meaningful. */
export function matchCall(rules: RuleSet, dotted: string): BoundaryRule | null {
  for (const rule of rules.boundaries) {
    if (matchesCall(rule, dotted)) return rule;
  }
  return null;
}

export function matchSubscript(rules: RuleSet, dotted: string): BoundaryRule | null {
  return rules.subscriptIndex.get(dotted) ?? null;
}

/**
 * `RuleSet.network_profile`, transcribed — including the clause that makes a bare key
 * exact. `requests.` and `httpx.AsyncClient` are namespace prefixes; `fetch` is a bare
 * name, and a prefix test makes it match `fetchImpl` and `fetchAll` (rule 5). Measured:
 * DunneNote reported exactly one network call and it was `fetchImpl`, a parameter holding
 * an implementation rather than the global.
 */
export function matchNetwork(rules: RuleSet, dotted: string): NetLibrary | null {
  if (!dotted) return null;
  for (const lib of rules.netLibraries) {
    if (dotted === lib.prefix) return lib;
    if (lib.prefix.includes(".") && dotted.startsWith(lib.prefix)) return lib;
  }
  return null;
}
