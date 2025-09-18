import os
import shutil
import tempfile
from pathlib import Path
import yaml

import benchmarks.benchmark_main as bm


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_run_single_task_success(monkeypatch):
    tmpdir = Path(tempfile.mkdtemp(prefix="bench-ut-"))
    try:
        tasks_root = tmpdir / "tasks"
        results_dir = tmpdir / "results"

        # Create a minimal task workspace
        task_dir = tasks_root / "1-fix-pod-oom"
        write_file(task_dir / "task.yaml", """
task_name: "fix-pod-oom"
scripts:
  - prompt: "请修复 case1-fix-pod-oom 命名空间下的 OOM 问题"
setup:
  - setup_script_file: "setup.sh"
cleanup:
  - cleanup_script_file: "cleanup.sh"
verify:
  - verify_script_file: "verify.sh"
""")

        # Setup scripts: always succeed quickly
        write_file(task_dir / "setup.sh", "#!/usr/bin/env bash\necho setup ok\n")
        write_file(task_dir / "cleanup.sh", "#!/usr/bin/env bash\necho cleanup ok\n")
        write_file(task_dir / "verify.sh", "#!/usr/bin/env bash\necho verify ok\nexit 0\n")

        # Make scripts executable (optional in our runner, but good practice)
        for f in ["setup.sh", "cleanup.sh", "verify.sh"]:
            p = task_dir / f
            os.chmod(p, 0o755)

        # Monkeypatch run_agent to avoid real subprocess call
        def fake_run_agent(prompt: str, agent_cmd_template: str, extra_env=None):
            try:
                out = f"FAKE_AGENT_OUTPUT for: {prompt}"
                print(out)
                return 0, out, ""
            except Exception as e:
                print(f"[test] run_agent exception: {e}")
                return 127, "", str(e)

        monkeypatch.setattr(bm, "run_agent", fake_run_agent)

        # Wrap bm.run_script with try/except to catch all subprocess issues
        original_run_script = bm.run_script

        def safe_run_script(script_path, env=None, timeout=None):
            try:
                return original_run_script(script_path, env=env, timeout=timeout)
            except Exception as e:
                print(f"[test] run_script exception on {script_path}: {e}")
                return 127, "", str(e)

        monkeypatch.setattr(bm, "run_script", safe_run_script)

        # Run benchmark main with our temp dirs
        try:
            exit_code = bm.main([
                "--tasks-dir", str(tasks_root),
                "--results-dir", str(results_dir),
                "--agent", "kubectl-ai",
                "--llm-model", "qwen3-coder-plus",
                "--openai-api-key", "sk-test",
            ])
        except Exception as e:
            print(f"[test] bm.main exception: {e}")
            assert False, f"bm.main raised exception: {e}"

        assert exit_code == 0

        # Verify report file exists and structure matches expectation
        files = list(results_dir.glob("*-report.yaml"))
        assert files, "report file not generated"
        report_path = files[0]
        report_text = report_path.read_text(encoding="utf-8")
        print("=== Benchmark Report Raw ===\n" + report_text)
        report = yaml.safe_load(report_text)

        assert "report_metadata" in report
        assert "results" in report and "tasks" in report["results"]
        assert len(report["results"]["tasks"]) == 1
        task_result = report["results"]["tasks"][0]
        assert task_result["task_name"] == "1-fix-pod-oom"
        assert task_result["is_success"] is True
        assert task_result["error"] is None or task_result["error"] == ""
        assert "result_content" in task_result
        assert "verify_content" in task_result
        # Echo task outputs to stdout for visibility in CI logs
        print("=== Task Result Content ===\n" + (task_result.get("result_content") or ""))
        print("=== Task Verify Content ===\n" + (task_result.get("verify_content") or ""))

    finally:
        shutil.rmtree(tmpdir)


