
# --- chunked report summary surface ---
import api_report_summary as mod
from api_report_summary import (
    as_list,
    as_str,
    chunk_text,
    extract_text,
    merge_chunk_summaries,
    normalize,
    safe_json_loads,
    scan_reports,
)


def _tmp_root(tmp_path):
    # point SUMMARY_DIR + SCAN_DIRS at a temp tree
    mod.SUMMARY_DIR = tmp_path / "cache"
    mod.SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_extract_text_strips_noise():
    html = "<html><head><style>body{}</style></head><body><script>x()</script><nav>menu</nav><h1>Hi</h1><p class='c' id='i'>real text</p><footer>f</footer></body></html>"
    text = extract_text(html)
    assert "real text" in text
    assert "menu" not in text
    assert "script" not in text
    assert "style" not in text


def test_chunk_text_splits_long_input():
    big = "word " * 5000  # ~25_000 chars
    chunks = chunk_text(big, size=8000, overlap=500)
    assert len(chunks) >= 3
    # overlap preserved at chunk boundary
    assert chunks[1].startswith(chunks[0][-500:])


def test_chunk_text_short_input():
    assert chunk_text("tiny") == ["tiny"]
    assert chunk_text("") == []


def test_as_list_caps_and_dedupes():
    items = [f"item {i}" for i in range(20)] + ["item 1"]
    out = as_list(items)
    assert len(out) == 5
    assert len(out[0]) <= 160


def test_as_str_truncates():
    assert as_str("x" * 1000).endswith("...")
    assert len(as_str(None)) == 0


def test_safe_json_loads_extracts_codeblock():
    raw = "noise\n```json\n{\"a\": 1}\n```\nmore"
    assert safe_json_loads(raw) == {"a": 1}


def test_normalize_handles_missing_keys():
    out = normalize({})
    assert out["key_findings"] == []
    assert out["overall_assessment"] == ""


def test_scan_reports_discovers_html_files(tmp_path, monkeypatch):
    _tmp_root(tmp_path)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "out").mkdir()
    f = proj / "out" / "demo.html"
    f.write_text("<html><body>hi</body></html>", encoding="utf-8")
    monkeypatch.setattr(mod, "SCAN_DIRS", [{"dir": str(f.relative_to(proj)), "kind": "code", "review_type": "Demo"}])
    # also patch pathlib root resolution
    import pathlib as _pl
    real_resolve = _pl.Path.resolve
    monkeypatch.setattr(_pl.Path, "resolve", lambda self, *a, **k: proj if str(self).endswith("api_report_summary.py") else real_resolve(self, *a, **k))
    rows = scan_reports()
    assert any(r["review_type"] == "Demo" for r in rows)


def test_merge_chunk_summaries_dedupes_and_caps():
    a = {"key_findings": ["one", "two"], "critical_issues": ["c1"], "medium_issues": [], "recommendations": ["r1"], "positive_observations": ["p1"], "overall_assessment": "first", "final_verdict": "v1"}
    b = {"key_findings": ["one", "three"], "critical_issues": ["c1", "c2"], "medium_issues": ["m"], "recommendations": ["r1", "r2"], "positive_observations": ["p1"], "overall_assessment": "second", "final_verdict": "v2"}
    merged = merge_chunk_summaries([a, b])
    assert merged["key_findings"][:2] == ["one", "two"] or merged["key_findings"][:2] == ["one", "three"]
    assert len(merged["key_findings"]) <= 5
    assert merged["overall_assessment"] == "first"
    assert merged["final_verdict"] == "v2"
