import os
import re
import shlex

_K8S_NAME_RE = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$')

_SHELL_METACHARS = frozenset(';&|`$\\\n<>(){}[]\'"!*?#~')

_READONLY_COMMANDS = frozenset({
    "api-resources",
    "api-versions",
    "cluster-info",
    "describe",
    "diff",
    "events",
    "explain",
    "get",
    "kustomize",
    "logs",
    "options",
    "top",
    "version",
})

_FORBIDDEN_KUBECTL_FLAGS = frozenset({
    '--kubeconfig',
    '--server',
    '--token',
    '--client-certificate',
    '--client-key',
    '--as',
    '--as-group',
    '--user',
    '--cluster',
    '--context',
    '--insecure-skip-tls-verify',
    '--raw',
})

_INTERACTIVE_FLAGS = frozenset({'-i', '-t', '--stdin', '--tty'})

_WORKLOAD_TYPES = frozenset({'deployment', 'statefulset', 'daemonset', 'replicaset'})

_FORBIDDEN_FLAGS_NORMALIZED = frozenset(f.lstrip('-') for f in _FORBIDDEN_KUBECTL_FLAGS)


def validate_kubernetes_name(name: str, context: str = "resource") -> str:
    if not name or not _K8S_NAME_RE.match(name):
        raise ValueError(f"Invalid {context} name: {name}")
    return name


def validate_shell_safe_param(value: str, context: str = "parameter") -> str:
    if not value:
        raise ValueError(f"Empty {context}")
    if any(c in _SHELL_METACHARS for c in value):
        raise ValueError(f"Unsafe characters in {context}: {value}")
    return value


def validate_kubeconfig_path(path: str) -> str:
    if not path:
        raise ValueError("Empty kubeconfig path")
    if any(c in _SHELL_METACHARS for c in path):
        raise ValueError(f"Unsafe characters in kubeconfig path: {path}")
    resolved = os.path.abspath(os.path.expanduser(path))
    norm = os.path.normpath(resolved)
    if '..' in norm.split(os.sep):
        raise ValueError(f"Path traversal detected in kubeconfig path: {path}")
    return resolved


def validate_workload_type(workload_type: str) -> str:
    normalized = workload_type.lower()
    if normalized not in _WORKLOAD_TYPES:
        raise ValueError(f"Invalid workload type: {workload_type}. Must be one of: {', '.join(sorted(_WORKLOAD_TYPES))}")
    return normalized


def _is_forbidden_flag(token: str) -> bool:
    if not token.startswith('-'):
        return False
    normalized = token.lstrip('-').split('=', 1)[0]
    return normalized in _FORBIDDEN_FLAGS_NORMALIZED


def _is_interactive_flag(token: str) -> bool:
    if token in _INTERACTIVE_FLAGS:
        return True
    if token.startswith('-') and not token.startswith('--') and 'i' in token and 't' in token:
        return True
    return False


def is_write_command(command: str) -> tuple[bool, str | None]:
    try:
        tokens = shlex.split(command.strip())
    except ValueError:
        return True, "Invalid command syntax"

    if not tokens:
        return True, "Empty command not allowed"

    if ';' in command or '|' in command or '&' in command:
        return True, "Command chaining not allowed"

    forbidden_flags = [t for t in tokens if _is_forbidden_flag(t)]
    if forbidden_flags:
        return True, f"Forbidden flag(s) not allowed in read-only mode: {', '.join(forbidden_flags)}"

    main_command = tokens[0]
    if main_command not in _READONLY_COMMANDS:
        return True, f"Write command '{main_command}' not allowed in read-only mode. Only read-only commands are permitted: {', '.join(sorted(_READONLY_COMMANDS))}"

    return False, None


def is_streaming_command(command: str) -> tuple[bool, str | None]:
    try:
        tokens = shlex.split(command.strip())
    except ValueError:
        return False, None

    if not tokens:
        return False, None

    if tokens[0] == "get" and any(t == "-w" or t == "--watch" or t.startswith("-w=") or t.startswith("--watch=") for t in tokens):
        return True, "watch"
    if tokens[0] == "logs" and ("-f" in tokens or "--follow" in tokens):
        return True, "logs"
    if tokens[0] == "attach":
        return True, "attach"

    return False, None


def is_interactive_command(command: str) -> tuple[bool, str | None]:
    try:
        tokens = shlex.split(command.strip())
    except ValueError:
        return True, "Invalid command syntax"

    if not tokens:
        return False, None

    if tokens[0] == "port-forward":
        return True, "interactive mode not supported for kubectl port-forward, please use service types like NodePort or LoadBalancer"
    if tokens[0] == "edit":
        return True, "interactive mode not supported for kubectl edit, please use 'kubectl get -o yaml', 'kubectl patch', or 'kubectl apply'"

    has_interactive = any(_is_interactive_flag(t) for t in tokens)
    if has_interactive:
        return True, "interactive mode not supported (commands with -it/-i/-t/--stdin/--tty flags), please use non-interactive commands"

    return False, None


def escape_sls_query_value(value: str) -> str:
    escaped = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'
