"""TypeScript's resolver.

Beside `plugins/typescript/` and `canonical/`, and the same third place adding a language
touches — with one difference worth stating at the door: **this resolver does not resolve
anything.** The TypeScript compiler already did, in the plugin's own process, and what is
here is the part only the host can do: turn a location into an id.

Nothing in `src/` imports from here any longer: `resolve/calls.py`'s `RESOLVERS` table
names `supplied.resolve` directly, and this address is kept for the tests that cite it.
"""
