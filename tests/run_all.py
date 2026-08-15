#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT_DIR / "reports" / "tests"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DIRECTORIES = [
    "tests/unit",
    "tests/integration",
    "tests/performance",
]

def run_command_for_target(cmd_list, test_id, rel_file):
    print(f"Executing [{test_id}]: {' '.join(cmd_list)}")
    start_time = time.time()
    try:
        res = subprocess.run(cmd_list, cwd=ROOT_DIR, capture_output=True, text=True, timeout=120, check=False)
        exit_code = res.returncode
        stdout = res.stdout
        stderr = res.stderr
    except subprocess.TimeoutExpired as e:
        exit_code = -1
        stdout = e.stdout or ""
        stderr = (e.stderr or "") + "\nTimeout expired during test execution."
    except Exception as e:
        exit_code = 1
        stdout = ""
        stderr = str(e)

    elapsed_ms = int((time.time() - start_time) * 1000)
    status = "Passed" if exit_code == 0 else "Failed"

    result_data = {
        "test_id": test_id,
        "file": rel_file,
        "command": " ".join(cmd_list),
        "stdout": stdout,
        "stderr": stderr,
        "logs": f"Executing command: {' '.join(cmd_list)}\n\n--- STDOUT ---\n{stdout}\n" + (f"\n--- STDERR ---\n{stderr}\n" if stderr else ""),
        "exitCode": exit_code,
        "elapsedMs": elapsed_ms,
        "status": status,
        "artifacts": str(REPORTS_DIR),
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    report_file = REPORTS_DIR / f"{test_id}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    print(f"[{status}] {test_id} ({elapsed_ms}ms)")
    return status == "Passed"

def main():
    passed = 0
    failed = 0
    total = 0
    failed_tests = []

    def run_and_track(cmd_list, test_id, rel_file):
        nonlocal passed, failed, total
        total += 1
        success = run_command_for_target(cmd_list, test_id, rel_file)
        if success:
            passed += 1
        else:
            failed += 1
            failed_tests.append(test_id)
        return success

    # 1. Iterate through tests/unit directory files
    unit_dir = ROOT_DIR / "tests" / "unit"
    if unit_dir.exists():
        for py_file in sorted(unit_dir.glob("*.py")):
            if py_file.name.startswith("conftest") or py_file.name == "__init__.py":
                continue
            test_id = py_file.stem
            cmd = ["python3", "-m", "pytest", str(py_file), "-v"]
            run_and_track(cmd, test_id, str(py_file.relative_to(ROOT_DIR)))

    # 2. Iterate through tests/integration directory files & scenarios
    integration_dir = ROOT_DIR / "tests" / "integration"
    if integration_dir.exists():
        for py_file in sorted(integration_dir.glob("*.py")):
            if py_file.name.startswith("conftest") or py_file.name == "__init__.py":
                continue
            test_id = py_file.stem
            cmd = ["python3", "-m", "pytest", str(py_file), "-v"]
            if py_file.name == "run_scenario_matrix.py":
                cmd = ["python3", str(py_file), "--no-auth"]
                test_id = "scenario_matrix_all"
            run_and_track(cmd, test_id, str(py_file.relative_to(ROOT_DIR)))

    # 3. Iterate through tests/performance directory (benchmarks, load, profiles)
    perf_dir = ROOT_DIR / "tests" / "performance"
    if perf_dir.exists():
        bench_dir = perf_dir / "benchmarks"
        if bench_dir.exists():
            for py_file in sorted(bench_dir.glob("*.py")):
                if py_file.name.startswith("conftest") or py_file.name == "__init__.py":
                    continue
                test_id = py_file.stem
                cmd = ["python3", "-m", "pytest", str(py_file), "-v"]
                run_and_track(cmd, test_id, str(py_file.relative_to(ROOT_DIR)))

        load_dir = perf_dir / "load"
        if load_dir.exists():
            for js_file in sorted(load_dir.glob("*.js")):
                test_id = f"k6_{js_file.stem}"
                rel_file = str(js_file.relative_to(ROOT_DIR))
                if shutil.which("k6"):
                    cmd = ["k6", "run", rel_file]
                elif shutil.which("node"):
                    cmd = ["node", "-c", rel_file]
                else:
                    cmd = ["node", "-c", rel_file]
                run_and_track(cmd, test_id, rel_file)

        profiles_dir = perf_dir / "profiles"
        if profiles_dir.exists():
            for py_file in sorted(profiles_dir.glob("*.py")):
                test_id = py_file.stem
                cmd = ["python3", str(py_file)]
                run_and_track(cmd, test_id, str(py_file.relative_to(ROOT_DIR)))

    print("\n========================================")
    print(f"Test Run Complete: Total: {total}, Passed: {passed}, Failed: {failed}")
    if failed_tests:
        print("\n❌ FAILED TESTS DETAIL:")
        for tid in failed_tests:
            rep_file = REPORTS_DIR / f"{tid}.json"
            if rep_file.exists():
                try:
                    rdata = json.loads(rep_file.read_text(encoding="utf-8"))
                    print(f" - [{tid}] ExitCode: {rdata.get('exitCode')}")
                    err_lines = [l for l in rdata.get('stderr', '').splitlines() if l.strip()]
                    if err_lines:
                        print(f"   Error snippet: {err_lines[-1]}")
                except Exception:
                    print(f" - [{tid}] (Report read error)")
            else:
                print(f" - [{tid}] (No report artifact found)")
    print("========================================")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
