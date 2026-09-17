/**
 * Ways in that a framework declares by **where a file sits**.
 *
 * Python's ways in are written down in the file: `@app.get("/x")` is a decorator this
 * reader can match, `[project.scripts]` is a contract in packaging metadata. A Next.js App
 * Router page declares nothing at all — `app/(marketing)/services/[slug]/page.tsx` serves
 * `/services/[slug]` because of *where it is*, and the file itself is a component like any
 * other. A reader that does not know the convention finds thirty-three components nothing
 * calls and reports a program with no way into it.
 *
 * So the path is the declaration, and this module is the one place it is read. What is a
 * root, what is a page, what is a handler and which segments are not URL all arrive from
 * `detectors/typescript.yaml` (`rules.RouteRule`), as the boundary names do; what is here
 * is the derivation, which is an algorithm and not a table.
 *
 * **Two segment shapes and they are opposites.** A route group — `(marketing)`, `(admin)`
 * — exists to share a layout and is *not* part of any URL, so it vanishes; a `(…)` left in
 * a route name is a name no reader can type into a browser, and it is the first thing
 * anybody who writes Next.js checks. A dynamic segment — `[slug]`, `[...nextauth]` — is
 * kept exactly as written, because the program's own word for that hole is the only name
 * it has and inventing `:slug` would be this reader translating (rule 30).
 *
 * **What it deliberately does not claim**, each stated rather than absent:
 *
 * - **`"use server"` actions.** They are called across the wire and so are ways in by the
 *   meaning of HTTP_ROUTE, but nothing in the tree says which of a module's exports the
 *   client actually calls, and claiming every export of every action file would put names
 *   in "Where to start" that no request ever reaches (rule 1). The directive is recorded
 *   on the routine instead, so the hole has a count and a query.
 * - **`layout.tsx`, `loading.tsx`, `error.tsx`, `not-found.tsx`.** They are framework
 *   hooks around a route rather than routes: nothing is served at their URL.
 * - **Parallel and intercepted routes** — `@slot`, `(.)photo`. Neither corpus here has
 *   one, and a convention nobody has read a file of is a guess.
 */

import ts from "typescript";
import { makeId } from "./ids.js";
import type { Entrypoint, EntrypointKind, Routine } from "./facts.js";
import type { RouteRule, RuleSet } from "./rules.js";

/** The route tree a file sits in, and where it sits — or nothing. */
function under(rel: string, rule: RouteRule): string | null {
  for (const root of rule.roots) {
    if (rel === root || rel.startsWith(`${root}/`)) return rel.slice(root.length + 1);
  }
  return null;
}

/**
 * The URL a route file serves, from the directories between the root and the file.
 *
 * `(marketing)/services/[slug]/page.tsx` is `/services/[slug]`, and a tree with nothing but
 * groups above it — `(marketing)/page.tsx` — is `/`, which is a real URL and the one most
 * programs care about most.
 */
export function routeUrl(within: string, stripGroups: boolean): string {
  const parts = within.split("/");
  parts.pop();
  const kept = parts.filter((p) => p !== "" && !(stripGroups && p.startsWith("(") && p.endsWith(")")));
  return `/${kept.join("/")}`;
}

/** The routine a `export default` names, where this reader recorded one. */
function defaultExport(sf: ts.SourceFile, byNode: Map<ts.Node, Routine>,
                       byName: Map<string, Routine>): Routine | null {
  for (const stmt of sf.statements) {
    const flags = ts.getCombinedModifierFlags(stmt as unknown as ts.Declaration);
    if ((flags & ts.ModifierFlags.ExportDefault) !== 0) {
      const hit = byNode.get(stmt);
      if (hit !== undefined) return hit;
    }
    // `export default Page;` — the component was declared above and is named here.
    if (ts.isExportAssignment(stmt) && stmt.isExportEquals !== true
        && ts.isIdentifier(stmt.expression)) {
      const hit = byName.get(stmt.expression.text);
      if (hit !== undefined) return hit;
    }
  }
  return null;
}

/**
 * Every name this file exports, in the three spellings a route handler is written in.
 *
 * The third is not an edge case: `app/api/auth/[...nextauth]/route.ts` is
 * `export const { GET, POST } = handlers;` — next-auth hands the file its handlers and the
 * file re-exports them by destructuring. A scan for exported *functions* finds nothing
 * there and reports a route file that serves no method.
 */
function exportedNames(sf: ts.SourceFile): Set<string> {
  const names = new Set<string>();
  const bind = (name: ts.BindingName): void => {
    if (ts.isIdentifier(name)) {
      names.add(name.text);
      return;
    }
    // `const { GET, POST } = handlers` and `const [a, b] = xs`.
    for (const element of name.elements) {
      if (ts.isBindingElement(element)) bind(element.name);
    }
  };

  for (const stmt of sf.statements) {
    const exported =
      (ts.getCombinedModifierFlags(stmt as unknown as ts.Declaration)
       & ts.ModifierFlags.Export) !== 0;
    if (exported && ts.isFunctionDeclaration(stmt) && stmt.name) names.add(stmt.name.text);
    if (exported && ts.isVariableStatement(stmt)) {
      for (const decl of stmt.declarationList.declarations) bind(decl.name);
    }
    // `export { GET, POST };` and `export { handler as GET };` — the *exported* spelling
    // is what the framework looks for, so it is the alias that counts where there is one.
    if (ts.isExportDeclaration(stmt) && stmt.exportClause
        && ts.isNamedExports(stmt.exportClause)) {
      for (const spec of stmt.exportClause.elements) names.add(spec.name.text);
    }
  }
  return names;
}

/**
 * The ways in one file declares by sitting where it does.
 *
 * A page yields one; a handler yields one per HTTP verb it exports, because that is what
 * the file declares — one `route.ts` serving GET and POST is two ways in and a reader
 * looking for where a POST is handled must find it.
 */
export function waysIn(
  rel: string,
  sf: ts.SourceFile,
  rules: RuleSet,
  routines: Routine[],
  anchors: Map<ts.Node, Routine>,
): Entrypoint[] {
  const base = rel.slice(rel.lastIndexOf("/") + 1);
  const byName = new Map<string, Routine>();
  for (const r of routines) if (!byName.has(r.name)) byName.set(r.name, r);

  for (const rule of rules.routes) {
    const within = under(rel, rule);
    if (within === null) continue;
    const kind = rule.kind as EntrypointKind;
    const url = routeUrl(within, rule.stripGroups);

    if (rule.pages.has(base)) {
      const target = defaultExport(sf, anchors, byName);
      return [{
        id: makeId("ep", `${rel}:${url}`),
        kind,
        name: url,
        routine_id: target?.id ?? null,
        module: rel,
        evidence: `${rule.evidence} page`,
        group: rule.framework,
      }];
    }

    if (rule.handlers.has(base)) {
      const out: Entrypoint[] = [];
      for (const verb of exportedNames(sf)) {
        if (!rule.verbs.has(verb)) continue;
        out.push({
          id: makeId("ep", `${rel}:${verb} ${url}`),
          kind,
          // The verb leads, because two files serving one path with different methods are
          // two ways in and the method is what tells them apart.
          name: `${verb} ${url}`,
          routine_id: byName.get(verb)?.id ?? null,
          module: rel,
          evidence: `${rule.evidence} route handler, exported as ${verb}`,
          group: rule.framework,
        });
      }
      // Sorted, because `exportedNames` is a set over source order and a way in is a row
      // in a document somebody diffs (rule 66).
      return out.sort((a, b) => a.name.localeCompare(b.name));
    }
  }
  return [];
}
