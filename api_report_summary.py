import datetime as _dt
import hashlib as _hl
import json
import os
import pathlib
import re as _re
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

SUMMARY_DIR = pathlib.Path(__file__).resolve().parent / ".ai" / "temp" / "report-summaries"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

# Anything that belongs to CI / logs / junit / dep-check must NOT bleed into
# the Performance group even if it lives under reports/.
_EXCLUDE_FROM_PERF = (
    "ci-summary.html",
    "ci-summary.json",
    "ci-logs.txt",
    "junit-python.xml",
    "junit-python.html",
    "dependency-check-report.html",
    "lighthouse-report.html",
)

SCAN_DIRS = [
    {"dir": ".code-review",                                     "kind": "code",     "review_type": "Code Review"},
    {"dir": "skills/reports",                                   "kind": "security", "review_type": "Security Review"},
    {"dir": "reports/ci",                                       "kind": "ci",       "review_type": "CI Report"},
    {"dir": "reports/ci/dependency-check-report",               "kind": "security", "review_type": "Security Review"},
    {"dir": "reports/ci/backend-python-reports/htmlcov-python", "kind": "code",     "review_type": "Code Review (Coverage)"},
    {"dir": "reports/ci",                                       "kind": "ci",       "review_type": "CI JUnit XML",            "include_globs": ["backend-python-reports/junit-python.xml"]},
    {"dir": "reports/ci",                                       "kind": "security", "review_type": "OWASP Dependency-Check",  "include_globs": ["dependency-check-report/dependency-check-report.html"]},
    # Perf bucket -------------------------------------------------------
    {"dir": "reports",                                          "kind": "perf",     "review_type": "Performance Review",     "include_globs": ["lighthouse-report.html"]},
    {"dir": "reports/allure-results",                            "kind": "perf",     "review_type": "Allure Results",         "include_globs": ["*.json"]},
]

SYSTEM_PROMPT = (
    "You are a senior engineering reviewer summarizing an existing report.\n"
    "Produce ONLY valid JSON. No markdown. No code blocks. No prose.\n"
    "Format:\n"
    "{\n"
    '    "overall_assessment": "1-2 sentence overview of the report quality.",\n'
    '    "key_findings": ["1-5 short bullet strings"],\n'
    '    "critical_issues": ["short bullets, only high-priority issues or empty array"],\n'
    '    "medium_issues": ["short bullets, medium severity findings or empty array"],\n'
    '    "recommendations": ["actionable fix bullets, 1-5 items or empty array"],\n'
    '    "positive_observations": ["things already implemented well, 1-5 items or empty array"],\n'
    '    "final_verdict": "1-2 sentence overall quality score and conclusion."\n'
    "}\n"
    "Rules:\n"
    "- Summarize ONLY what is in the chunk. Do not invent issues.\n"
    "- Use 1-5 bullets per section. Leave arrays empty when there is nothing to report.\n"
    "- Keep each bullet under 160 characters.\n"
    "- Do not include markdown, headings, or prose outside the JSON.\n"
)

_NOISE = [
    _re.compile(r"<style\b[^>]*>.*?</style>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<script\b[^>]*>.*?</script>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<svg\b[^>]*>.*?</svg>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<noscript\b[^>]*>.*?</noscript>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<template\b[^>]*>.*?</template>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<iframe\b[^>]*>.*?</iframe>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<head\b[^>]*>.*?</head>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<form\b[^>]*>.*?</form>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<nav\b[^>]*>.*?</nav>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<footer\b[^>]*>.*?</footer>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<header\b[^>]*>.*?</header>", _re.IGNORECASE | _re.DOTALL),
    _re.compile(r"<!--.*?-->", _re.DOTALL),
    _re.compile(r"<[^>]+>"),
    _re.compile(r"&(amp|lt|gt|quot|nbsp|#\d+|#x[0-9a-fA-F]+);", _re.IGNORECASE),
    _re.compile(r"https?://\S+"),
    _re.compile(r"\bdata:image/[A-Za-z0-9+/=;,-]+\b"),
    _re.compile(r"\bstyle\s*=\s*\"[^\"]*\"", _re.IGNORECASE),
    _re.compile(r"\bclass\s*=\s*\"[^\"]*\"", _re.IGNORECASE),
    _re.compile(r"\bid\s*=\s*\"[^\"]*\"", _re.IGNORECASE),
]

CHUNK_SIZE = 8000
CHUNK_OVERLAP = 500
MAX_TEXT = 20000


def extract_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = raw_html
    for p in _NOISE:
        text = p.sub(" ", text)
    text = _re.sub(r"\s+", " ", text)
    text = _re.sub(r"(?:\b\w\b\s*){3,}", " ", text)
    return text.strip()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    out = []
    step = max(1, size - overlap)
    i = 0
    while i < len(text):
        piece = text[i:i + size].strip()
        if piece:
            out.append(piece)
        if i + size >= len(text):
            break
        i += step
    return out


def report_id_for(rel_path: str) -> str:
    return _hl.md5(rel_path.encode("utf-8")).hexdigest()[:16]


def file_content_hash(path: pathlib.Path) -> str:
    try:
        st = path.stat()
    except OSError:
        return ""
    h = _hl.md5()
    h.update(str(st.st_size).encode("utf-8"))
    h.update(str(st.st_mtime_ns).encode("utf-8"))
    with open(path, "rb") as fh:
        while True:
            buf = fh.read(65536)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def safe_json_loads(raw):
    if not raw:
        return None
    text = raw.strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    m = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (ValueError, TypeError):
            return None
    s = text.find("{"); e = text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except (ValueError, TypeError):
            return None
    return None


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = [value]
    else:
        items = [value]
    out, seen = [], set()
    for v in items:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        if len(s) > 160:
            s = s[:157].rstrip() + "..."
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        out.append(s)
        if len(out) >= 5:
            break
    return out


def as_str(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(v) for v in value if v)
    s = str(value).strip()
    if len(s) > 400:
        s = s[:397].rstrip() + "..."
    return s


def normalize(summary):
    if not isinstance(summary, dict):
        return None
    return {
        "overall_assessment":   as_str(summary.get("overall_assessment")),
        "key_findings":         as_list(summary.get("key_findings")),
        "critical_issues":      as_list(summary.get("critical_issues")),
        "medium_issues":        as_list(summary.get("medium_issues")),
        "recommendations":      as_list(summary.get("recommendations")),
        "positive_observations": as_list(summary.get("positive_observations") or summary.get("positive_findings")),
        "final_verdict":        as_str(summary.get("final_verdict") or summary.get("conclusion")),
    }


def _is_perf_row(entry: dict, rel: str) -> bool:
    """Perf bucket = kind=perf OR review_type ~ perf/lighthouse/allure, minus CI/logs/junit/dep-check."""
    if entry["kind"] != "perf":
        return False
    base = pathlib.PurePosixPath(rel).name
    if base in _EXCLUDE_FROM_PERF:
        return False
    return not ("/ci/" in "/" + rel or rel.startswith("reports/ci/"))


def scan_reports():
    import fnmatch
    root = pathlib.Path(__file__).resolve().parent
    seen, rows = set(), []
    for entry in SCAN_DIRS:
        directory = root / entry["dir"]
        if not directory.exists() or not directory.is_dir():
            continue
        globs = entry.get("include_globs")
        for ext in (".html", ".json", ".xml", ".txt"):
            for path in directory.rglob("*" + ext):
                if not path.is_file():
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                try:
                    rel = path.relative_to(root).as_posix()
                except ValueError:
                    rel = path.as_posix()
                rel_in_dir = path.relative_to(directory).as_posix()
                if globs and not any(fnmatch.fnmatch(rel_in_dir, g) for g in globs):
                    continue
                rid = report_id_for(rel)
                if rid in seen:
                    continue
                seen.add(rid)
                group = "performance" if _is_perf_row(entry, rel) else "report"
                rows.append({
                    "id":             rid,
                    "name":           (path.stem.replace("-", " ").replace("_", " ").title() or path.name),
                    "filename":       path.name,
                    "review_type":    entry["review_type"],
                    "kind":           entry["kind"],
                    "type":           entry["review_type"],
                    "path":           rel,
                    "group":          group,
                    "generated_at":   _dt.datetime.fromtimestamp(stat.st_mtime, tz=_dt.timezone.utc).isoformat(timespec="seconds"),
                    "generated_date": _dt.datetime.fromtimestamp(stat.st_mtime, tz=_dt.timezone.utc).isoformat(timespec="seconds"),
                    "size":           stat.st_size,
                    "summary_exists": (SUMMARY_DIR / f"{rid}.json").exists(),
                })
    rows.sort(key=lambda r: (r.get("group", "report") != "performance", -(_dt.datetime.fromisoformat(r["generated_date"]).timestamp())))
    return rows


def _gemini_call(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-flash:generateContent?key=" + api_key)
    payload = {"contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt}]}]}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())
    return result["candidates"][0]["content"]["parts"][0]["text"]


def _ollama_call(prompt: str) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    body = json.dumps({"model": "llama3.2", "prompt": SYSTEM_PROMPT + "\n\n" + prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(f"{host}/api/generate", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())
    return result.get("response", "")


def call_llm(prompt: str) -> str:
    try:
        return _gemini_call(prompt)
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError, KeyError):
        pass
    return _ollama_call(prompt)


def merge_chunk_summaries(summaries):
    fields = ["key_findings", "critical_issues", "medium_issues", "recommendations", "positive_observations"]
    merged = {f: [] for f in fields}
    assessments, verdicts = [], []
    for s in summaries:
        if not s:
            continue
        a = as_str(s.get("overall_assessment"))
        if a:
            assessments.append(a)
        v = as_str(s.get("final_verdict"))
        if v:
            verdicts.append(v)
        for f in fields:
            merged[f].extend(as_list(s.get(f)))
    return {
        "overall_assessment":   as_str(assessments[0]) if assessments else "",
        "key_findings":         as_list(merged["key_findings"]),
        "critical_issues":      as_list(merged["critical_issues"]),
        "medium_issues":        as_list(merged["medium_issues"]),
        "recommendations":      as_list(merged["recommendations"]),
        "positive_observations": as_list(merged["positive_observations"]),
        "final_verdict":        as_str(verdicts[-1]) if verdicts else "",
    }


def summarize_text(report_name: str, review_type: str, text: str):
    text = (text or "")[:MAX_TEXT]
    chunks = chunk_text(text)
    if not chunks:
        raise RuntimeError("Empty report content")
    partials = []
    for idx, chunk in enumerate(chunks, 1):
        prompt = (f"Summarize chunk {idx}/{len(chunks)} of report '{report_name}' "
                  f"(review type: {review_type}). Return JSON only.\n\n{chunk}")
        try:
            raw = call_llm(prompt)
        except (RuntimeError, urllib.error.URLError, json.JSONDecodeError, KeyError):
            partials.append(None)
            continue
        parsed = normalize(safe_json_loads(raw))
        if parsed:
            partials.append(parsed)
    valid = [p for p in partials if p]
    if not valid:
        raise RuntimeError("LLM failed for every chunk")
    merged = merge_chunk_summaries(valid)
    try:
        synthesis_prompt = (f"Based ONLY on the chunk summaries below, produce the final JSON for "
                            f"report '{report_name}' (review type: {review_type}). "
                            f"Keep bullets under 160 chars, max 5 per list. JSON only.\n\n"
                            + json.dumps(merged))
        raw = call_llm(synthesis_prompt)
        final = normalize(safe_json_loads(raw))
        if final:
            return final
    except (RuntimeError, urllib.error.URLError, json.JSONDecodeError, KeyError):
        pass
    return merged


def build_payload(report, summary, cached, source_hash, chunk_count):
    return {
        "id":             report["id"],
        "name":           report["name"],
        "review_type":    report["review_type"],
        "kind":           report["kind"],
        "group":          report.get("group", "report"),
        "path":           report["path"],
        "generated_at":   report.get("generated_at") or report.get("generated_date"),
        "size":           report["size"],
        "summary":        summary,
        "cached":         cached,
        "source_hash":    source_hash,
        "chunk_count":    chunk_count,
    }


def _load_report(report_id: str):
    index = {r["id"]: r for r in scan_reports()}
    if report_id not in index:
        raise HTTPException(status_code=404, detail="Report not found")
    return index[report_id]


def get_summary(report_id: str, refresh: bool = False):
    report = _load_report(report_id)
    root = pathlib.Path(__file__).resolve().parent
    file_path = root / report["path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    cache_path = SUMMARY_DIR / f"{report_id}.json"
    source_hash = file_content_hash(file_path)
    if cache_path.exists() and not refresh:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("source_hash") == source_hash and cached.get("summary"):
                return build_payload(report, cached["summary"], True, source_hash, cached.get("chunk_count", 1))
        except (OSError, ValueError, TypeError):
            try:
                cache_path.unlink()
            except OSError:
                pass
    try:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not read report: {exc}")
    summary = summarize_text(report["name"], report["review_type"], extract_text(raw))
    chunk_count = max(1, len(chunk_text(extract_text(raw))))
    cache_payload = {
        "summary":     summary,
        "source_hash": source_hash,
        "chunk_count": chunk_count,
        "cached_at":   _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds") + "Z",
    }
    try:
        cache_path.write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
    except OSError:
        pass
    return build_payload(report, summary, False, source_hash, chunk_count)


def bulk_summary(group: str = Query("performance")):
    rows = [r for r in scan_reports() if r.get("group") == group]
    items = []
    for r in rows:
        try:
            payload = get_summary(r["id"], refresh=False)
            items.append({
                "id":      r["id"],
                "name":    r["name"],
                "path":    r["path"],
                "ok":      True,
                "cached":  payload.get("cached", False),
                "summary": payload.get("summary"),
            })
        except (HTTPException, OSError, RuntimeError, ValueError) as exc:
            items.append({"id": r["id"], "name": r["name"], "path": r["path"], "ok": False, "error": str(exc)})
    return {"group": group, "total": len(items), "items": items}


def download_file(report_id: str):
    report = _load_report(report_id)
    root = pathlib.Path(__file__).resolve().parent
    file_path = root / report["path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(path=str(file_path), media_type="text/html", filename=report["filename"])


def view_file(report_id: str):
    report = _load_report(report_id)
    root = pathlib.Path(__file__).resolve().parent
    file_path = root / report["path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(path=str(file_path), media_type="text/html")


router = APIRouter()
router.add_api_route("/api/reports",                         scan_reports,                       methods=["GET"])
router.add_api_route("/api/reports/bulk-summary",            bulk_summary,                       methods=["GET"])
router.add_api_route("/api/reports/{report_id}/summary",     get_summary,                        methods=["GET"])
router.add_api_route("/api/report-download/{report_id}",     download_file,                      methods=["GET"])
router.add_api_route("/api/report-view/{report_id}",         view_file,                          methods=["GET"])
router.add_api_route("/api/report-summary",                  lambda: {"reports": scan_reports()}, methods=["GET"])
router.add_api_route("/api/report-summary/{report_id}",      get_summary,                        methods=["GET"])
