"""A count and its noun agree (BACKLOG 28)."""

from __future__ import annotations

from dunneflow.words import are, plural


def test_one_of_a_thing_is_singular_and_every_other_count_is_not():
    assert plural(1, "time") == "1 time"
    assert plural(0, "time") == "0 times"
    assert plural(1_047, "analysis", "analyses") == "1,047 analyses"
    assert (are(1), are(2), are(0)) == ("is", "are", "are")


def test_the_worklist_never_says_called_1_times():
    """The sentence the retake photographed, rebuilt from the detector's own f-string."""
    import inspect

    from dunneflow import anomalies

    src = inspect.getsource(anomalies)
    assert "is called {row['n']} times" not in src
    assert "plural(row['n'], 'time')" in src
