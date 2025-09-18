#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import yaml
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def iso_now() -> str:
    return datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat()


def read_yaml(file_path: Path) -> Dict[str, Any]:
    with file_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_script(script_path: Path, env: Optional[Dict[str, str]] = None, timeout: Optional[int] = None) -> Tuple[int, str, str]:
    proc = subprocess.Popen(
        ["bash", str(script_path)],
        cwd=str(script_path.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **(env or {})},
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return 124, out, err or "timeout"
    return proc.returncode, out, err


def run_agent(prompt: str, agent_cmd_template: Optional[str], extra_env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
    if not agent_cmd_template:
        # No agent command configured; return placeholder
        msg = "agent command not configured; skipped running agent"
        return 0, msg, ""

    # If the template contains {prompt}, substitute; otherwise send via stdin
    if "{prompt}" in agent_cmd_template:
        cmd = agent_cmd_template.format(prompt=prompt)
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, **(extra_env or {})},
        )
        out, err = proc.communicate()
        return proc.returncode, out, err
    else:
        proc = subprocess.Popen(
            agent_cmd_template,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, **(extra_env or {})},
        )
        out, err = proc.communicate(input=prompt)
        return proc.returncode, out, err


def collect_tools_static() -> List[str]:
    # 基于 README 中示例，提供一个静态列表；后续可改为从服务端动态获取
    return [
        "ack_kubectl",
        "diagnose_resource",
        "get_current_time",
        "get_diagnose_resource_result",
        "list_clusters",
        "query_audit_logs",
        "query_controlplane_logs",
        "query_inspect_report",
        "query_prometheus",
        "query_prometheus_metric_guidance",
    ]


def find_task_dirs(tasks_root: Path) -> List[Path]:
    task_dirs: List[Path] = []
    if not tasks_root.exists():
        return task_dirs
    for child in sorted(tasks_root.iterdir()):
        if child.is_dir() and (child / "task.yaml").exists():
            task_dirs.append(child)
    return task_dirs


def get_git_commit_id(repo_root: Path) -> str:
    try:
        proc = subprocess.Popen(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        out, _ = proc.communicate(timeout=5)
        if proc.returncode == 0:
            return out.strip()
    except Exception:
        pass
    return "unknown"


def run_task(task_dir: Path, agent_cmd_template: Optional[str], skip_setup: bool, skip_cleanup: bool, verify_timeout: Optional[int], agent_env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    task_yaml = read_yaml(task_dir / "task.yaml")
    task_name = task_dir.name

    start_ts = iso_now()
    result_content = ""
    verify_content = ""
    error_msg: Optional[str] = None
    is_success = False

    try:
        # setup
        if not skip_setup:
            for item in task_yaml.get("setup", []):
                script_file = item.get("setup_script_file")
                if not script_file:
                    continue
                rc, out, err = run_script(task_dir / script_file)
                result_content += f"\n[setup:{script_file}] rc={rc}\n{out}\n{err}"
                print(f"[setup:{script_file}] rc={rc}")
                if out:
                    print(out)
                if err:
                    print(err)
                if rc != 0:
                    raise RuntimeError(f"setup failed: {script_file} rc={rc}")

        # agent conversation/scripts
        for script in task_yaml.get("scripts", []):
            prompt = script.get("prompt", "").strip()
            if not prompt:
                continue
            rc, out, err = run_agent(prompt, agent_cmd_template, extra_env=agent_env)
            result_content += f"\n[agent] rc={rc}\n>>> prompt:\n{prompt}\n<<< output:\n{out}\n<<< stderr:\n{err}"
            print("[agent] rc=" + str(rc))
            print(">>> prompt:\n" + prompt)
            if out:
                print("<<< output:\n" + out)
            if err:
                print("<<< stderr:\n" + err)
            if rc != 0:
                # 不硬失败，允许后续 verify 判断
                error_msg = (error_msg or "") + f"; agent rc={rc}"

        # verify
        verify_rc_aggregate = 0
        for item in task_yaml.get("verify", []):
            script_file = item.get("verify_script_file")
            if not script_file:
                continue
            rc, out, err = run_script(task_dir / script_file, timeout=verify_timeout)
            verify_content += f"\n[verify:{script_file}] rc={rc}\n{out}\n{err}"
            print(f"[verify:{script_file}] rc={rc}")
            if out:
                print(out)
            if err:
                print(err)
            verify_rc_aggregate = rc or verify_rc_aggregate

        is_success = verify_rc_aggregate == 0

    except Exception as e:
        error_msg = str(e)
    finally:
        if not skip_cleanup:
            for item in task_yaml.get("cleanup", []):
                script_file = item.get("cleanup_script_file")
                if not script_file:
                    continue
                rc, out, err = run_script(task_dir / script_file)
                result_content += f"\n[cleanup:{script_file}] rc={rc}\n{out}\n{err}"
                print(f"[cleanup:{script_file}] rc={rc}")
                if out:
                    print(out)
                if err:
                    print(err)

    finished_ts = iso_now()

    return {
        "task_name": task_name,
        "is_success": bool(is_success),
        "error": error_msg,
        "startTimestamp": start_ts,
        "finishedTimestamp": finished_ts,
        "result_content": (result_content or None),
        "verify_content": (verify_content or None),
    }


def build_report_metadata(agent_name: str, llm_model: str, mcp_server_version: str) -> Dict[str, Any]:
    return {
        "creationTimestamp": iso_now(),
        "finishedTimestamp": iso_now(),  # 将在写出前更新
        "ai_agent": {
            "name": agent_name,
        },
        "llm_model": {
            "name": llm_model,
        },
        "mcp-server": [
            {
                "name": "ack-mcp-server",
                "version": mcp_server_version,
            }
        ],
        "tools": collect_tools_static(),
        "external_configs": [
            {"debug": bool(os.environ.get("BENCH_DEBUG"))},
            {"debug_log_path": os.environ.get("BENCH_DEBUG_LOG", "")},
        ],
    }


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark runner for ack-mcp-server")
    parser.add_argument("--tasks-dir", default=str(Path(__file__).parent / "tasks"), help="tasks root directory")
    parser.add_argument("--results-dir", default=str(Path(__file__).parent / "results"), help="results output directory")
    parser.add_argument("--only", default="", help="comma separated task dir names to run")
    parser.add_argument("--skip-setup", action="store_true", help="skip running setup scripts")
    parser.add_argument("--skip-cleanup", action="store_true", help="skip running cleanup scripts")
    parser.add_argument("--verify-timeout", type=int, default=300, help="verify script timeout seconds")
    parser.add_argument("--agent", default=os.environ.get("BENCH_AGENT_NAME", "qwen_code"), help="agent: kubectl-ai or qwen_code")
    parser.add_argument("--llm-model", default="qwen3-32b")
    parser.add_argument("--model", dest="llm_model", help="alias of --llm-model")
    parser.add_argument("--openai-api-key", required=True, help="OpenAI-compatible API key for both agents")
    parser.add_argument(
        "--openai-base-url",
        default="https://dashscope.aliyuncs.com/compatible-mode/v1/",
        help="OpenAI-compatible base URL; default is DashScope compatible endpoint",
    )
    parser.add_argument("--mcp-server-version", default=os.environ.get("MCP_SERVER_VERSION", ""), help="ack-mcp-server version, default to current git commit id")
    parser.add_argument(
        "--agent-cmd-template",
        default=os.environ.get("BENCH_AGENT_CMD", ""),
        help="Agent command template; include {prompt} placeholder to inline prompt, otherwise it will be piped via stdin",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    tasks_root = Path(args.tasks_dir).resolve()
    results_dir = Path(args.results_dir).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    selected: Optional[set] = None
    if args.only.strip():
        selected = {x.strip() for x in args.only.split(",") if x.strip()}

    task_dirs = [d for d in find_task_dirs(tasks_root) if (not selected or d.name in selected)]
    if not task_dirs:
        print(f"No tasks found under {tasks_root}", file=sys.stderr)
        return 2

    # Resolve mcp server version default as current git commit id
    repo_root = Path(__file__).resolve().parent.parent
    mcp_server_version = args.mcp_server_version or get_git_commit_id(repo_root)

    report: Dict[str, Any] = {
        "report_metadata": build_report_metadata(args.agent, args.llm_model, mcp_server_version),
        "results": {
            "tasks": []
        },
    }

    # Prepare agent cmd with model interpolation if needed
    # Prepare agent cmd with model interpolation if needed
    agent_cmd_template: Optional[str]
    if args.agent_cmd_template:
        agent_cmd_template = args.agent_cmd_template
    else:
        # Provide sensible defaults based on agent
        agent_lower = (args.agent or "").lower().strip()
        if agent_lower == "qwen_code":
            agent_cmd_template = (
                "qwen --openai-api-key \"{api_key}\" --openai-base-url \"{base_url}\" --model \"{model}\" -p \"{prompt}\""
            )
        else:
            # kubectl-ai: pass prompt as positional after --mcp-client
            agent_cmd_template = (
                "kubectl-ai --llm-provider=openai --model={model} --mcp-client \"{prompt}\""
            )
    agent_cmd_template = (agent_cmd_template or "").replace("{model}", args.llm_model)

    # Build agent environment (unified for both agents)
    agent_env = {
        "OPENAI_API_KEY": args.openai_api_key,
        "OPENAI_BASE_URL": args.openai_base_url,
        "OPENAI_ENDPOINT": args.openai_base_url,  # compatibility
    }

    for task_dir in task_dirs:
        task_result = run_task(
            task_dir=task_dir,
            agent_cmd_template=agent_cmd_template,
            skip_setup=args.skip_setup,
            skip_cleanup=args.skip_cleanup,
            verify_timeout=args.verify_timeout,
            agent_env=agent_env,
        )
        report["results"]["tasks"].append(task_result)

    # Update finished timestamp
    report["report_metadata"]["finishedTimestamp"] = iso_now()

    # File name: YYYYMMDD-report.yaml (ensure uniqueness with time if exists)
    date_prefix = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d")
    out_path = results_dir / f"{date_prefix}-report.yaml"
    if out_path.exists():
        # append HHMMSS
        out_path = results_dir / f"{date_prefix}-{datetime.datetime.now(datetime.UTC).strftime('%H%M%S')}-report.yaml"

    with out_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f, allow_unicode=True, sort_keys=False)

    print(f"Benchmark report written to: {out_path}")
    # Non-zero if any task failed
    any_fail = any(not t.get("is_success") for t in report["results"]["tasks"])
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())


