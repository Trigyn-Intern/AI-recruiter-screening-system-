import pathlib

p = pathlib.Path(r"AI-recruiter-screening-system-\api.py")
src = p.read_text(encoding="utf-8")

# Skip if the new endpoints are already present.
if "POST /api/code-review/start" not in src and "/api/code-review/start" not in src:
    add = """

# ==================================================
# Code Review + Security Review background jobs
# ==================================================
#
# Two independent flows that share only the in-process job manager
# (jobs_db, persisted to review_jobs.json) and the polling mechanism.
# Each flow has its own:
#   - endpoint pair (start + jobs/<id>)
#   - SKILL.md manifest (code-review-policy vs security-review)
#   - report generator (render_checklist.py vs render_security_report.py)
#   - output location (.code-review/ vs skills/reports/)
#   - job record (kind field)
#
# A failure in one flow does not affect the other.

JOB_KIND_CODE_REVIEW = "code-review"
JOB_KIND_SECURITY_REVIEW = "security-review"
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"

REPO_ROOT_FOR_JOBS = pathlib.Path(__file__).resolve().parent
SKILLS_DIR_FOR_JOBS = REPO_ROOT_FOR_JOBS / "skills"
CODE_REVIEW_DIR = REPO_ROOT_FOR_JOBS / ".code-review"
SECURITY_REVIEW_DIR = REPO_ROOT_FOR_JOBS / "skills" / "reports"


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _diff_against_main(limit_files: int = 200, limit_chars: int = 80000) -> Dict[str, Any]:
    \"\"\"Return {files: [...], diff: '...'} for the current diff against main.\"\"\"
    files: List[str] = []
    diff_text = ""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "main..HEAD"],
            cwd=str(REPO_ROOT_FOR_JOBS),
            capture_output=True, text=True, timeout=15,
        )
        files = [f for f in proc.stdout.splitlines() if f.strip()][:limit_files]
    except Exception:
        pass
    try:
        proc = subprocess.run(
            ["git", "diff", "main..HEAD"],
            cwd=str(REPO_ROOT_FOR_JOBS),
            capture_output=True, text=True, timeout=30,
        )
        diff_text = proc.stdout[:limit_chars]
    except Exception:
        pass
    return {"files": files, "diff": diff_text}


def _create_job(kind: str) -> str:
    job_id = str(uuid.uuid4())
    jobs_db[job_id] = {
        "id": job_id,
        "kind": kind,
        "status": JOB_QUEUED,
        "started_at": _now_iso(),
        "finished_at": None,
        "error": None,
        "report_path": None,
    }
    save_jobs()
    return job_id


def _set_job(job_id: str, **fields) -> None:
    if job_id in jobs_db:
        jobs_db[job_id].update(fields)
        save_jobs()


def _call_llm_for_skill(skill_name: str, payload: Dict[str, Any]) -> str:
    \"\"\"Call Ollama or Gemini with the skill's SKILL.md as the system prompt.\"\"\"
    manifest_path = SKILLS_DIR_FOR_JOBS / skill_name / "SKILL.md"
    if not manifest_path.exists():
        raise RuntimeError(f"Skill manifest not found: {manifest_path}")
    system = manifest_path.read_text(encoding="utf-8")
    user_prompt = (
        "# Skill: " + skill_name + "\n\n"
        "```json\n" + json.dumps(payload, indent=2, ensure_ascii=False) + "\n```\n\n"
        "Follow the SKILL.md manifest above. Apply it to the payload and return your findings in the format described in the manifest."
    )

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.5-flash:generateContent?key=" + api_key
            )
            data = {"contents": [{"parts": [{"text": system + "\n\n" + user_prompt}]}]}
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            print(f"[llm] Gemini failed ({exc}); falling back to Ollama")

    ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    req = urllib.request.Request(
        f"{ollama_host}/api/generate",
        data=json.dumps({"model": "llama3.2", "prompt": system + "\n\n" + user_prompt, "stream": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("response", "")


def _run_code_review_worker(job_id: str) -> None:
    try:
        _set_job(job_id, status=JOB_RUNNING)
        diff = _diff_against_main()
        review_md = _call_llm_for_skill("code-review-policy", {
            "mode": "changed-files",
            "files": diff["files"],
            "diff": diff["diff"],
        })
        CODE_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        data_path = CODE_REVIEW_DIR / f"last-checklist-data-{job_id}.json"
        report_path = CODE_REVIEW_DIR / "checklist-report.html"
        data_path.write_text(json.dumps({
            "projectName": "AI Recruiter Screening System",
            "repositoryBranch": "main",
            "reviewerName": "Code Review Policy (background job " + job_id[:8] + ")",
            "reviewDate": datetime.datetime.now().strftime("%Y-%m-%d"),
            "hasTests": "See report",
            "coveragePercent": "Manual",
            "manualTestNotes": review_md[:2000],
            "codeQuality": [],
            "hasSecuritySection": False,
            "securityChecks": [],
            "performanceChecks": [],
            "stylePractices": [],
            "generalChecklist": [],
            "reviewerFeedbacks": [],
            "finalNotes": review_md[:8000],
            "approvedBy": "Code Review Policy",
            "approvalDate": datetime.datetime.now().strftime("%Y-%m-%d"),
            "mergeStatus": "Approve with Suggestions",
            "checkedItems": [],
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        renderer = REPO_ROOT_FOR_JOBS / "skills" / "code-review-policy" / "render_checklist.py"
        proc = subprocess.run(
            [sys.executable, str(renderer),
             "--structured", str(SKILLS_DIR_FOR_JOBS / "code-review-policy" / "templates" / "checklist-structured.md"),
             "--detailed",   str(SKILLS_DIR_FOR_JOBS / "code-review-policy" / "templates" / "checklist-detailed.md"),
             "--data",       str(data_path),
             "--output",     str(report_path)],
            cwd=str(REPO_ROOT_FOR_JOBS), capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"renderer failed: {proc.stderr}")
        _set_job(job_id, status=JOB_COMPLETED, finished_at=_now_iso(), report_path=str(report_path))
    except Exception as exc:
        _set_job(job_id, status=JOB_FAILED, finished_at=_now_iso(), error=str(exc))


def _run_security_review_worker(job_id: str) -> None:
    try:
        _set_job(job_id, status=JOB_RUNNING)
        diff = _diff_against_main()
        review_md = _call_llm_for_skill("security-review", {
            "files": diff["files"],
            "diff": diff["diff"],
            "mode": "all",
        })
        SECURITY_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        data_path = SECURITY_REVIEW_DIR / f"security-review-data-{stamp}.json"
        report_path = SECURITY_REVIEW_DIR / f"security-review-all-{stamp}.html"
        data_path.write_text(json.dumps({
            "projectName": "AI Recruiter Screening System",
            "repositoryBranch": "main",
            "reviewerName": "Security Review (background job " + job_id[:8] + ")",
            "reviewDate": datetime.datetime.now().strftime("%Y-%m-%d"),
            "hasTests": "See report",
            "coveragePercent": "Manual",
            "manualTestNotes": "Review the rendered HTML report.",
            "codeQuality": [],
            "hasSecuritySection": True,
            "securityChecks": [],
            "performanceChecks": [],
            "stylePractices": [],
            "generalChecklist": [],
            "reviewerFeedbacks": [],
            "finalNotes": review_md[:8000],
            "approvedBy": "Security Review",
            "approvalDate": datetime.datetime.now().strftime("%Y-%m-%d"),
            "mergeStatus": "Approve with Suggestions",
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        renderer = SKILLS_DIR_FOR_JOBS / "render_security_report.py"
        proc = subprocess.run(
            [sys.executable, str(renderer),
             "--data",   str(data_path),
             "--output", str(report_path),
             "--mode",   "all",
             "--stamp",  stamp],
            cwd=str(REPO_ROOT_FOR_JOBS), capture_output=True, text=True, timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"renderer failed: {proc.stderr}")
        _set_job(job_id, status=JOB_COMPLETED, finished_at=_now_iso(), report_path=str(report_path))
    except Exception as exc:
        _set_job(job_id, status=JOB_FAILED, finished_at=_now_iso(), error=str(exc))


class CodeReviewStartRequest(BaseModel):
    mode: str = "changed-files"


class SecurityReviewStartRequest(BaseModel):
    mode: str = "all"


@api.post("/api/code-review/start")
def start_code_review(req: CodeReviewStartRequest):
    job_id = _create_job(JOB_KIND_CODE_REVIEW)
    threading.Thread(target=_run_code_review_worker, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": JOB_QUEUED, "kind": JOB_KIND_CODE_REVIEW}


@api.post("/api/security-review/start")
def start_security_review(req: SecurityReviewStartRequest):
    job_id = _create_job(JOB_KIND_SECURITY_REVIEW)
    threading.Thread(target=_run_security_review_worker, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": JOB_QUEUED, "kind": JOB_KIND_SECURITY_REVIEW}


@api.get("/api/code-review/jobs/{job_id}")
def get_code_review_job(job_id: str):
    return _get_job_response(job_id, JOB_KIND_CODE_REVIEW)


@api.get("/api/security-review/jobs/{job_id}")
def get_security_review_job(job_id: str):
    return _get_job_response(job_id, JOB_KIND_SECURITY_REVIEW)


def _get_job_response(job_id: str, expected_kind: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="job not found")
    job = jobs_db[job_id]
    if job.get("kind") != expected_kind:
        raise HTTPException(status_code=400, detail="job kind mismatch")
    return job
"""
    src = src.rstrip() + "\n" + add
    p.write_text(src, encoding="utf-8")
    print("appended", len(add), "bytes")
else:
    print("already present")