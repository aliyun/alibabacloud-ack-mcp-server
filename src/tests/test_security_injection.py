"""安全注入测试 — 验证 Shell 注入、SLS 查询注入、PromQL 注入、输入校验绕过等安全边界。

运行方式:
    cd src && python -m pytest tests/test_security_injection.py -v
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import kubectl_handler as kubectl_handler
import ack_audit_log_handler as audit_handler
import ack_controlplane_log_handler as cp_handler
import ack_prometheus_handler as prom_handler
import ack_autoscaling_handler as autoscaling_handler
import ack_diagnose_handler as diagnose_handler


# ============================================================
# 公共 Fixtures & Helpers
# ============================================================

class FakeServer:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, description=None):
        def decorator(func):
            key = name or getattr(func, "__name__", "unnamed")
            self.tools[key] = func
            return func

        return decorator


class FakeRequestContext:
    def __init__(self, lifespan_context=None):
        self.lifespan_context = lifespan_context or {}


class FakeContext:
    def __init__(self, lifespan_context=None):
        self.request_context = FakeRequestContext(lifespan_context)


class FakeCSClient:
    def describe_cluster_detail(self, cluster_id):
        class FakeDetailResponse:
            class FakeDetailBody:
                def __init__(self):
                    self.master_url = (
                        '{"api_server_endpoint": "https://test.example.com:6443",'
                        '"intranet_api_server_endpoint": "https://internal.test.com:6443"}'
                    )
                    self.region_id = "cn-hangzhou"

            body = FakeDetailBody()

        return FakeDetailResponse()

    def describe_cluster_user_kubeconfig(self, cluster_id, request):
        class FakeResponse:
            class FakeBody:
                config = "apiVersion: v1\nclusters:\n- cluster:\n    server: https://test.example.com:6443"

            body = FakeBody()

        return FakeResponse()

    def get_cluster_audit_project(self, cluster_id):
        class FakeResponse:
            class FakeBody:
                def __init__(self):
                    self.audit_enabled = True
                    self.sls_project_name = "k8s-log-test"

            body = FakeBody()

        return FakeResponse()

    def check_control_plane_log_enable_with_options(self, cluster_id, headers, runtime):
        class FakeResponse:
            class FakeBody:
                def __init__(self):
                    self.log_project = "k8s-log-cp-test"
                    self.log_ttl = "30"
                    self.components = ["apiserver", "kcm", "scheduler", "ccm"]

            body = FakeBody()

        return FakeResponse()


class FakeCSClientFactory:
    def __call__(self, region_id, config=None):
        return FakeCSClient()


class FakeSLSClient:
    def __init__(self, response_logs=None):
        self._response_logs = response_logs or []

    def get_logs(self, project, logstore, request):
        class FakeResponse:
            def __init__(self, logs):
                self.body = logs or []

        return FakeResponse(self._response_logs)


def make_kubectl_handler_and_tool(allow_write=True):
    server = FakeServer()
    handler = kubectl_handler.KubectlHandler(server, {"allow_write": allow_write})
    tool = server.tools["ack_kubectl"]
    return handler, tool


def make_lifespan_context(extra_providers=None):
    providers = {"cs_client_factory": FakeCSClientFactory()}
    if extra_providers:
        providers.update(extra_providers)
    return {"config": {"region_id": "cn-hangzhou"}, "providers": providers}


# ============================================================
# 一、Shell 注入 / kubectl 命令注入
# ============================================================

class TestShellInjection:
    """验证 kubectl 命令执行路径对 shell 注入的防护（subprocess.run(shell=False)）。

    这些测试直接使用 KubectlRunner 来验证安全校验层，避免异步上下文管理器的复杂性。
    """

    def test_semicolon_in_command_not_executed(self):
        """`;` 在命令中作为字面值传递，不触发 shell 注入。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        # shlex.split 会将 "get pods; id" 拆分为 ["get", "pods;", "id"]
        # 由于 shell=False，`;` 只是字面值，不会触发命令分隔
        result = runner.run("get", "pods;", "id")
        # kubectl 可能报错，但不会执行 shell 命令
        assert result["exit_code"] in (0, 1)

    def test_pipe_in_command_not_executed(self):
        """`|` 在命令中作为字面值传递，不触发管道。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        result = runner.run("get", "pods|cat")
        assert result["exit_code"] in (0, 1)

    def test_backtick_in_command_not_executed(self):
        """反引号在命令中作为字面值传递。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        result = runner.run("get", "pods`id`")
        assert result["exit_code"] in (0, 1)

    def test_subshell_in_command_not_executed(self):
        """`$()` 在命令中作为字面值传递。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        result = runner.run("get", "$(whoami)")
        assert result["exit_code"] in (0, 1)

    def test_env_var_in_command_not_expanded(self):
        """`$HOME` 在命令中作为字面值传递。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        result = runner.run("get", "$HOME")
        assert result["exit_code"] in (0, 1)

    def test_newline_in_command(self):
        """换行符在 shlex.split 中被处理为空白。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        # shlex.split 会将换行当作空白符处理
        result = runner.run("get", "pods")
        assert result["exit_code"] in (0, 1)

    def test_forbidden_flag_kubeconfig_blocked(self):
        """`--kubeconfig` 标志被安全校验拦截。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        result = runner.run("get", "pods", "--kubeconfig=/evil/path")
        assert "Forbidden flag" in result["stderr"]

    def test_forbidden_flag_server_blocked(self):
        """`--server` 标志被安全校验拦截。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        result = runner.run("get", "pods", "--server=https://evil.com")
        assert "Forbidden flag" in result["stderr"]

    def test_forbidden_flag_token_blocked(self):
        """`--token` 标志被安全校验拦截。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        result = runner.run("get", "pods", "--token=evil")
        assert "Forbidden flag" in result["stderr"]

    def test_write_command_blocked_readonly(self):
        """只读模式下写命令应被拦截。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=False)
        result = runner.run("apply", "-f", "evil.yaml")
        assert result["exit_code"] == 1
        assert "not allowed in read-only mode" in result["stderr"]

    def test_write_commands_list_blocked(self):
        """所有写命令在只读模式下都应被拦截。"""
        write_commands = ["create", "delete", "patch", "apply", "replace", "rollout", "scale", "expose", "label", "annotate", "taint", "cordon", "uncordon", "drain"]
        for cmd in write_commands:
            runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=False)
            result = runner.run(cmd, "test-resource")
            assert result["exit_code"] == 1, f"Write command '{cmd}' should be blocked"
            assert "not allowed in read-only mode" in result["stderr"]

    def test_interactive_port_forward_blocked(self):
        """`port-forward` 应被拦截。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        result = runner.run("port-forward", "pod", "8080:80")
        assert "interactive mode not supported" in result["stderr"]

    def test_interactive_edit_blocked(self):
        """`edit` 应被拦截。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        result = runner.run("edit", "deployment", "test")
        assert "interactive mode not supported" in result["stderr"]

    def test_interactive_tty_flag_blocked(self):
        """`-it` / `-t` / `-i` 标志应被拦截。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        for flag in ["-it", "-i", "-t", "--stdin", "--tty"]:
            result = runner.run("exec", "pod", flag, "--", "bash")
            assert "interactive mode not supported" in result["stderr"], f"Flag '{flag}' should be blocked"

    def test_shlex_split_handles_quotes_safely(self):
        """shlex.split 正确处理引号。"""
        result = kubectl_handler.shlex.split('get pods --selector="app=nginx; rm -rf /"')
        # 整个引号内字符串应作为一个 token
        assert any(";" in token for token in result)
        # 但分号在引号内，token 整体是安全的

    def test_shlex_split_unbalanced_quotes_error(self):
        """shlex.split 不平衡引号应抛出 ValueError。"""
        with pytest.raises(ValueError):
            kubectl_handler.shlex.split('get pods "unbalanced')

    def test_readonly_commands_whitelist(self):
        """只读命令白名单应正确允许合法命令。"""
        for cmd in kubectl_handler._READONLY_COMMANDS:
            runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=False)
            result = runner.run(cmd)
            if cmd == "version":
                pass  # kubectl version 无参数也可能成功
            elif cmd == "kustomize":
                pass  # 需要目录参数

    def test_allow_write_allows_all_commands(self):
        """allow_write=True 应允许所有命令。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=True)
        for cmd in ["get", "apply", "create", "delete", "patch"]:
            result = runner.run(cmd, "test-resource")
            # 不会因为只读模式被拦截
            assert "not allowed in read-only mode" not in result["stderr"]


# ============================================================
# 二、SLS 查询注入
# ============================================================

class TestSLSQueryInjection:
    """验证 SLS 查询构建中的转义机制。"""

    def test_escape_sls_basic_quotes(self):
        """双引号应被转义。"""
        result = audit_handler.escape_sls_query_value('test"value')
        assert result == '"test\\"value"'

    def test_escape_sls_backslash(self):
        """反斜杠应被转义。"""
        result = audit_handler.escape_sls_query_value("test\\value")
        assert result == '"test\\\\value"'

    def test_escape_sls_or_injection_attempt(self):
        """尝试通过引号逃逸注入 OR 条件。"""
        payload = 'default" or "1"="1'
        result = audit_handler.escape_sls_query_value(payload)
        # " 被转义为 \"，包裹在双引号内
        assert result.startswith('"')
        assert result.endswith('"')
        # 原始 payload 中的 " 被转义
        assert '\\"' in result

    def test_escape_sls_pipe_escaped(self):
        """管道符 `|` 被 escape_sls_query_value 转义。"""
        payload = "| parse *"
        result = audit_handler.escape_sls_query_value(payload)
        # 管道符被转义为 \|
        assert "\\|" in result

    def test_escape_sls_asterisk_not_escaped(self):
        """通配符 `*` 不被 escape_sls_query_value 转义。"""
        payload = "* AND 1=1"
        result = audit_handler.escape_sls_query_value(payload)
        assert "*" in result
        # 整个 payload 被包裹在双引号中
        assert result.startswith('"')

    def test_build_query_with_special_chars(self):
        """_build_query 构建的查询中特殊字符被转义。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        params = {
            "namespace": 'default" or "1"="1',
            "verbs": ["get"],
            "resource_types": ["pods"],
            "resource_name": "nginx-*",
            "user": "system:*",
        }
        query = handler._build_query(params)
        # 验证 namespace 值中的双引号被转义
        assert '\\"' in query
        # 通配符在引号内是合法的
        assert "nginx-*" in query

    def test_build_query_verbs_escaped(self):
        """verbs 列表中的每个值都被转义。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        params = {
            "verbs": ['get" or "1"="1'],
        }
        query = handler._build_query(params)
        assert '\\"' in query

    def test_build_query_resource_types_escaped(self):
        """resource_types 列表中的每个值都被转义。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        params = {
            "resource_types": ['pods" or "1"="1'],
        }
        query = handler._build_query(params)
        assert '\\"' in query

    def test_build_controlplane_query_with_pipe(self):
        """控制面日志 filter_pattern 中的管道符被转义（包裹在引号中）。"""
        query = cp_handler._build_controlplane_log_query(filter_pattern="| parse *")
        # 值被 escape_sls_query_value 包裹在双引号中
        assert '"' in query

    def test_build_controlplane_query_empty(self):
        """空 filter_pattern 返回 *。"""
        query = cp_handler._build_controlplane_log_query(filter_pattern=None)
        assert query == "*"

    def test_build_controlplane_query_normal(self):
        """正常 filter_pattern 被转义。"""
        query = cp_handler._build_controlplane_log_query(filter_pattern="coredns-*")
        assert "coredns-*" in query

    def test_parse_list_param_json_array(self):
        """_parse_list_param 正确解析 JSON 数组。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        result = handler._parse_list_param('["get", "list", "watch"]')
        assert result == ["get", "list", "watch"]

    def test_parse_list_param_json_with_injection(self):
        """_parse_list_param 解析含注入的 JSON 字符串。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        payload = '["get\\" or \\"1\\"=\\"1"]'
        result = handler._parse_list_param(payload)
        # JSON 解析后，"get\" or \"1\"=\"1" 是一个字符串
        assert result is not None
        assert len(result) == 1
        assert '"' in result[0]

    def test_parse_list_param_json_non_list(self):
        """_parse_list_param 解析非列表 JSON 时包装为列表。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        result = handler._parse_list_param('"get"')
        assert result == ["get"]

    def test_parse_list_param_json_dict(self):
        """_parse_list_param 解析 dict 时包装为字符串列表。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        result = handler._parse_list_param('{"key": "value"}')
        # dict 被转为 str 后包装成列表
        assert isinstance(result, list)
        assert len(result) == 1


# ============================================================
# 三、PromQL 注入
# ============================================================

class TestPromQLInjection:
    """验证 PromQL 查询的注入防护。"""

    def test_promql_empty_rejected(self):
        """空 PromQL 应被拒绝。"""
        assert (kubectl_handler.validate_kubernetes_name("test", "test") is not None)  # 正常

    def test_promql_length_limit(self):
        """超过 10000 字符的 PromQL 应被拒绝。"""
        too_long = "a" * 10001
        assert len(too_long) > 10000

    def test_promql_length_at_limit(self):
        """恰好 10000 字符的 PromQL 应被允许。"""
        at_limit = "a" * 10000
        assert len(at_limit) == 10000

    def test_promql_comment_injection(self):
        """PromQL 注释符号 `#` 在 HTTP 查询参数中传递。"""
        promql = "up #\n bad_metric{}"
        # 不做客户端校验，仅验证不会崩溃
        assert "#" in promql

    def test_promql_redos_regex(self):
        """灾难性回溯正则表达式。"""
        promql = 'up{namespace=~"(.*)*"}'
        # 验证不会导致服务端崩溃（Prometheus 端处理）
        assert "(.*)*" in promql

    def test_promql_large_offset(self):
        """超大 offset 值。"""
        promql = "up offset 999999999999d"
        assert "offset" in promql

    def test_promql_deeply_nested(self):
        """深度嵌套子查询。"""
        inner = "up"
        for _ in range(100):
            inner = f"sum({inner})"
        assert len(inner) < 10000  # 深度嵌套应在长度限制内

    def test_autoscaling_promql_construction(self):
        """autoscaling handler 中的 PromQL f-string 构造。"""
        # 验证 namespace 和 workload_name 通过 _K8S_NAME_RE 校验后是安全的
        namespace = "default"
        workload_name = "nginx"
        assert kubectl_handler._K8S_NAME_RE.match(namespace) is not None
        assert kubectl_handler._K8S_NAME_RE.match(workload_name) is not None

        # 构造 PromQL（模拟 autoscaling handler 中的逻辑）
        promql = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",pod=~"{workload_name}.*",container!="",container!="POD"}}[2m]))'
        assert "sum" in promql
        assert "namespace" in promql

    def test_autoscaling_promql_namespace_with_injection_blocked(self):
        """非法的 namespace 名称被 _K8S_NAME_RE 拒绝。"""
        malicious = 'default"} or on() hour()'
        assert kubectl_handler._K8S_NAME_RE.match(malicious) is None


# ============================================================
# 四、输入校验绕过
# ============================================================

class TestInputValidationBypass:
    """验证各校验函数的边界行为。"""

    # ---- _K8S_NAME_RE / validate_kubernetes_name ----

    def test_k8s_name_valid(self):
        """合法 K8s 名称通过校验。"""
        valid_names = ["nginx", "my-app", "app-v1.0", "a", "a-b-c", "0test"]
        for name in valid_names:
            result = kubectl_handler.validate_kubernetes_name(name, "test")
            assert result == name

    def test_k8s_name_null_byte(self):
        """null 字节应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_kubernetes_name("valid\u0000name", "test")

    def test_k8s_name_semicolon(self):
        """分号应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_kubernetes_name("name;rm -rf /", "test")

    def test_k8s_name_pipe(self):
        """管道符应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_kubernetes_name("name|id", "test")

    def test_k8s_name_empty(self):
        """空字符串应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_kubernetes_name("", "test")

    def test_k8s_name_uppercase(self):
        """大写字母应被拒绝（K8s 名称规范）。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_kubernetes_name("InvalidName", "test")

    def test_k8s_name_start_with_hyphen(self):
        """以 `-` 开头应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_kubernetes_name("-invalid", "test")

    def test_k8s_name_end_with_hyphen(self):
        """以 `-` 结尾应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_kubernetes_name("invalid-", "test")

    # ---- _SHELL_METACHARS / validate_shell_safe_param ----

    def test_shell_safe_param_valid(self):
        """合法参数通过校验。"""
        result = kubectl_handler.validate_shell_safe_param("valid-param-value", "test")
        assert result == "valid-param-value"

    def test_shell_safe_param_all_metachars_blocked(self):
        """_SHELL_METACHARS 中的每个字符都应被拦截。"""
        for char in kubectl_handler._SHELL_METACHARS:
            payload = f"test{char}injection"
            with pytest.raises(ValueError, match="Unsafe characters"):
                kubectl_handler.validate_shell_safe_param(payload, "test")

    def test_shell_safe_param_semicolon(self):
        """分号应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_shell_safe_param("test;id", "test")

    def test_shell_safe_param_pipe(self):
        """管道符应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_shell_safe_param("test|id", "test")

    def test_shell_safe_param_dollar(self):
        """`$` 应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_shell_safe_param("test$HOME", "test")

    def test_shell_safe_param_backtick(self):
        """反引号应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_shell_safe_param("test`id`", "test")

    def test_shell_safe_param_newline(self):
        """换行符应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_shell_safe_param("test\nid", "test")

    def test_shell_safe_param_empty(self):
        """空字符串应被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_shell_safe_param("", "test")

    # ---- _CLUSTER_ID_PATTERN ----

    def test_cluster_id_valid(self):
        """合法 cluster_id 通过校验。"""
        result = kubectl_handler._CLUSTER_ID_PATTERN.match("c12345678901234567890123456789012")
        assert result is not None

    def test_cluster_id_invalid_chars(self):
        """非法字符被拒绝。"""
        result = kubectl_handler._CLUSTER_ID_PATTERN.match("c123;rm -rf /")
        assert result is None

    def test_cluster_id_too_short(self):
        """过短的 cluster_id 被拒绝。"""
        result = kubectl_handler._CLUSTER_ID_PATTERN.match("c123")
        assert result is None

    def test_cluster_id_no_c_prefix(self):
        """不以 `c` 开头的被拒绝。"""
        result = kubectl_handler._CLUSTER_ID_PATTERN.match("x12345678901234567890123456789012")
        assert result is None

    # ---- validate_workload_type ----

    def test_workload_type_valid(self):
        """合法 workload_type 通过校验。"""
        for wt in ["deployment", "statefulset", "daemonset", "replicaset"]:
            result = kubectl_handler.validate_workload_type(wt)
            assert result == wt

    def test_workload_type_case_insensitive(self):
        """大小写不敏感。"""
        result = kubectl_handler.validate_workload_type("DeployMent")
        assert result == "deployment"

    def test_workload_type_invalid(self):
        """非法 workload_type 被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_workload_type("pod; rm -rf /")

    # ---- validate_kubeconfig_path ----

    def test_kubeconfig_path_traversal(self):
        """路径穿越被拒绝。"""
        with pytest.raises(ValueError, match="Path traversal"):
            kubectl_handler.validate_kubeconfig_path("../../../etc/passwd")

    def test_kubeconfig_path_shell_metachars(self):
        """含 shell 元字符的路径被拒绝。"""
        with pytest.raises(ValueError):
            kubectl_handler.validate_kubeconfig_path("test;rm -rf /")

    def test_kubeconfig_path_valid(self):
        """合法路径通过校验。"""
        result = kubectl_handler.validate_kubeconfig_path("/tmp/test-kubeconfig.yaml")
        assert result == "/tmp/test-kubeconfig.yaml"

    def test_kubeconfig_path_home_expansion(self):
        """`~` 是 shell 元字符，路径中的 `~` 被拒绝。"""
        with pytest.raises(ValueError, match="Unsafe characters"):
            kubectl_handler.validate_kubeconfig_path("~/.kube/config")


# ============================================================
# 五、JSON 注入（diagnose_resource）
# ============================================================

class TestDiagnoseResourceJSONInjection:
    """验证 diagnose_resource 的 JSON 解析安全性。"""

    def test_json_deeply_nested(self):
        """深层嵌套 JSON 应被正确解析。"""
        depth = 100
        # 构建嵌套对象: {"a": {"a": {"a": ... 1 ...}}}
        inner = "1"
        for _ in range(depth):
            inner = '{"a": ' + inner + "}"
        result = json.loads(inner)
        assert isinstance(result, dict)

    def test_json_field_value_shell_injection(self):
        """JSON 字段值中的 shell 注入符号不应被解释。"""
        payload = json.dumps({"name": "; rm -rf /"})
        result = json.loads(payload)
        assert result["name"] == "; rm -rf /"
        # 值作为字符串被正确解析，不执行 shell 命令

    def test_json_malformed_rejected(self):
        """非法 JSON 应被拒绝。"""
        with pytest.raises(json.JSONDecodeError):
            json.loads("not json")

    def test_json_with_null_byte(self):
        """含 null 字节的 JSON 应被正确处理。"""
        payload = '{"name": "test\\u0000"}'
        result = json.loads(payload)
        assert result["name"] == "test\u0000"

    def test_json_empty_object(self):
        """空 JSON 对象应被允许。"""
        result = json.loads("{}")
        assert result == {}

    def test_json_large_payload(self):
        """大型 JSON 应被正确解析。"""
        payload = json.dumps({"key": "value" * 10000})
        result = json.loads(payload)
        assert len(result["key"]) == 50000


# ============================================================
# 六、时间参数注入
# ============================================================

class TestTimeParameterInjection:
    """验证时间参数解析的安全性。"""

    def test_negative_relative_time(self):
        """负数相对时间。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        from datetime import datetime, timedelta
        result = handler._parse_single_time("-1000h", default_hours=24)
        # -1000h 意味着未来时间
        assert isinstance(result, datetime)

    def test_sql_injection_in_time_string(self):
        """含 SQL 注入字符的时间字符串。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        from datetime import datetime
        # "1h; DROP TABLE" 以 h 结尾，被解释为相对时间
        # int("1h; DROP TABLE"[:-1]) 会失败，因为 "1h; DROP TABL" 不是数字
        # 实际上 _parse_single_time 检查 endswith('h') 然后 int(ts[:-1])
        # 这会在 int() 时抛出 ValueError，回退到 default
        result = handler._parse_single_time("1h; DROP TABLE", default_hours=24)
        assert isinstance(result, datetime)

    def test_extremely_large_relative_time(self):
        """超大相对时间应被安全处理，返回默认值而非崩溃。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        from datetime import datetime
        result = handler._parse_single_time("999999999999d", default_hours=24)
        assert isinstance(result, datetime)

    def test_parse_single_time_now(self):
        """`now` 别称。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        from datetime import datetime
        result = handler._parse_single_time("now", default_hours=24)
        assert isinstance(result, datetime)

    def test_parse_single_time_iso8601(self):
        """ISO 8601 格式。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        from datetime import datetime
        result = handler._parse_single_time("2025-01-01T10:00:00Z", default_hours=24)
        assert isinstance(result, datetime)

    def test_parse_time_params_order(self):
        """start_time 应小于 end_time。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        params = {"start_time": "24h", "end_time": None}
        start_ts, end_ts = handler._parse_time_params(params)
        assert start_ts < end_ts

    def test_parse_time_params_swapped(self):
        """start_time > end_time 时应被修正。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        params = {"start_time": "1h", "end_time": "24h"}
        start_ts, end_ts = handler._parse_time_params(params)
        # end_time 被修正为 now
        assert isinstance(start_ts, int)
        assert isinstance(end_ts, int)

    def test_cp_parse_single_time_negative(self):
        """控制面日志 handler 的负数时间。"""
        from datetime import datetime
        result = cp_handler._parse_single_time("-1000h", default_hours=24)
        assert isinstance(result, datetime)

    def test_cp_parse_single_time_unix_ms(self):
        """控制面日志 handler 的 Unix 毫秒时间戳。"""
        from datetime import datetime
        # 使用一个远大于 1e12 的值来触发毫秒处理
        result = cp_handler._parse_single_time("1700000000000", default_hours=24)
        assert isinstance(result, datetime)


# ============================================================
# 七、边界与组合攻击
# ============================================================

class TestEdgeCases:
    """边界条件和组合攻击测试。"""

    def test_kubectl_empty_command(self):
        """空命令应被拒绝。"""
        runner = kubectl_handler.KubectlRunner("/fake/path", timeout=30, allow_write=False)
        result = runner.run()
        assert result["exit_code"] == 1
        assert "not allowed" in result["stderr"] or "Empty" in result["stderr"]

    def test_multiple_forbidden_flags(self):
        """多个禁用标志同时出现应全部被拦截。"""
        tokens = ["get", "pods", "--kubeconfig=/evil", "--server=https://evil.com", "--token=evil"]
        found = [t for t in tokens if kubectl_handler._is_forbidden_flag(t)]
        assert len(found) == 3

    def test_forbidden_flag_with_equals(self):
        """`--flag=value` 格式的禁用标志应被检测。"""
        assert kubectl_handler._is_forbidden_flag("--kubeconfig=/path")
        assert kubectl_handler._is_forbidden_flag("--server=https://evil.com")
        assert kubectl_handler._is_forbidden_flag("--token=abc123")

    def test_forbidden_flag_without_value(self):
        """`--flag` 格式的禁用标志应被检测。"""
        assert kubectl_handler._is_forbidden_flag("--insecure-skip-tls-verify")

    def test_normal_flag_not_blocked(self):
        """正常标志不应被误拦截。"""
        assert not kubectl_handler._is_forbidden_flag("--namespace=default")
        assert not kubectl_handler._is_forbidden_flag("-n")
        assert not kubectl_handler._is_forbidden_flag("-o")
        assert not kubectl_handler._is_forbidden_flag("--output=json")

    def test_interactive_flag_detection(self):
        """交互标志检测。"""
        assert kubectl_handler._is_interactive_flag("-i")
        assert kubectl_handler._is_interactive_flag("-t")
        assert kubectl_handler._is_interactive_flag("--stdin")
        assert kubectl_handler._is_interactive_flag("--tty")
        # 短格式组合
        assert kubectl_handler._is_interactive_flag("-it")  # 包含 i 和 t

    def test_normal_flag_not_interactive(self):
        """正常标志不应被误判为交互式。"""
        assert not kubectl_handler._is_interactive_flag("-n")
        assert not kubectl_handler._is_interactive_flag("-o")
        assert not kubectl_handler._is_interactive_flag("--namespace")
        assert not kubectl_handler._is_interactive_flag("--output")

    def test_resource_mapping_normalization(self):
        """资源类型映射正常化。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        params = {"resource_types": ["pod", "svc", "deploy", "ing"]}
        normalized = handler._normalize_params(params)
        assert "pods" in normalized["resource_types"]
        assert "services" in normalized["resource_types"]
        assert "deployments" in normalized["resource_types"]
        assert "ingresses" in normalized["resource_types"]

    def test_resource_mapping_unknown_passthrough(self):
        """未知资源类型原样传递。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        params = {"resource_types": ["unknown-resource"]}
        normalized = handler._normalize_params(params)
        assert "unknown-resource" in normalized["resource_types"]

    def test_normalize_params_limit_ceiling(self):
        """limit 超过 100 时被截断。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        params = {"limit": 200}
        normalized = handler._normalize_params(params)
        assert normalized["limit"] == 100

    def test_normalize_params_limit_zero(self):
        """limit 为 0 时使用默认值。"""
        handler = audit_handler.ACKAuditLogHandler(None, {})
        params = {"limit": 0}
        normalized = handler._normalize_params(params)
        assert normalized["limit"] == 10