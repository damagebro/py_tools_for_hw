#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tool_registry import (
    DEFAULT_GROUP,
    REPOSITORY_MAP,
    TOOL_MAP,
    TOOL_SPECS,
    RepositorySpec,
    ToolSpec,
)


class HwToolError(Exception):
    pass


TOOL_KIND_SCRIPT = "script"
TOOL_KIND_HUB = "hub"
TOOL_SOURCE_GIT = "git"
DEFAULT_DOC_LINES = 48
GROUPS_ROOT_ENV = "HW_TOOL_GROUPS_ROOT"


def tool_root() -> Path:
    override = os.environ.get("HW_TOOL_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


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
    groups_root = os.environ.get(GROUPS_ROOT_ENV)
    if groups_root:
        return (Path(groups_root).expanduser().resolve() / repository.name).resolve()
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
    print("usage: hw_tool <list|help|doc|sync|group> [args ...]")
    print("       hw_tool list")
    print("       hw_tool help <tool>")
    print("       hw_tool doc <tool> [--all|--from <line>]")
    print("       hw_tool sync <group>|--all")
    print("       hw_tool <group> [group arguments]")


def git_state(tool: ToolSpec) -> tuple[str, str]:
    repository = repository_spec(tool)
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
    if tool.source == TOOL_SOURCE_GIT and not path.exists():
        return "not-synced", ""
    try:
        validate_tool(tool)
    except HwToolError:
        return "missing", ""
    if tool.source != TOOL_SOURCE_GIT:
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
        "description": tool.description,
        "status": status,
        "detail": detail or None,
        "doc_url": tool.doc_url,
    }


def print_tool_list(json_mode: bool = False) -> None:
    entries = [tool_payload(tool, *git_state(tool)) for tool in TOOL_SPECS]
    if json_mode:
        print(json.dumps({"tools": entries}, ensure_ascii=False))
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
        environment[GROUPS_ROOT_ENV] = str((tool_root() / "groups").resolve())
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


def group_tools(group: ToolSpec) -> list[str]:
    validate_tool(group)
    command = [sys.executable, "-B", str(script_path(group)), "list", "--json"]
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
    entries = payload.get("tools") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise HwToolError(f"group '{group.name}' JSON is missing tools")

    names: list[str] = []
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else None
        if isinstance(name, str) and name:
            names.append(name)
    return names


def global_tool_index() -> dict[str, list[ToolSpec]]:
    index: dict[str, list[ToolSpec]] = {}
    for group in TOOL_SPECS:
        if group.kind != TOOL_KIND_HUB:
            continue
        status, _ = git_state(group)
        if status != "ready":
            continue
        for name in group_tools(group):
            index.setdefault(name, []).append(group)
    return index


def resolve_implicit_tool(name: str) -> ToolSpec:
    if DEFAULT_GROUP is None:
        raise HwToolError(f"unknown tool: {name}")
    candidates = global_tool_index().get(name, [])
    if not candidates:
        raise HwToolError(f"unknown tool: {name}")
    if len(candidates) == 1:
        return candidates[0]

    for group in candidates:
        if group.name == DEFAULT_GROUP:
            return group
    group_names = ", ".join(group.name for group in candidates)
    raise HwToolError(
        f"tool '{name}' exists in groups: {group_names}; use: hw_tool <group> {name}"
    )


def print_global_tool_list() -> None:
    index = global_tool_index()
    if not index:
        print("no ready group tools")
        return
    name_width = max(len(name) for name in index)
    print("global tools:")
    for name in sorted(index):
        groups = index[name]
        group_names = ", ".join(group.name for group in groups)
        status = "conflict" if len(groups) > 1 else "unique"
        default = " default" if any(group.name == DEFAULT_GROUP for group in groups) else ""
        print(f"  {name:<{name_width}}  {status:<8}  {group_names}{default}")


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


def sync_git_tool(tool: ToolSpec) -> None:
    source = repository_spec(tool)
    if source is not None:
        workspace = repository_workspace_path(source)
        if workspace is not None and (workspace / tool.script).is_file():
            print(f"[sync] {source.name}: using local workspace {workspace}")
            return
        sync_git_repository(source)
        return

    if tool.source != TOOL_SOURCE_GIT:
        raise HwToolError(f"tool '{tool.name}' does not use a git source")
    if not tool.repository or not tool.branch:
        raise HwToolError(f"git tool '{tool.name}' has incomplete configuration")

    path = checkout_path(tool)
    if path is None:
        raise HwToolError(f"git tool '{tool.name}' requires a checkout path")

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        run_git(
            [
                "git",
                "clone",
                "--branch",
                tool.branch,
                "--single-branch",
                tool.repository,
                str(path),
            ],
            tool_root(),
        )
        print(f"[sync] {tool.name}: cloned {tool.branch}")
        return

    if not (path / ".git").exists():
        raise HwToolError(f"tool '{tool.name}' path is not a git checkout: {path}")

    status = run_git(["git", "status", "--porcelain"], path)
    if status.stdout.strip():
        raise HwToolError(f"tool '{tool.name}' has uncommitted changes: {path}")

    run_git(["git", "fetch", "origin", tool.branch], path)
    run_git(["git", "checkout", tool.branch], path)
    run_git(["git", "pull", "--ff-only", "origin", tool.branch], path)
    print(f"[sync] {tool.name}: updated {tool.branch}")


def sync_git_repository(repository: RepositorySpec) -> None:
    path = repository_checkout_path(repository)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        run_git(
            [
                "git",
                "clone",
                "--branch",
                repository.branch,
                "--single-branch",
                repository.repository,
                str(path),
            ],
            tool_root(),
        )
        print(f"[sync] {repository.name}: cloned {repository.branch}")
        return

    if not (path / ".git").exists():
        raise HwToolError(
            f"repository '{repository.name}' path is not a git checkout: {path}"
        )

    status = run_git(["git", "status", "--porcelain"], path)
    if status.stdout.strip():
        raise HwToolError(f"repository '{repository.name}' has uncommitted changes: {path}")

    run_git(["git", "fetch", "origin", repository.branch], path)
    run_git(["git", "checkout", repository.branch], path)
    run_git(["git", "pull", "--ff-only", "origin", repository.branch], path)
    print(f"[sync] {repository.name}: updated {repository.branch}")


def sync_groups(args: list[str]) -> int:
    if len(args) != 1:
        raise HwToolError("sync requires one group name or --all")
    nested_groups: list[ToolSpec] = []
    if args[0] == "--all":
        tools = [
            tool
            for tool in TOOL_SPECS
            if tool.source == TOOL_SOURCE_GIT or tool.repository_name
        ]
        if DEFAULT_GROUP is not None:
            nested_groups = [
                tool for tool in TOOL_SPECS if tool.kind == TOOL_KIND_HUB
            ]
    else:
        selected = get_tool(args[0])
        if selected.kind == TOOL_KIND_HUB and selected.source != TOOL_SOURCE_GIT:
            tools = []
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
            sync_git_tool(tool)
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
        result = run_tool(group, ["sync", "--all"])
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
        group = resolve_implicit_tool(tool_name)
        return run_tool(group, ["doc", tool_name, *args[1:]])

    print_tool_document(tool, start_line, all_lines)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print_usage()
        return 2

    command = args.pop(0)
    if command in {"-h", "--help"}:
        print_usage()
        return 0
    if command == "list":
        if not args:
            print_tool_list()
            return 0
        if args == ["--json"]:
            print_tool_list(json_mode=True)
            return 0
        if args == ["--tools"] and DEFAULT_GROUP is not None:
            try:
                print_global_tool_list()
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
    if command == "help":
        if len(args) != 1:
            print("[hw_tool] error: help requires exactly one tool name", file=sys.stderr)
            return 2
        if args[0] == "sync":
            print("usage: hw_tool sync <group>|--all")
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
                group = resolve_implicit_tool(args[0])
                return run_tool(group, ["help", args[0]])
            except HwToolError as implicit_exc:
                print(f"[hw_tool] error: {implicit_exc}", file=sys.stderr)
                return 2

    try:
        return run_tool(get_tool(command), args)
    except HwToolError as exc:
        try:
            group = resolve_implicit_tool(command)
            return run_tool(group, [command, *args])
        except HwToolError as implicit_exc:
            print(f"[hw_tool] error: {implicit_exc}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    raise SystemExit(main())
