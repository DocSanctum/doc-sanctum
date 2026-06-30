from __future__ import annotations

from backend.app.mcp.tools.search_documents import MAX_MATCHES_PER_FILE, _search_lines


def test_search_lines_basic_match():
    lines = ["Hello world\n", "No match here\n", "Hello again\n"]
    matches = _search_lines(lines, "hello")
    assert len(matches) == 2
    assert matches[0]["line_number"] == 1
    assert matches[1]["line_number"] == 3


def test_search_lines_case_insensitive():
    lines = ["INSTALLATION guide\n", "other line\n"]
    matches = _search_lines(lines, "installation")
    assert len(matches) == 1
    assert "INSTALLATION" in matches[0]["line"]


def test_search_lines_no_match():
    lines = ["foo\n", "bar\n"]
    matches = _search_lines(lines, "xyzzy_nonexistent")
    assert matches == []


def test_search_lines_context_bounds():
    lines = [f"line {i}\n" for i in range(10)]
    # Match on line index 0 — context should not go below 0
    lines[0] = "match here\n"
    matches = _search_lines(lines, "match here")
    assert matches[0]["line_number"] == 1
    assert len(matches[0]["context"]) <= 5


def test_search_lines_max_matches_per_file():
    lines = [f"keyword line {i}\n" for i in range(MAX_MATCHES_PER_FILE + 5)]
    matches = _search_lines(lines, "keyword")
    assert len(matches) == MAX_MATCHES_PER_FILE


def test_search_lines_context_includes_surrounding():
    lines = ["before\n", "target match\n", "after\n"]
    matches = _search_lines(lines, "target match")
    assert len(matches) == 1
    ctx = matches[0]["context"]
    assert "before" in ctx[0]
    assert "target match" in ctx[1]
    assert "after" in ctx[2]
