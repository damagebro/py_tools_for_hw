#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from importlib.util import find_spec
from pathlib import Path
import tomllib

from tool_registry import (
    DEFAULT_GROUP,
    REPOSITORY_MAP,
    TOOL_MAP,
    TOOL_SPECS,
    RepositorySpec,
    ToolSpec,
)
import tool_registry


class HwToolError(Exception):
    pass


TOOL_KIND_SCRIPT = "script"
TOOL_KIND_HUB = "hub"
TOOL_SOURCE_GIT = "git"
DEFAULT_DOC_LINES = 48
REPOSITORY_ROOT_ENV = "HW_TOOL_REPOSITORY_ROOT"
HUB_CHAIN_ENV = "HW_TOOL_HUB_CHAIN"
FEDERATION_SCHEMA_VERSION = 1


class FederatedTool:
    def __init__(
        self,
        name: str,
        qualified_name: str,
        route: tuple[str, ...],
        description: str,
        status: str,
        detail: str | None,
        doc_url: str | None,
    ) -> None:
        self.name = name
        self.qualified_name = qualified_name
        self.route = route
        self.description = description
        self.status = status
        self.detail = detail
        self.doc_url = doc_url


def tool_root() -> Path:
    override = os.environ.get("HW_TOOL_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def hub_identifier() -> str:
    configured = getattr(getattr(tool_registry, "HUB_SPEC", None), "identifier", None)
    if isinstance(configured, str) and configured:
        return configured
    configured = getattr(tool_registry, "HUB_ID", None)
    if isinstance(configured, str) and configured:
        return configured
    return tool_root().name


def hub_chain() -> tuple[str, ...]:
    value = os.environ.get(HUB_CHAIN_ENV, "")
    return tuple(item for item in value.split(":") if item)


def check_hub_cycle() -> None:
    chain = hub_chain()
    identifier = hub_identifier()
    if identifier in chain:
        route = " -> ".join((*chain, identifier))
        raise HwToolError(f"hub integration cycle detected: {route}")


def repository_spec(tool: ToolSpec) -> RepositorySpec | None:
    if not tool.repository_name:
        return None
    repository = REPOSITORY_MAP.get(tool.repository_name)
    if repository is None:
        raise HwToolError(
            f"tool '{tool.name}' references unknown repository: {tool.repository_name}"
        )
    return repository


def repository_workspace_path(repository: RepositorySpec) -> Path | None:
    if not repository.workspace:
        return None
    path = (tool_root() / repository.workspace).resolve()
    return path if path.is_dir() else None


def repository_checkout_path(repository: RepositorySpec) -> Path:
    repository_root = os.environ.get(REPOSITORY_ROOT_ENV)
    if repository_root:
        return (Path(repository_root).expanduser().resolve() / repository.name).resolve()
    return (tool_root() / repository.checkout).resolve()


def repository_roots(tool: ToolSpec) -> list[Path]:
    repository = repository_spec(tool)
    if repository is None:
        return [tool_root()]

    roots: list[Path] = []
    workspace = repository_workspace_path(repository)
    if workspace is not None:
        roots.append(workspace)
    checkout = repository_checkout_path(repository)
    if checkout not in roots:
        roots.append(checkout)
    return roots


def repository_path(tool: ToolSpec, relative_path: str, description: str) -> Path:
    for root in repository_roots(tool):
        path = root / relative_path
        if path.is_file():
            return path
    locations = ", ".join(str(root / relative_path) for root in repository_roots(tool))
    raise HwToolError(f"{description} not found for '{tool.name}': {locations}")


def script_path(tool: ToolSpec) -> Path:
    return repository_path(tool, tool.script, "script")


def readme_path(tool: ToolSpec) -> Path:
    if not tool.readme:
        raise HwToolError(f"tool '{tool.name}' does not register a README")
    return repository_path(tool, tool.readme, "README")


def print_tool_document(tool: ToolSpec, start_line: int, all_lines: bool) -> None:
    lines = readme_path(tool).read_text(encoding="utf-8").splitlines(keepends=True)
    start_index = start_line - 1
    if start_index >= len(lines):
        raise HwToolError(
            f"README for '{tool.name}' has {len(lines)} lines; "
            f"cannot start at line {start_line}"
        )
    visible_lines = lines[start_index:]
    if not all_lines:
        visible_lines = visible_lines[:DEFAULT_DOC_LINES]

    sys.stdout.write("".join(visible_lines))
    if visible_lines and not visible_lines[-1].endswith("\n"):
        sys.stdout.write("\n")
    end_line = start_index + len(visible_lines)
    if not all_lines and end_line < len(lines):
        print(
            f"... truncated at lines {start_line}-{end_line} of {len(lines)}; "
            f"use: hw_tool doc {tool.name} --all"
        )


def tool_home_path(tool: ToolSpec) -> Path | None:
    if tool.kind == TOOL_KIND_SCRIPT:
        return None
    if tool.kind != TOOL_KIND_HUB:
        raise HwToolError(f"unsupported tool kind for '{tool.name}': {tool.kind}")
    if not tool.tool_home:
        raise HwToolError(f"hub '{tool.name}' requires tool_home")

    return (tool_root() / tool.tool_home).resolve()


def checkout_path(tool: ToolSpec) -> Path | None:
    repository = repository_spec(tool)
    if repository is not None:
        return repository_checkout_path(repository)
    if tool.kind == TOOL_KIND_HUB:
        return tool_home_path(tool)
    if not tool.checkout:
        return None
    return (tool_root() / tool.checkout).resolve()


def child_tool_root(tool: ToolSpec) -> Path | None:
    path = tool_home_path(tool)
    if path is None:
        return None
    if not path.is_dir():
        raise HwToolError(f"tool home not found for '{tool.name}': {path}")
    return path


def validate_tool(tool: ToolSpec) -> None:
    script_path(tool)
    child_tool_root(tool)


def print_usage() -> None:
    print("usage: hw_tool <list|help|doc|doctor|verify|test|sync|run|group> [args ...]")
    print("       hw_tool --version")
    print("       hw_tool list [--tools|--recursive] [--json]")
    print("       hw_tool help <tool>")
    print("       hw_tool doc <tool> [--all|--from <line>]")
    print("       hw_tool doctor")
    print("       hw_tool verify [group|tool|--all]")
    print("       hw_tool test [group|tool|--all] [--unit|--smoke|--all]")
    print("       hw_tool sync <group>|--all [--dry-run] [--shallow]")
    print("       hw_tool run <qualified_tool> [tool arguments]")
    print("       hw_tool <group> [group arguments]")


def git_version(path: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    version = completed.stdout.strip()
    return version or "unknown"


def git_commit_date(path: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "log", "-1", "--format=%cI"],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    timestamp = completed.stdout.strip()
    if len(timestamp) < 16 or timestamp[10] != "T":
        return "unknown"
    return f"{timestamp[:10]} {timestamp[11:16]}"


def release_version(path: Path) -> tuple[str, str] | None:
    metadata_path = path / "release_info.toml"
    try:
        metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    release = metadata.get("release")
    if not isinstance(release, dict):
        return None
    version = release.get("version")
    built_at = release.get("built_at")
    if not isinstance(version, str) or not isinstance(built_at, str):
        return None
    return version, built_at


def print_version() -> None:
    version = git_version(tool_root())
    commit_date = git_commit_date(tool_root())
    if version == "unknown":
        release = release_version(tool_root())
        if release is not None:
            version, commit_date = release
    print(
        f"{tool_root().name}: {version} ({commit_date})"
    )


def print_doctor_report() -> int:
    print(f"{tool_root().name} doctor", flush=True)
    print(f"[ok]   python: {sys.executable} ({sys.version.split()[0]})")

    try:
        completed = subprocess.run(
            ["git", "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        completed = None
    if completed is None or completed.returncode != 0:
        print("[fail] git: unavailable")
        failed = True
    else:
        print(f"[ok]   git: {completed.stdout.strip()}")
        failed = False

    launcher = shutil.which("hw_tool") or shutil.which("hw_tool.cmd")
    if launcher:
        print(f"[ok]   launcher: {launcher}")
    else:
        print("[warn] launcher: hw_tool is not on PATH")

    for tool in TOOL_SPECS:
        status, detail = git_state(tool)
        suffix = f" ({detail})" if detail else ""
        if status == "ready":
            print(f"[ok]   {tool.name}: ready{suffix}")
            continue
        if status == "not-synced":
            print(f"[warn] {tool.name}: not synced; run: hw_tool sync {tool.name}")
            continue
        print(f"[fail] {tool.name}: {status}{suffix}")
        failed = True

    packages = sorted(
        {package for tool in TOOL_SPECS for package in tool.doctor_packages}
    )
    for package in packages:
        if find_spec(package) is None:
            print(f"[warn] python package: {package} is not installed")
        else:
            print(f"[ok]   python package: {package}")
    return 1 if failed else 0


def doctor() -> int:
    result = print_doctor_report()
    if DEFAULT_GROUP is None:
        return result

    for group in TOOL_SPECS:
        if group.kind != TOOL_KIND_HUB:
            continue
        status, _ = git_state(group)
        if status != "ready":
            result = 1
            continue
        print(f"\n[{group.name}]", flush=True)
        if run_tool(group, ["doctor"]) != 0:
            result = 1
    return result


def tool_source_root(tool: ToolSpec) -> Path:
    for root in repository_roots(tool):
        if (root / tool.script).is_file():
            return root
    raise HwToolError(f"source root not found for '{tool.name}'")


def run_checked_command(
    tool: ToolSpec,
    args: list[str],
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-B", str(script_path(tool)), *args]
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise HwToolError(f"failed to run '{tool.name}': {exc}") from exc


def print_command_failure(completed: subprocess.CompletedProcess[str]) -> None:
    output = completed.stderr.strip() or completed.stdout.strip()
    if output:
        print(output, file=sys.stderr)


def verify_tool_contract(tool: ToolSpec) -> bool:
    if not tool.contract_enabled:
        print(f"[skip] {tool.name}: externally maintained")
        return True

    try:
        source_root = tool_source_root(tool)
        if not tool.repository_name or repository_spec(tool) is None:
            raise HwToolError("missing repository_name")
        if not tool.doc_url:
            raise HwToolError("missing doc_url")
        if not tool.readme:
            raise HwToolError("missing README registration")
        readme_path(tool)
        if not tool.example:
            raise HwToolError("missing minimum example registration")
        example = source_root / tool.example
        if not example.exists():
            raise HwToolError(f"minimum example not found: {example}")
        if not tool.smoke_args or not (tool.smoke_outputs or getattr(tool, "smoke_stdout", ())):
            raise HwToolError("missing smoke test registration")
        if not tool.unit_tests:
            raise HwToolError("missing unit test registration")
    except HwToolError as exc:
        print(f"[fail] {tool.name}: {exc}", file=sys.stderr)
        return False

    completed = run_checked_command(tool, ["--help"], source_root)
    if completed.returncode != 0:
        print(
            f"[fail] {tool.name}: --help returned {completed.returncode}",
            file=sys.stderr,
        )
        print_command_failure(completed)
        return False

    print(f"[ok]   {tool.name}: contract")
    return True


def local_contract_tools(target: str) -> list[ToolSpec]:
    if target == "--all":
        return list(TOOL_SPECS)
    return [get_tool(target)]


def verify_local_tools(args: list[str]) -> int:
    if len(args) > 1:
        raise HwToolError("verify accepts one tool name or --all")
    target = args[0] if args else "--all"
    failed = False
    for tool in local_contract_tools(target):
        if not verify_tool_contract(tool):
            failed = True
    return 1 if failed else 0


def verify(args: list[str]) -> int:
    if DEFAULT_GROUP is None:
        return verify_local_tools(args)
    if len(args) > 1:
        raise HwToolError("verify accepts one group name or --all")
    selected = args[0] if args else "--all"
    groups = (
        [tool for tool in TOOL_SPECS if tool.kind == TOOL_KIND_HUB]
        if selected == "--all"
        else [get_tool(selected)]
    )
    failed = False
    for group in groups:
        if group.kind != TOOL_KIND_HUB:
            raise HwToolError(f"'{group.name}' is not a group")
        if run_tool(group, ["verify"]) != 0:
            failed = True
    return 1 if failed else 0


def run_unit_tests(tool: ToolSpec, source_root: Path) -> bool:
    cwd = source_root / tool.unit_cwd if tool.unit_cwd else source_root
    if not cwd.is_dir():
        print(f"[fail] {tool.name}: unit test cwd not found: {cwd}", file=sys.stderr)
        return False
    for relative_path in tool.unit_tests:
        path = source_root / relative_path
        if not path.is_file():
            print(f"[fail] {tool.name}: unit test not found: {path}", file=sys.stderr)
            return False
        completed = subprocess.run(
            [sys.executable, "-B", str(path)],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            print(f"[fail] {tool.name}: unit test failed: {path.name}", file=sys.stderr)
            print_command_failure(completed)
            return False
    print(f"[ok]   {tool.name}: unit")
    return True


def run_smoke_test(tool: ToolSpec, source_root: Path) -> bool:
    work_root = source_root / ".hw_tool_smoke"
    workdir = work_root / uuid.uuid4().hex
    output = workdir / "out"
    try:
        workdir.mkdir(parents=True)
        output.mkdir()
        example = source_root / (tool.example or "")
        args = [
            value.format(example=str(example), output=str(output))
            for value in tool.smoke_args
        ]
        completed = run_checked_command(tool, args, source_root)
        if completed.returncode != 0:
            print(f"[fail] {tool.name}: smoke returned {completed.returncode}", file=sys.stderr)
            print_command_failure(completed)
            return False
        missing = [
            relative_path
            for relative_path in tool.smoke_outputs
            if not (output / relative_path).is_file()
        ]
        if missing:
            print(
                f"[fail] {tool.name}: smoke missing output: {', '.join(missing)}",
                file=sys.stderr,
            )
            return False
        missing_stdout = [
            text for text in getattr(tool, "smoke_stdout", ()) if text not in completed.stdout
        ]
        if missing_stdout:
            print(
                f"[fail] {tool.name}: smoke missing stdout: {', '.join(missing_stdout)}",
                file=sys.stderr,
            )
            return False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        try:
            work_root.rmdir()
        except OSError:
            pass
    print(f"[ok]   {tool.name}: smoke")
    return True


def parse_test_args(args: list[str]) -> tuple[str, str]:
    target = "--all"
    mode = "all"
    for arg in args:
        if arg in {"--unit", "--smoke", "--all"}:
            new_mode = arg[2:] if arg != "--all" else "all"
            if mode != "all" and new_mode != mode:
                raise HwToolError("test accepts one of --unit, --smoke, or --all")
            mode = new_mode
            continue
        if target != "--all":
            raise HwToolError("test accepts one tool name")
        target = arg
    return target, mode


def test_local_tools(args: list[str]) -> int:
    target, mode = parse_test_args(args)
    failed = False
    for tool in local_contract_tools(target):
        if not tool.contract_enabled:
            print(f"[skip] {tool.name}: externally maintained")
            continue
        if not verify_tool_contract(tool):
            failed = True
            continue
        source_root = tool_source_root(tool)
        if mode in {"unit", "all"} and not run_unit_tests(tool, source_root):
            failed = True
        if mode in {"smoke", "all"} and not run_smoke_test(tool, source_root):
            failed = True
    return 1 if failed else 0


def test(args: list[str]) -> int:
    if DEFAULT_GROUP is None:
        return test_local_tools(args)
    if not args or args == ["--all"]:
        groups = [tool for tool in TOOL_SPECS if tool.kind == TOOL_KIND_HUB]
        child_args = ["test", "--all"]
    else:
        group = get_tool(args[0])
        if group.kind != TOOL_KIND_HUB:
            raise HwToolError(f"'{group.name}' is not a group")
        groups = [group]
        child_args = ["test", *args[1:]]

    failed = False
    for group in groups:
        if run_tool(group, child_args) != 0:
            failed = True
    return 1 if failed else 0


def git_state(tool: ToolSpec) -> tuple[str, str]:
    repository = repository_spec(tool)
    is_git_source = repository is not None or tool.source == TOOL_SOURCE_GIT
    if repository is not None:
        workspace = repository_workspace_path(repository)
        if workspace is not None and (workspace / tool.script).is_file():
            try:
                commit = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=workspace,
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except OSError:
                return "ready", f"workspace {workspace}"
            detail = commit.stdout.strip()
            suffix = f" {detail}" if commit.returncode == 0 and detail else ""
            return "ready", f"workspace{suffix}"

    path = checkout_path(tool)
    if path is None:
        return "ready", ""
    if is_git_source and not path.exists():
        return "not-synced", ""
    try:
        validate_tool(tool)
    except HwToolError:
        return "missing", ""
    if not is_git_source:
        return "ready", ""

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "invalid", "git unavailable"
    if commit.returncode != 0 or dirty.returncode != 0:
        return "invalid", "not a git checkout"

    detail = commit.stdout.strip()
    if dirty.stdout.strip():
        detail = f"{detail} dirty"
    return "ready", detail


def tool_payload(tool: ToolSpec, status: str, detail: str) -> dict[str, str | None]:
    return {
        "name": tool.name,
        "kind": tool.kind,
        "description": tool.description,
        "status": status,
        "detail": detail or None,
        "doc_url": tool.doc_url,
    }


def print_tool_list(json_mode: bool = False) -> None:
    entries = [tool_payload(tool, *git_state(tool)) for tool in TOOL_SPECS]
    if json_mode:
        print(
            json.dumps(
                {
                    "schema_version": FEDERATION_SCHEMA_VERSION,
                    "hub": {"id": hub_identifier()},
                    "tools": entries,
                },
                ensure_ascii=False,
            )
        )
        return

    name_width = max(len(tool.name) for tool in TOOL_SPECS)
    print("available tools:")
    for tool, entry in zip(TOOL_SPECS, entries):
        status = entry["status"] or "unknown"
        detail = entry["detail"] or ""
        suffix = f"  {detail}" if detail else ""
        print(f"  {tool.name:<{name_width}}  {status:<11}  {tool.description}{suffix}")


def get_tool(name: str) -> ToolSpec:
    tool = TOOL_MAP.get(name)
    if tool is None:
        raise HwToolError(f"unknown tool: {name}")
    return tool


def tool_environment(tool: ToolSpec) -> dict[str, str]:
    environment = os.environ.copy()
    child_root = child_tool_root(tool)
    if child_root is not None:
        environment["HW_TOOL_HOME"] = str(child_root)
        environment[REPOSITORY_ROOT_ENV] = str((tool_root() / "repository").resolve())
        environment[HUB_CHAIN_ENV] = ":".join((*hub_chain(), hub_identifier()))
    return environment


def run_tool(tool: ToolSpec, args: list[str]) -> int:
    validate_tool(tool)
    command = [sys.executable, "-B", str(script_path(tool)), *args]
    try:
        completed = subprocess.run(
            command,
            cwd=Path.cwd(),
            env=tool_environment(tool),
            check=False,
        )
    except OSError as exc:
        raise HwToolError(f"failed to run '{tool.name}': {exc}") from exc
    return completed.returncode


def group_federated_tools(group: ToolSpec) -> list[FederatedTool]:
    validate_tool(group)
    command = [
        sys.executable,
        "-B",
        str(script_path(group)),
        "list",
        "--recursive",
        "--json",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=Path.cwd(),
            env=tool_environment(group),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise HwToolError(f"failed to query group '{group.name}': {exc}") from exc
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip()
        raise HwToolError(f"failed to query group '{group.name}': {error}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HwToolError(f"group '{group.name}' returned invalid JSON") from exc
    schema_version = payload.get("schema_version") if isinstance(payload, dict) else None
    entries = payload.get("tools") if isinstance(payload, dict) else None
    if schema_version != FEDERATION_SCHEMA_VERSION:
        raise HwToolError(
            f"group '{group.name}' does not support federation schema "
            f"{FEDERATION_SCHEMA_VERSION}"
        )
    if not isinstance(entries, list):
        raise HwToolError(f"group '{group.name}' JSON is missing tools")

    tools: list[FederatedTool] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        qualified_name = entry.get("qualified_name")
        route = entry.get("route")
        description = entry.get("description", "")
        status = entry.get("status", "unknown")
        detail = entry.get("detail")
        doc_url = entry.get("doc_url")
        if not (
            isinstance(name, str)
            and name
            and isinstance(qualified_name, str)
            and qualified_name
            and isinstance(route, list)
            and route
            and all(isinstance(item, str) and item for item in route)
            and isinstance(description, str)
            and isinstance(status, str)
            and (detail is None or isinstance(detail, str))
            and (doc_url is None or isinstance(doc_url, str))
        ):
            raise HwToolError(f"group '{group.name}' returned an invalid tool entry")
        tools.append(
            FederatedTool(
                name=name,
                qualified_name=f"{group.name}.{qualified_name}",
                route=(group.name, *route),
                description=description,
                status=status,
                detail=detail,
                doc_url=doc_url,
            )
        )
    return tools


def recursive_tool_entries() -> list[FederatedTool]:
    entries: list[FederatedTool] = []
    for tool in TOOL_SPECS:
        status, detail = git_state(tool)
        if tool.kind == TOOL_KIND_SCRIPT:
            entries.append(
                FederatedTool(
                    name=tool.name,
                    qualified_name=tool.name,
                    route=(tool.name,),
                    description=tool.description,
                    status=status,
                    detail=detail or None,
                    doc_url=tool.doc_url,
                )
            )
            continue
        if tool.kind != TOOL_KIND_HUB or status != "ready":
            continue
        entries.extend(group_federated_tools(tool))
    return entries


def global_tool_index() -> dict[str, list[FederatedTool]]:
    index: dict[str, list[FederatedTool]] = {}
    for tool in recursive_tool_entries():
        if tool.status == "ready":
            index.setdefault(tool.name, []).append(tool)
    return index


def resolve_implicit_tool(name: str) -> FederatedTool:
    if DEFAULT_GROUP is None:
        raise HwToolError(f"unknown tool: {name}")
    candidates = global_tool_index().get(name, [])
    if not candidates:
        raise HwToolError(f"unknown tool: {name}")
    if len(candidates) == 1:
        return candidates[0]

    for candidate in candidates:
        if candidate.route[0] == DEFAULT_GROUP:
            return candidate
    group_names = ", ".join(candidate.qualified_name for candidate in candidates)
    raise HwToolError(
        f"tool '{name}' exists in: {group_names}; use a qualified tool name"
    )


def print_global_tool_list() -> None:
    index = global_tool_index()
    if not index:
        print("no ready group tools")
        return
    name_width = max(len(name) for name in index)
    print("global tools:")
    for name in sorted(index):
        candidates = index[name]
        routes = ", ".join(candidate.qualified_name for candidate in candidates)
        status = "conflict" if len(candidates) > 1 else "unique"
        default = " default" if any(
            candidate.route[0] == DEFAULT_GROUP for candidate in candidates
        ) else ""
        print(f"  {name:<{name_width}}  {status:<8}  {routes}{default}")


def print_recursive_tool_list(json_mode: bool = False) -> None:
    entries = recursive_tool_entries()
    if json_mode:
        payload = {
            "schema_version": FEDERATION_SCHEMA_VERSION,
            "hub": {"id": hub_identifier()},
            "tools": [
                {
                    "name": entry.name,
                    "qualified_name": entry.qualified_name,
                    "route": list(entry.route),
                    "description": entry.description,
                    "status": entry.status,
                    "detail": entry.detail,
                    "doc_url": entry.doc_url,
                }
                for entry in entries
            ],
        }
        print(json.dumps(payload, ensure_ascii=False))
        return

    if not entries:
        print("no ready federated tools")
        return
    name_width = max(len(entry.qualified_name) for entry in entries)
    print("federated tools:")
    for entry in sorted(entries, key=lambda item: item.qualified_name):
        detail = f"  {entry.detail}" if entry.detail else ""
        print(
            f"  {entry.qualified_name:<{name_width}}  {entry.status:<11}  "
            f"{entry.description}{detail}"
        )


def resolve_qualified_tool(name: str) -> FederatedTool:
    for tool in recursive_tool_entries():
        if tool.qualified_name == name:
            return tool
    raise HwToolError(f"unknown qualified tool: {name}")


def run_federated_tool(tool: FederatedTool, args: list[str]) -> int:
    first_hop = get_tool(tool.route[0])
    if first_hop.kind != TOOL_KIND_HUB:
        if len(tool.route) != 1:
            raise HwToolError(f"invalid direct route for '{tool.qualified_name}'")
        return run_tool(first_hop, args)
    return run_tool(first_hop, [*tool.route[1:], *args])


def run_federated_command(
    tool: FederatedTool,
    command: str,
    args: list[str],
) -> int:
    first_hop = get_tool(tool.route[0])
    if first_hop.kind != TOOL_KIND_HUB:
        if len(tool.route) != 1:
            raise HwToolError(f"invalid direct route for '{tool.qualified_name}'")
        if command == "help":
            return run_tool(first_hop, ["--help"])
        if command == "doc":
            return print_document([first_hop.name, *args])
        raise HwToolError(f"unsupported federated command: {command}")
    nested_name = ".".join(tool.route[1:])
    return run_tool(first_hop, [command, nested_name, *args])


def run_git(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise HwToolError(f"failed to run git: {exc}") from exc
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip()
        raise HwToolError(f"git command failed: {' '.join(command)}\n{error}")
    return completed


def sync_git_tool(
    tool: ToolSpec,
    dry_run: bool = False,
    shallow: bool = False,
) -> None:
    source = repository_spec(tool)
    if source is not None:
        workspace = repository_workspace_path(source)
        if workspace is not None and (workspace / tool.script).is_file():
            action = "would use" if dry_run else "using"
            print(f"[sync] {source.name}: {action} local workspace {workspace}")
            return
        sync_git_repository(source, dry_run, shallow)
        return

    if tool.source != TOOL_SOURCE_GIT:
        raise HwToolError(f"tool '{tool.name}' does not use a git source")
    if not tool.repository or not tool.branch:
        raise HwToolError(f"git tool '{tool.name}' has incomplete configuration")

    path = checkout_path(tool)
    if path is None:
        raise HwToolError(f"git tool '{tool.name}' requires a checkout path")

    if not path.exists():
        if dry_run:
            depth = " shallow" if shallow else ""
            print(
                f"[sync] {tool.name}: would clone{depth} {tool.repository} "
                f"-> {path} ({tool.branch})"
            )
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        clone_command = ["git", "clone"]
        if shallow:
            clone_command.extend(["--depth", "1"])
        clone_command.extend(
            [
                "--branch",
                tool.branch,
                "--single-branch",
                tool.repository,
                str(path),
            ]
        )
        run_git(
            clone_command,
            tool_root(),
        )
        depth = " shallow" if shallow else ""
        print(f"[sync] {tool.name}: cloned{depth} {tool.branch}")
        return

    if not (path / ".git").exists():
        raise HwToolError(f"tool '{tool.name}' path is not a git checkout: {path}")

    status = run_git(["git", "status", "--porcelain"], path)
    if status.stdout.strip():
        if dry_run:
            print(f"[sync] {tool.name}: would skip dirty checkout {path}")
            return
        raise HwToolError(f"tool '{tool.name}' has uncommitted changes: {path}")

    if dry_run:
        print(f"[sync] {tool.name}: would update {path} ({tool.branch})")
        return

    run_git(["git", "fetch", "origin", tool.branch], path)
    run_git(["git", "checkout", tool.branch], path)
    run_git(["git", "pull", "--ff-only", "origin", tool.branch], path)
    print(f"[sync] {tool.name}: updated {tool.branch}")


def sync_git_repository(
    repository: RepositorySpec,
    dry_run: bool = False,
    shallow: bool = False,
) -> None:
    path = repository_checkout_path(repository)
    if not path.exists():
        if dry_run:
            depth = " shallow" if shallow else ""
            print(
                f"[sync] {repository.name}: would clone{depth} {repository.repository} "
                f"-> {path} ({repository.branch})"
            )
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        clone_command = ["git", "clone"]
        if shallow:
            clone_command.extend(["--depth", "1"])
        clone_command.extend(
            [
                "--branch",
                repository.branch,
                "--single-branch",
                repository.repository,
                str(path),
            ]
        )
        run_git(
            clone_command,
            tool_root(),
        )
        depth = " shallow" if shallow else ""
        print(f"[sync] {repository.name}: cloned{depth} {repository.branch}")
        return

    if not (path / ".git").exists():
        raise HwToolError(
            f"repository '{repository.name}' path is not a git checkout: {path}"
        )

    status = run_git(["git", "status", "--porcelain"], path)
    if status.stdout.strip():
        if dry_run:
            print(f"[sync] {repository.name}: would skip dirty checkout {path}")
            return
        raise HwToolError(f"repository '{repository.name}' has uncommitted changes: {path}")

    if dry_run:
        print(f"[sync] {repository.name}: would update {path} ({repository.branch})")
        return

    run_git(["git", "fetch", "origin", repository.branch], path)
    run_git(["git", "checkout", repository.branch], path)
    run_git(["git", "pull", "--ff-only", "origin", repository.branch], path)
    print(f"[sync] {repository.name}: updated {repository.branch}")


def parse_sync_args(args: list[str]) -> tuple[str, bool, bool]:
    dry_run = False
    shallow = False
    names: list[str] = []
    for arg in args:
        if arg == "--dry-run":
            if dry_run:
                raise HwToolError("sync --dry-run may only be specified once")
            dry_run = True
            continue
        if arg == "--shallow":
            if shallow:
                raise HwToolError("sync --shallow may only be specified once")
            shallow = True
            continue
        names.append(arg)
    if len(names) != 1:
        raise HwToolError("sync requires one group name or --all")
    return names[0], dry_run, shallow


def sync_groups(args: list[str]) -> int:
    selected_name, dry_run, shallow = parse_sync_args(args)
    nested_groups: list[ToolSpec] = []
    if selected_name == "--all":
        tools = [
            tool
            for tool in TOOL_SPECS
            if tool.source == TOOL_SOURCE_GIT or tool.repository_name
        ]
        nested_groups = [tool for tool in TOOL_SPECS if tool.kind == TOOL_KIND_HUB]
    else:
        selected = get_tool(selected_name)
        if selected.kind == TOOL_KIND_HUB:
            tools = [selected] if selected.source == TOOL_SOURCE_GIT else []
            nested_groups = [selected]
        else:
            tools = [selected]

    failed = False
    synced_sources: set[str] = set()
    for tool in tools:
        source_key = tool.repository_name or tool.name
        if source_key in synced_sources:
            continue
        synced_sources.add(source_key)
        try:
            sync_git_tool(tool, dry_run, shallow)
        except HwToolError as exc:
            failed = True
            print(f"[hw_tool] error: {exc}", file=sys.stderr)

    for group in nested_groups:
        status, _ = git_state(group)
        if status != "ready":
            failed = True
            print(
                f"[hw_tool] error: group '{group.name}' is not ready for sync",
                file=sys.stderr,
            )
            continue
        child_args = ["sync", "--all"]
        if dry_run:
            child_args.append("--dry-run")
        if shallow:
            child_args.append("--shallow")
        result = run_tool(group, child_args)
        if result != 0:
            failed = True

    if not tools and not nested_groups:
        print("[sync] no git sources are registered")
    return 1 if failed else 0


def print_document(args: list[str]) -> int:
    if not args:
        raise HwToolError("doc requires one tool name")
    tool_name = args[0]
    start_line = 1
    all_lines = False
    index = 1
    while index < len(args):
        option = args[index]
        if option == "--all":
            all_lines = True
            index += 1
            continue
        if option == "--from":
            if index + 1 >= len(args):
                raise HwToolError("doc --from requires a positive line number")
            try:
                start_line = int(args[index + 1])
            except ValueError as exc:
                raise HwToolError("doc --from requires a positive line number") from exc
            if start_line < 1:
                raise HwToolError("doc --from requires a positive line number")
            index += 2
            continue
        raise HwToolError(f"unsupported doc option: {option}")
    try:
        tool = get_tool(tool_name)
    except HwToolError:
        if "." in tool_name:
            return run_federated_command(
                resolve_qualified_tool(tool_name), "doc", args[1:]
            )
        return run_federated_command(resolve_implicit_tool(tool_name), "doc", args[1:])

    print_tool_document(tool, start_line, all_lines)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        check_hub_cycle()
    except HwToolError as exc:
        print(f"[hw_tool] error: {exc}", file=sys.stderr)
        return 2
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print_usage()
        return 2

    command = args.pop(0)
    if command in {"-h", "--help"}:
        print_usage()
        return 0
    if command in {"-v", "-V", "--version"}:
        if args:
            print("[hw_tool] error: version does not accept arguments", file=sys.stderr)
            return 2
        print_version()
        return 0
    if command == "doctor":
        if args:
            print("[hw_tool] error: doctor does not accept arguments", file=sys.stderr)
            return 2
        return doctor()
    if command == "verify":
        try:
            return verify(args)
        except HwToolError as exc:
            print(f"[hw_tool] error: {exc}", file=sys.stderr)
            return 2
    if command == "test":
        try:
            return test(args)
        except HwToolError as exc:
            print(f"[hw_tool] error: {exc}", file=sys.stderr)
            return 2
    if command == "list":
        if not args:
            print_tool_list()
            return 0
        if args == ["--json"]:
            print_tool_list(json_mode=True)
            return 0
        if set(args) in ({"--tools"}, {"--recursive"}):
            try:
                print_recursive_tool_list()
                return 0
            except HwToolError as exc:
                print(f"[hw_tool] error: {exc}", file=sys.stderr)
                return 2
        if set(args) in ({"--tools", "--json"}, {"--recursive", "--json"}):
            try:
                print_recursive_tool_list(json_mode=True)
                return 0
            except HwToolError as exc:
                print(f"[hw_tool] error: {exc}", file=sys.stderr)
                return 2
        if args:
            print("[hw_tool] error: list does not accept arguments", file=sys.stderr)
            return 2
    if command == "sync":
        try:
            return sync_groups(args)
        except HwToolError as exc:
            print(f"[hw_tool] error: {exc}", file=sys.stderr)
            return 2
    if command == "doc":
        try:
            return print_document(args)
        except HwToolError as exc:
            print(f"[hw_tool] error: {exc}", file=sys.stderr)
            return 2
    if command == "run":
        if not args:
            print("[hw_tool] error: run requires a qualified tool name", file=sys.stderr)
            return 2
        try:
            return run_federated_tool(resolve_qualified_tool(args[0]), args[1:])
        except HwToolError as exc:
            print(f"[hw_tool] error: {exc}", file=sys.stderr)
            return 2
    if command == "help":
        if len(args) != 1:
            print("[hw_tool] error: help requires exactly one tool name", file=sys.stderr)
            return 2
        if args[0] == "sync":
            print("usage: hw_tool sync <group>|--all [--dry-run] [--shallow]")
            return 0
        if args[0] == "doctor":
            print("usage: hw_tool doctor")
            print("checks Python, Git, PATH, registered tools, and child groups")
            return 0
        if args[0] == "verify":
            print("usage: hw_tool verify [group|tool|--all]")
            return 0
        if args[0] == "test":
            print("usage: hw_tool test [group|tool|--all] [--unit|--smoke|--all]")
            return 0
        if args[0] in {"-v", "-V", "--version"}:
            print("usage: hw_tool --version")
            return 0
        try:
            tool = get_tool(args[0])
            if tool.doc_url:
                print(f"document: {tool.doc_url}", flush=True)
            print(tool.usage, flush=True)
            help_args = ["list"] if tool.kind == TOOL_KIND_HUB else ["--help"]
            return run_tool(tool, help_args)
        except HwToolError as exc:
            try:
                if "." in args[0]:
                    return run_federated_command(
                        resolve_qualified_tool(args[0]), "help", []
                    )
                return run_federated_command(resolve_implicit_tool(args[0]), "help", [])
            except HwToolError as implicit_exc:
                print(f"[hw_tool] error: {implicit_exc}", file=sys.stderr)
                return 2

    try:
        return run_tool(get_tool(command), args)
    except HwToolError as exc:
        try:
            if "." in command:
                return run_federated_tool(resolve_qualified_tool(command), args)
            return run_federated_tool(resolve_implicit_tool(command), args)
        except HwToolError as implicit_exc:
            print(f"[hw_tool] error: {implicit_exc}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
