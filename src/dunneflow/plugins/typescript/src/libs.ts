/**
 * TypeScript's own standard library, carried in the bundle.
 *
 * **Empty here and filled at bundle time**, by `build.mjs`'s `tsLibs` plugin, from
 * `node_modules/typescript/lib/lib*.d.ts`. Nothing runs this file: `plugin.json`'s `entry`
 * is `main.bundle.cjs` and the checkout's `src/` is only ever type-checked, so the empty
 * object is a placeholder the compiler can read and never a value anybody gets.
 *
 * **Why it has to be here at all, and it was measured rather than assumed.** A bundled
 * `tsc` resolves its default library off `__dirname`, which after bundling is the plugin's
 * own directory — where there is no `lib.es5.d.ts` and never will be. The compiler does not
 * refuse: it builds a program in which `Array`, `String`, `Promise` and every DOM type are
 * missing, every value typed through one of them is `any`, and every call on one resolves
 * to nothing. **It still produces edges**, which is exactly why this had to be measured —
 * rule 49, in the one place a plausible answer hides a whole missing library.
 *
 * Measured on `../DunneNote`, 5,119 call sites, with the libraries and without:
 *
 * | | edges supplied | resolved outside the map | could not resolve at all |
 * |---|---|---|---|
 * | **with** | 1,935 | 2,868 | **187** |
 * | without | 1,931 | 472 | **2,587** |
 *
 * So the libraries buy **four edges** and they buy the *account*: without them the run says
 * it could not name the far end of half the program's calls, and with them it says those
 * calls go to `Math`, `JSON`, `Set` and the DOM — external, and right (rule 32). A reader
 * that cannot tell those two apart is a reader nobody can weigh, and the map it produces
 * looks the same either way.
 *
 * All of them are carried rather than a chosen subset: which `lib` a project asks for is
 * its `tsconfig.json`'s business, `/// <reference lib="..." />` pulls in more, and a subset
 * picked here would be this reader guessing at somebody else's compilation.
 */
export const TS_LIBS: Record<string, string> = {};

/** Where the compiler is told its library lives. Never a path on any disk. */
export const LIB_DIR = "/__dunneflow_ts_libs__";
