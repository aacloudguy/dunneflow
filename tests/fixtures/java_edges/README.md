# The Java edge fixture

One call of each shape the Java reader's dispatch rule distinguishes, written so that
`tests/test_java_reader.py` can name each site by its callee and say which answer it gets.
Two build modules (`app/` and `lib/`), each with its own `build.gradle`, so that a call
across modules is one of the shapes.

Nothing here compiles cleanly on purpose: `Missing` is imported from a package that does not
exist, so that an untyped receiver is one of the shapes too.
