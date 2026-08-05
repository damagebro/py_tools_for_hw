#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from admin_policy import (
    AdminConfig,
    AdminError,
    PolicyStatus,
    RepositoryTarget,
    admin_state_dir,
    append_audit,
    load_admin_config,
    now_text,
    provider_client,
    provider_for_repository,
    read_json,
    write_json,
)


STATE_DIR_NAME = ".git_repo"
MANIFEST_NAME = "git_deps.toml"
RESOLVED_NAME = "resolved.toml"
GRAPH_NAME = "graph.json"
TREE_NAME = "tree.txt"
SCHEMA_VERSION = 1
CHECKOUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class RepoMgrError(Exception):
    def __init__(self, code: str, message: str, details: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class Dependency:
    repository: str
    ref: str


@dataclass(frozen=True)
class Request:
    ref: str
    chain: tuple[str, ...]


@dataclass
class RepositoryNode:
    key: str
    name: str
    repository: str
    ref: str
    commit: str
    checkout: str
    path: Path
    root: bool = False
    requests: list[Request] = field(default_factory=list)


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def git_output(args: list[str], cwd: Path) -> str:
    result = run_git(args, cwd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RepoMgrError(
            "E_GIT",
            f"git {' '.join(args)} failed in {cwd}",
            (detail,) if detail else (),
        )
    return result.stdout.strip()


def git_success(args: list[str], cwd: Path) -> bool:
    return run_git(args, cwd).returncode == 0


def normalize_repository(repository: str) -> str:
    value = repository.strip().rstrip("/\\")
    if value.endswith(".git"):
        value = value[:-4]
    path = Path(value)
    if path.is_absolute():
        return str(path.resolve()).casefold()
    return value


def is_full_repository(repository: str) -> bool:
    value = repository.strip()
    return "://" in value or value.startswith("git@") or Path(value).is_absolute()


def repository_basename(repository: str) -> str:
    value = repository.strip().rstrip("/\\")
    if value.endswith(".git"):
        value = value[:-4]
    value = value.replace("\\", "/")
    name = value.rsplit("/", maxsplit=1)[-1]
    if not CHECKOUT_NAME_RE.fullmatch(name):
        raise RepoMgrError(
            "E_CHECKOUT_NAME",
            f"repository basename cannot be used as a checkout name: {name}",
            ("add a [[checkout]] entry in the top-level git_deps.toml",),
        )
    return name


def validate_checkout_name(name: object) -> str:
    if not isinstance(name, str) or not CHECKOUT_NAME_RE.fullmatch(name):
        raise RepoMgrError(
            "E_CHECKOUT_NAME",
            "checkout name must contain only letters, digits, '.', '_', or '-'",
        )
    if name in {".", ".."}:
        raise RepoMgrError("E_CHECKOUT_NAME", f"invalid checkout name: {name}")
    return name


def read_toml(path: Path, purpose: str) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RepoMgrError("E_MANIFEST_MISSING", f"{purpose} not found: {path}") from exc
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RepoMgrError("E_TOML", f"failed to read {purpose}: {path}", (str(exc),)) from exc
    if not isinstance(data, dict):
        raise RepoMgrError("E_TOML", f"{purpose} must contain a TOML table: {path}")
    return data


def remote_urls(data: dict[str, Any], path: Path) -> dict[str, str]:
    raw_remotes = data.get("remote", {})
    if raw_remotes is None:
        return {}
    if not isinstance(raw_remotes, dict):
        raise RepoMgrError("E_MANIFEST", f"[remote] must be a table: {path}")

    result: dict[str, str] = {}
    for name, item in raw_remotes.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            raise RepoMgrError("E_MANIFEST", f"invalid remote entry in {path}")
        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            raise RepoMgrError("E_MANIFEST", f"remote '{name}' requires a non-empty url: {path}")
        result[name] = url.strip().rstrip("/")
    return result


def resolve_repository(
    item: dict[str, Any],
    remotes: dict[str, str],
    path: Path,
) -> str:
    repository = item.get("repository")
    remote = item.get("remote")
    if not isinstance(repository, str) or not repository.strip():
        raise RepoMgrError("E_MANIFEST", f"dependency requires repository: {path}")
    repository = repository.strip()

    if is_full_repository(repository):
        if remote is not None:
            raise RepoMgrError(
                "E_MANIFEST",
                f"dependency with full repository URL must not set remote: {path}",
            )
        return repository

    if remote is None:
        if len(remotes) == 1:
            remote = next(iter(remotes))
        elif not remotes:
            raise RepoMgrError(
                "E_MANIFEST",
                f"relative repository requires a [remote.*] definition: {path}",
            )
        else:
            raise RepoMgrError(
                "E_MANIFEST",
                f"relative repository requires explicit remote when multiple remotes exist: {path}",
            )
    if not isinstance(remote, str) or remote not in remotes:
        raise RepoMgrError("E_MANIFEST", f"unknown remote '{remote}' in {path}")
    return f"{remotes[remote]}/{repository.lstrip('/')}"


def parse_dependencies(data: dict[str, Any], path: Path) -> tuple[Dependency, ...]:
    remotes = remote_urls(data, path)
    raw_dependencies = data.get("dependency", [])
    if not isinstance(raw_dependencies, list):
        raise RepoMgrError("E_MANIFEST", f"[[dependency]] entries must be an array: {path}")

    result: list[Dependency] = []
    for item in raw_dependencies:
        if not isinstance(item, dict):
            raise RepoMgrError("E_MANIFEST", f"invalid [[dependency]] entry: {path}")
        ref = item.get("ref")
        if not isinstance(ref, str) or not ref.strip():
            raise RepoMgrError("E_MANIFEST", f"dependency requires ref: {path}")
        result.append(Dependency(resolve_repository(item, remotes, path), ref.strip()))
    return tuple(result)


def parse_checkout_overrides(data: dict[str, Any], path: Path) -> dict[str, str]:
    remotes = remote_urls(data, path)
    raw_overrides = data.get("checkout", [])
    if not isinstance(raw_overrides, list):
        raise RepoMgrError("E_MANIFEST", f"[[checkout]] entries must be an array: {path}")

    result: dict[str, str] = {}
    for item in raw_overrides:
        if not isinstance(item, dict):
            raise RepoMgrError("E_MANIFEST", f"invalid [[checkout]] entry: {path}")
        repository = resolve_repository(item, remotes, path)
        name = validate_checkout_name(item.get("name"))
        key = normalize_repository(repository)
        previous = result.get(key)
        if previous is not None and previous != name:
            raise RepoMgrError(
                "E_CHECKOUT_OVERRIDE",
                f"repository has conflicting checkout names: {repository}",
                (f"first: {previous}", f"second: {name}"),
            )
        result[key] = name
    return result


def ensure_git_repository(path: Path) -> Path:
    result = run_git(["rev-parse", "--show-toplevel"], path)
    if result.returncode != 0:
        raise RepoMgrError("E_NOT_GIT", f"not a Git repository: {path}")
    return Path(result.stdout.strip()).resolve()


def repository_origin(path: Path) -> str:
    origin = git_output(["config", "--get", "remote.origin.url"], path)
    if not origin:
        raise RepoMgrError("E_ORIGIN", f"repository has no remote.origin.url: {path}")
    return origin


def repository_commit(path: Path) -> str:
    return git_output(["rev-parse", "HEAD"], path)


def is_dirty(path: Path, ignored_untracked: tuple[str, ...] = ()) -> bool:
    lines = git_output(["status", "--porcelain"], path).splitlines()
    for line in lines:
        if not line.startswith("?? "):
            return True
        name = line[3:].replace("\\", "/")
        if not any(name == prefix.rstrip("/") or name.startswith(prefix) for prefix in ignored_untracked):
            return True
    return False


def is_top_dirty(top: Path) -> bool:
    return is_dirty(top, ("import/", ".git_repo/"))


def checkout_commit(path: Path, commit: str) -> str:
    git_output(["checkout", "--detach", commit], path)
    return repository_commit(path)


def resolve_ref(path: Path, ref: str) -> str:
    git_output(["fetch", "--tags", "origin"], path)
    candidates = (ref, f"origin/{ref}", "FETCH_HEAD")
    for candidate in candidates:
        result = run_git(["rev-parse", "--verify", f"{candidate}^{{commit}}"], path)
        if result.returncode == 0:
            return result.stdout.strip()
    fetch_result = run_git(["fetch", "origin", ref], path)
    if fetch_result.returncode == 0:
        result = run_git(["rev-parse", "--verify", "FETCH_HEAD^{commit}"], path)
        if result.returncode == 0:
            return result.stdout.strip()
    raise RepoMgrError(
        "E_REF_NOT_FOUND",
        f"cannot resolve ref '{ref}' in {path}",
    )


def materialize_repository(path: Path, repository: str, ref: str, shallow: bool) -> str:
    if path.exists():
        if not path.is_dir():
            raise RepoMgrError("E_CHECKOUT_PATH", f"checkout path is not a directory: {path}")
        ensure_git_repository(path)
        origin = repository_origin(path)
        if normalize_repository(origin) != normalize_repository(repository):
            raise RepoMgrError(
                "E_ORIGIN_CONFLICT",
                f"checkout path belongs to a different repository: {path}",
                (f"existing: {origin}", f"requested: {repository}"),
            )
        if is_dirty(path):
            raise RepoMgrError("E_DIRTY", f"refusing to update dirty checkout: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        clone_args = ["clone", "--no-checkout"]
        if shallow:
            clone_args.extend(("--depth", "1"))
        clone_args.extend((repository, str(path)))
        result = run_git(clone_args, path.parent)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise RepoMgrError(
                "E_CLONE",
                f"failed to clone repository: {repository}",
                (detail,) if detail else (),
            )

    commit = resolve_ref(path, ref)
    return checkout_commit(path, commit)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def state_dir(top: Path) -> Path:
    return top / STATE_DIR_NAME


def relative_checkout(top: Path, path: Path) -> str:
    return "." if path == top else path.relative_to(top).as_posix()


class WorkspaceResolver:
    def __init__(self, top: Path, shallow: bool) -> None:
        self.top = ensure_git_repository(top)
        self.shallow = shallow
        self.nodes: dict[str, RepositoryNode] = {}
        self.node_order: list[str] = []
        self.edges: list[tuple[str, str]] = []
        self.checkout_names: dict[str, str] = {}
        self.root_key = ""
        self.overrides: dict[str, str] = {}

    def resolve(self) -> None:
        top_manifest_path = self.top / MANIFEST_NAME
        top_manifest = read_toml(top_manifest_path, MANIFEST_NAME)
        self.overrides = parse_checkout_overrides(top_manifest, top_manifest_path)

        root_repository = repository_origin(self.top)
        self.root_key = normalize_repository(root_repository)
        root_node = RepositoryNode(
            key=self.root_key,
            name=self.top.name,
            repository=root_repository,
            ref="HEAD",
            commit=repository_commit(self.top),
            checkout=".",
            path=self.top,
            root=True,
        )
        self.nodes[self.root_key] = root_node
        self.node_order.append(self.root_key)
        self._walk(root_node, top_manifest, (self.root_key,), (root_node.name,))

    def _walk(
        self,
        parent: RepositoryNode,
        manifest: dict[str, Any],
        stack: tuple[str, ...],
        chain: tuple[str, ...],
    ) -> None:
        for dependency in parse_dependencies(manifest, parent.path / MANIFEST_NAME):
            key = normalize_repository(dependency.repository)
            existing = self.nodes.get(key)
            target_name = existing.name if existing is not None else self._checkout_name(key, dependency.repository)
            request_chain = (*chain, target_name)

            if key in stack:
                cycle_start = stack.index(key)
                cycle_names = [self.nodes[item].name for item in stack[cycle_start:]]
                cycle_names.append(target_name)
                raise RepoMgrError(
                    "E_DEPENDENCY_CYCLE",
                    "circular Git dependency detected",
                    (
                        f"cycle: {' -> '.join(cycle_names)}",
                        "dependency tree:",
                        *self._tree_lines_for_chain(request_chain, "CYCLE"),
                    ),
                )

            if existing is not None:
                previous = existing.requests[0]
                if previous.ref != dependency.ref:
                    raise RepoMgrError(
                        "E_REF_CONFLICT",
                        "one repository requires multiple refs",
                        (
                            f"repository: {dependency.repository}",
                            "conflicting requests:",
                            f"  {' -> '.join(previous.chain)}  ref: {previous.ref}",
                            f"  {' -> '.join(request_chain)}  ref: {dependency.ref}",
                            "resolution: align the ref values in the relevant git_deps.toml files",
                        ),
                    )
                existing.requests.append(Request(dependency.ref, request_chain))
                self.edges.append((parent.key, existing.key))
                continue

            checkout = self._checkout_name(key, dependency.repository)
            path = self.top / "import" / checkout
            commit = materialize_repository(path, dependency.repository, dependency.ref, self.shallow)
            node = RepositoryNode(
                key=key,
                name=checkout,
                repository=dependency.repository,
                ref=dependency.ref,
                commit=commit,
                checkout=relative_checkout(self.top, path),
                path=path,
                requests=[Request(dependency.ref, request_chain)],
            )
            self.nodes[key] = node
            self.node_order.append(key)
            self.checkout_names[checkout] = key
            self.edges.append((parent.key, key))
            child_manifest = read_toml(path / MANIFEST_NAME, MANIFEST_NAME)
            self._walk(node, child_manifest, (*stack, key), request_chain)

    def _checkout_name(self, key: str, repository: str) -> str:
        name = self.overrides.get(key, repository_basename(repository))
        previous_key = self.checkout_names.get(name)
        if previous_key is not None and previous_key != key:
            previous = self.nodes[previous_key]
            raise RepoMgrError(
                "E_CHECKOUT_NAME_CONFLICT",
                f"flat checkout name collision: {name}",
                (
                    f"existing repository: {previous.repository}",
                    f"requested repository: {repository}",
                    "add a unique [[checkout]] name in the top-level git_deps.toml",
                ),
            )
        return name

    def _tree_lines_for_chain(self, chain: tuple[str, ...], marker: str) -> tuple[str, ...]:
        lines: list[str] = []
        for index, name in enumerate(chain):
            prefix = "  " * index
            suffix = f" [{marker}]" if index == len(chain) - 1 else ""
            lines.append(f"{prefix}{name}{suffix}")
        return tuple(lines)

    def tree_text(self) -> str:
        children: dict[str, list[str]] = {key: [] for key in self.nodes}
        for parent, child in self.edges:
            children[parent].append(child)

        lines = [self.nodes[self.root_key].name]
        visited = {self.root_key}

        def append_children(parent: str, prefix: str) -> None:
            items = children[parent]
            for index, child in enumerate(items):
                last = index == len(items) - 1
                connector = "└── " if last else "├── "
                node = self.nodes[child]
                shared = child in visited
                suffix = " [shared]" if shared else ""
                lines.append(f"{prefix}{connector}{node.name}{suffix}")
                if not shared:
                    visited.add(child)
                    append_children(child, prefix + ("    " if last else "│   "))

        append_children(self.root_key, "")
        return "\n".join(lines) + "\n"

    def state(self) -> dict[str, Any]:
        root = self.nodes[self.root_key]
        repositories = []
        for key in self.node_order:
            if key == self.root_key:
                continue
            node = self.nodes[key]
            repositories.append(
                {
                    "name": node.name,
                    "repository": node.repository,
                    "ref": node.ref,
                    "commit": node.commit,
                    "checkout": node.checkout,
                }
            )
        return {
            "workspace": {
                "schema_version": SCHEMA_VERSION,
                "top_name": root.name,
                "top_repository": root.repository,
                "top_commit": root.commit,
            },
            "repositories": repositories,
        }

    def graph(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "root": self.root_key,
            "nodes": [
                {
                    "name": self.nodes[key].name,
                    "repository": self.nodes[key].repository,
                    "ref": self.nodes[key].ref,
                    "commit": self.nodes[key].commit,
                    "git_root": self.nodes[key].checkout,
                    "root": self.nodes[key].root,
                }
                for key in self.node_order
            ],
            "edges": [
                {"from": parent, "to": child}
                for parent, child in self.edges
            ],
        }


def state_to_toml(state: dict[str, Any]) -> str:
    workspace = state["workspace"]
    lines = [
        "[workspace]",
        f"schema_version = {workspace['schema_version']}",
        f"top_name = {toml_string(workspace['top_name'])}",
        f"top_repository = {toml_string(workspace['top_repository'])}",
        f"top_commit = {toml_string(workspace['top_commit'])}",
        "",
    ]
    for repository in state["repositories"]:
        lines.extend(
            (
                "[[repository]]",
                f"name = {toml_string(repository['name'])}",
                f"repository = {toml_string(repository['repository'])}",
                f"ref = {toml_string(repository['ref'])}",
                f"commit = {toml_string(repository['commit'])}",
                f"checkout = {toml_string(repository['checkout'])}",
                "",
            )
        )
    return "\n".join(lines)


def write_workspace_state(top: Path, resolver: WorkspaceResolver) -> None:
    output_dir = state_dir(top)
    output_dir.mkdir(parents=True, exist_ok=True)
    state = resolver.state()
    (output_dir / RESOLVED_NAME).write_text(state_to_toml(state), encoding="utf-8")
    (output_dir / GRAPH_NAME).write_text(
        json.dumps(resolver.graph(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_dir / TREE_NAME).write_text(resolver.tree_text(), encoding="utf-8")


def load_resolved(top: Path) -> dict[str, Any]:
    path = state_dir(top) / RESOLVED_NAME
    data = read_toml(path, RESOLVED_NAME)
    workspace = data.get("workspace")
    repositories = data.get("repository")
    if not isinstance(workspace, dict) or not isinstance(repositories, list):
        raise RepoMgrError("E_RESOLVED", f"invalid resolved state: {path}")
    required_workspace = ("top_name", "top_repository", "top_commit")
    if any(not isinstance(workspace.get(key), str) for key in required_workspace):
        raise RepoMgrError("E_RESOLVED", f"invalid workspace section: {path}")
    for item in repositories:
        if not isinstance(item, dict):
            raise RepoMgrError("E_RESOLVED", f"invalid repository entry: {path}")
        required = ("name", "repository", "ref", "commit", "checkout")
        if any(not isinstance(item.get(key), str) for key in required):
            raise RepoMgrError("E_RESOLVED", f"invalid repository entry: {path}")
    return {"workspace": workspace, "repositories": repositories}


def state_entries(top: Path, state: dict[str, Any]) -> list[tuple[str, Path]]:
    entries = [(str(state["workspace"]["top_name"]), top)]
    for item in state["repositories"]:
        checkout = Path(str(item["checkout"]))
        if checkout.is_absolute() or ".." in checkout.parts:
            raise RepoMgrError("E_RESOLVED", f"invalid checkout path in resolved state: {checkout}")
        entries.append((str(item["name"]), (top / checkout).resolve()))
    return entries


def state_records(top: Path, state: dict[str, Any]) -> list[dict[str, str | Path]]:
    workspace = state["workspace"]
    records: list[dict[str, str | Path]] = [
        {
            "name": str(workspace["top_name"]),
            "repository": str(workspace["top_repository"]),
            "ref": "HEAD",
            "commit": str(workspace["top_commit"]),
            "checkout": ".",
            "path": top,
        }
    ]
    for item in state["repositories"]:
        records.append(
            {
                "name": str(item["name"]),
                "repository": str(item["repository"]),
                "ref": str(item["ref"]),
                "commit": str(item["commit"]),
                "checkout": str(item["checkout"]),
                "path": (top / str(item["checkout"])).resolve(),
            }
        )
    return records


def command_sync(top_arg: str, shallow: bool) -> int:
    resolver = WorkspaceResolver(Path(top_arg).resolve(), shallow)
    resolver.resolve()
    write_workspace_state(resolver.top, resolver)
    print(f"synced {len(resolver.node_order) - 1} imported repository(s)")
    print(f"tree: {state_dir(resolver.top) / TREE_NAME}")
    return 0


def command_export_flat(top_arg: str, output_arg: str) -> int:
    top = ensure_git_repository(Path(top_arg).resolve())
    state = load_resolved(top)
    output = Path(output_arg)
    if not output.is_absolute():
        output = top / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(state_to_toml(state), encoding="utf-8")
    print(f"generated flat snapshot: {output}")
    return 0


def command_graph(top_arg: str, output_format: str) -> int:
    top = ensure_git_repository(Path(top_arg).resolve())
    if output_format == "tree":
        path = state_dir(top) / TREE_NAME
        try:
            print(path.read_text(encoding="utf-8"), end="")
        except OSError as exc:
            raise RepoMgrError("E_STATE", f"tree state not found: {path}") from exc
        return 0
    path = state_dir(top) / GRAPH_NAME
    try:
        print(path.read_text(encoding="utf-8"), end="")
    except OSError as exc:
        raise RepoMgrError("E_STATE", f"graph state not found: {path}") from exc
    return 0


def command_status(top_arg: str) -> int:
    top = ensure_git_repository(Path(top_arg).resolve())
    state = load_resolved(top)
    expected_origin = str(state["workspace"]["top_repository"])
    actual_origin = repository_origin(top)
    if normalize_repository(actual_origin) != normalize_repository(expected_origin):
        raise RepoMgrError("E_ORIGIN_CONFLICT", "top repository does not match resolved state")

    failures = 0
    for name, path in state_entries(top, state):
        if not path.is_dir():
            print(f"[missing] {name}: {path}")
            failures += 1
            continue
        try:
            commit = repository_commit(path)
            dirty = is_top_dirty(path) if path == top else is_dirty(path)
        except RepoMgrError as exc:
            print(f"[error] {name}: {exc.message}")
            failures += 1
            continue
        suffix = " dirty" if dirty else ""
        print(f"[ok] {name}: {commit[:12]}{suffix}")
        if dirty:
            failures += 1
    return 1 if failures else 0


def command_forall(
    top_arg: str,
    command: str,
    projects: list[str],
    fail_fast: bool,
    dry_run: bool,
) -> int:
    top = ensure_git_repository(Path(top_arg).resolve())
    state = load_resolved(top)
    records = state_records(top, state)
    record_map = {str(record["name"]): record for record in records}
    unknown = [name for name in projects if name not in record_map]
    if unknown:
        raise RepoMgrError(
            "E_PROJECT",
            f"unknown project name: {unknown[0]}",
            (f"available: {', '.join(record_map)}",),
        )
    selected = set(projects)
    targets = [record for record in records if not selected or record["name"] in selected]
    failures = 0

    for record in targets:
        name = str(record["name"])
        path = record["path"]
        if not isinstance(path, Path) or not path.is_dir():
            print(f"[missing] {name}: {path}", file=sys.stderr)
            failures += 1
            if fail_fast:
                break
            continue
        checkout = str(record["checkout"])
        if dry_run:
            print(f"[plan] {name} ({checkout}): {command}")
            continue

        env = os.environ.copy()
        env.update(
            {
                "GIT_REPO_MGR_TOP": str(top),
                "GIT_REPO_MGR_NAME": name,
                "GIT_REPO_MGR_PATH": checkout,
                "REPO_PROJECT": name,
                "REPO_PATH": checkout,
                "REPO_REMOTE": str(record["repository"]),
                "REPO_LREV": repository_commit(path),
                "REPO_RREV": str(record["ref"]),
            }
        )
        result = subprocess.run(
            command,
            cwd=path,
            env=env,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        print(f"==> {name} ({checkout})")
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
        if result.returncode != 0:
            print(f"[failed] {name}: exit {result.returncode}", file=sys.stderr)
            failures += 1
            if fail_fast:
                break
    return 1 if failures else 0


def fetch_branch_checkout(path: Path, ref: str) -> str:
    git_output(["fetch", "--tags", "origin"], path)
    remote_branch = f"refs/remotes/origin/{ref}"
    if git_success(["show-ref", "--verify", "--quiet", remote_branch], path):
        git_output(["checkout", "-B", ref, f"origin/{ref}"], path)
        return repository_commit(path)
    return checkout_commit(path, resolve_ref(path, ref))


def command_switch(top_arg: str, ref: str, dry_run: bool) -> int:
    top = ensure_git_repository(Path(top_arg).resolve())
    state = load_resolved(top)
    entries = state_entries(top, state)
    for name, path in entries:
        if not path.is_dir():
            raise RepoMgrError("E_CHECKOUT_MISSING", f"checkout is missing: {name}: {path}")
        if is_top_dirty(path) if path == top else is_dirty(path):
            raise RepoMgrError("E_DIRTY", f"refusing to switch dirty checkout: {name}: {path}")
    for name, path in entries:
        if dry_run:
            print(f"[plan] {name}: switch to {ref}")
        else:
            commit = fetch_branch_checkout(path, ref)
            print(f"[ok] {name}: {ref} {commit[:12]}")
    return 0


def command_tag(top_arg: str, tag: str, message: str | None, push: bool, dry_run: bool) -> int:
    top = ensure_git_repository(Path(top_arg).resolve())
    state = load_resolved(top)
    entries = state_entries(top, state)
    for name, path in entries:
        if not path.is_dir():
            raise RepoMgrError("E_CHECKOUT_MISSING", f"checkout is missing: {name}: {path}")
        if is_top_dirty(path) if path == top else is_dirty(path):
            raise RepoMgrError("E_DIRTY", f"refusing to tag dirty checkout: {name}: {path}")
        if git_success(["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"], path):
            raise RepoMgrError("E_TAG_EXISTS", f"tag already exists: {name}: {tag}")
    annotation = message or f"git_repo_mgr workspace tag {tag}"
    for name, path in entries:
        if dry_run:
            print(f"[plan] {name}: tag {tag}")
        else:
            git_output(["tag", "-a", tag, "-m", annotation], path)
            print(f"[ok] {name}: tagged {tag}")
    if push and not dry_run:
        for name, path in entries:
            git_output(["push", "origin", f"refs/tags/{tag}"], path)
            print(f"[ok] {name}: pushed {tag}")
    return 0


def command_sync_flat(top_arg: str, flat_arg: str, shallow: bool) -> int:
    top = ensure_git_repository(Path(top_arg).resolve())
    flat_path = Path(flat_arg).resolve()
    state = read_flat_snapshot(flat_path)
    workspace = state["workspace"]
    if normalize_repository(repository_origin(top)) != normalize_repository(str(workspace["top_repository"])):
        raise RepoMgrError("E_ORIGIN_CONFLICT", "top repository does not match flat snapshot")
    if is_top_dirty(top):
        raise RepoMgrError("E_DIRTY", f"refusing to update dirty top checkout: {top}")
    checkout_commit(top, str(workspace["top_commit"]))
    for item in state["repositories"]:
        name = validate_checkout_name(item["name"])
        checkout = Path(item["checkout"])
        expected = Path("import") / name
        if checkout != expected:
            raise RepoMgrError(
                "E_FLAT",
                f"flat snapshot checkout must be {expected.as_posix()}: {checkout}",
            )
        commit = materialize_repository(top / checkout, item["repository"], item["commit"], shallow)
        if commit != item["commit"]:
            raise RepoMgrError("E_FLAT", f"commit mismatch while restoring {name}")
    state_dir(top).mkdir(parents=True, exist_ok=True)
    (state_dir(top) / RESOLVED_NAME).write_text(state_to_toml(state), encoding="utf-8")
    print(f"restored flat snapshot: {flat_path}")
    return 0


def admin_targets(top: Path, state: dict[str, Any]) -> list[RepositoryTarget]:
    result: list[RepositoryTarget] = []
    for record in state_records(top, state):
        path = record["path"]
        if not isinstance(path, Path):
            raise RepoMgrError("E_RESOLVED", "invalid checkout path in resolved state")
        result.append(
            RepositoryTarget(
                name=str(record["name"]),
                repository=str(record["repository"]),
                checkout=str(record["checkout"]),
                commit=repository_commit(path),
                ref=str(record["ref"]),
            )
        )
    return result


def admin_context(top_arg: str, config_arg: str | None) -> tuple[Path, AdminConfig, list[RepositoryTarget]]:
    top = ensure_git_repository(Path(top_arg).resolve())
    state = load_resolved(top)
    config = load_admin_config(top, config_arg, tomllib.loads)
    return top, config, admin_targets(top, state)


def admin_statuses(config: AdminConfig, targets: list[RepositoryTarget]) -> list[PolicyStatus]:
    clients: dict[str, Any] = {}
    statuses: list[PolicyStatus] = []
    for target in targets:
        provider, _ = provider_for_repository(config, target.repository)
        client = clients.get(provider.name)
        if client is None:
            client = provider_client(provider)
            clients[provider.name] = client
        statuses.append(client.status(target, config.branch))
    return statuses


def admin_client_map(config: AdminConfig) -> dict[str, Any]:
    clients: dict[str, Any] = {}
    for provider in config.providers:
        clients[provider.name] = provider_client(provider)
    return clients


def command_admin_policy_status(top_arg: str, config_arg: str | None) -> int:
    top, config, targets = admin_context(top_arg, config_arg)
    clients = admin_client_map(config)
    for provider in config.providers:
        print(f"[provider] {provider.name}: {provider.kind} as {clients[provider.name].identity()}")
    failures = 0
    for status in admin_statuses(config, targets):
        marker = "ok" if status.protected else "missing"
        print(f"[{marker}] {status.target.name}: {status.provider.name} {config.branch} {status.mode}")
        if not status.protected:
            failures += 1
    return 1 if failures else 0


def command_admin_policy_diff(top_arg: str, config_arg: str | None) -> int:
    _, config, targets = admin_context(top_arg, config_arg)
    failures = 0
    for status in admin_statuses(config, targets):
        matches = status.protected and status.mode == config.baseline_mode
        marker = "ok" if matches else "drift"
        print(
            f"[{marker}] {status.target.name}: expected {config.baseline_mode}, "
            f"actual {status.mode}"
        )
        if not matches:
            failures += 1
    return 1 if failures else 0


def lock_state_path(top: Path, lock_id: str) -> Path:
    return admin_state_dir(top) / "locks" / f"{lock_id}.json"


def apply_policy_mode(
    top: Path,
    config: AdminConfig,
    targets: list[RepositoryTarget],
    mode: str,
    operation: str,
    state_path: Path | None,
    dry_run: bool,
) -> int:
    if mode not in {"read-only", "integration-only"}:
        raise RepoMgrError("E_POLICY", f"unsupported policy mode: {mode}")
    statuses = admin_statuses(config, targets)
    clients = admin_client_map(config)
    state: dict[str, Any] = {
        "operation": operation,
        "timestamp": now_text(),
        "branch": config.branch,
        "mode": mode,
        "status": "planned" if dry_run else "in_progress",
        "repositories": [
            {
                "name": status.target.name,
                "repository": status.target.repository,
                "checkout": status.target.checkout,
                "provider": status.provider.name,
                "project": status.project,
                "raw_policy": status.raw,
                "applied": False,
            }
            for status in statuses
        ],
    }
    if state_path is not None and not dry_run:
        write_json(state_path, state)
    for item in state["repositories"]:
        name = str(item["name"])
        if dry_run:
            print(f"[plan] {name}: {config.branch} -> {mode}")
            continue
        client = clients[str(item["provider"])]
        client.apply_mode(str(item["project"]), config.branch, mode, item["raw_policy"])
        item["applied"] = True
        if state_path is not None:
            write_json(state_path, state)
        print(f"[ok] {name}: {config.branch} -> {mode}")
    state["status"] = "complete"
    if state_path is not None and not dry_run:
        write_json(state_path, state)
    if not dry_run:
        append_audit(
            top,
            {
                "operation": operation,
                "branch": config.branch,
                "mode": mode,
                "state": str(state_path) if state_path else None,
                "dry_run": dry_run,
            },
        )
    return 0


def command_admin_lock_main(
    top_arg: str,
    config_arg: str | None,
    mode: str,
    lock_id: str | None,
    dry_run: bool,
) -> int:
    top, config, targets = admin_context(top_arg, config_arg)
    generated_id = f"main-{datetime_stamp()}"
    selected_id = lock_id or generated_id
    path = lock_state_path(top, selected_id)
    if path.exists():
        raise RepoMgrError("E_LOCK", f"lock state already exists: {path}")
    result = apply_policy_mode(top, config, targets, mode, "lock-main", path, dry_run)
    if not dry_run:
        print(f"lock_id: {selected_id}")
    return result


def datetime_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def command_admin_unlock_main(top_arg: str, config_arg: str | None, lock_id: str, dry_run: bool) -> int:
    top, config, _ = admin_context(top_arg, config_arg)
    path = lock_state_path(top, lock_id)
    state = read_json(path)
    if state.get("operation") != "lock-main":
        raise RepoMgrError("E_LOCK", f"not a lock state: {path}")
    clients = admin_client_map(config)
    repositories = state.get("repositories")
    if not isinstance(repositories, list):
        raise RepoMgrError("E_LOCK", f"invalid lock state: {path}")
    for item in repositories:
        if not isinstance(item, dict):
            raise RepoMgrError("E_LOCK", f"invalid lock state: {path}")
        name = str(item.get("name", "unknown"))
        provider_name = item.get("provider")
        project = item.get("project")
        raw = item.get("raw_policy")
        if not isinstance(provider_name, str) or not isinstance(project, str):
            raise RepoMgrError("E_LOCK", f"invalid lock entry: {name}")
        if dry_run:
            print(f"[plan] {name}: restore {config.branch} policy")
            continue
        clients[provider_name].restore(project, config.branch, raw if isinstance(raw, dict) else None)
        print(f"[ok] {name}: restored {config.branch} policy")
    if not dry_run:
        state["status"] = "unlocked"
        state["unlocked_at"] = now_text()
        write_json(path, state)
    if not dry_run:
        append_audit(
            top,
            {"operation": "unlock-main", "branch": config.branch, "lock_id": lock_id, "dry_run": dry_run},
        )
    return 0


def command_admin_policy_apply(top_arg: str, config_arg: str | None, dry_run: bool) -> int:
    top, config, targets = admin_context(top_arg, config_arg)
    return apply_policy_mode(
        top,
        config,
        targets,
        config.baseline_mode,
        "policy-apply",
        None,
        dry_run,
    )


def release_state_path(top: Path, name: str) -> Path:
    return admin_state_dir(top) / "releases" / f"{name}.json"


def release_precheck(top: Path, config: AdminConfig, targets: list[RepositoryTarget], tag: str) -> None:
    failures: list[str] = []
    status_by_name = {status.target.name: status for status in admin_statuses(config, targets)}
    for target in targets:
        path = top / target.checkout
        dirty = is_top_dirty(path) if target.checkout == "." else is_dirty(path)
        if dirty:
            failures.append(f"{target.name}: dirty checkout")
            continue
        main_commit = resolve_ref(path, config.branch)
        head_commit = repository_commit(path)
        if head_commit != main_commit:
            failures.append(f"{target.name}: HEAD is not origin/{config.branch}")
        status = status_by_name[target.name]
        if not status.protected:
            failures.append(f"{target.name}: {config.branch} is not protected")
        if git_success(["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"], path):
            failures.append(f"{target.name}: tag already exists: {tag}")
    if failures:
        raise RepoMgrError("E_RELEASE_PRECHECK", "release precheck failed", tuple(failures))


def command_admin_release(
    top_arg: str,
    config_arg: str | None,
    name: str,
    push: bool,
    dry_run: bool,
) -> int:
    top, config, targets = admin_context(top_arg, config_arg)
    path = release_state_path(top, name)
    if path.exists():
        raise RepoMgrError("E_RELEASE", f"release state already exists: {path}")
    release_precheck(top, config, targets, name)
    state = {
        "operation": "release",
        "name": name,
        "timestamp": now_text(),
        "branch": config.branch,
        "push": push,
        "status": "planned" if dry_run else "in_progress",
        "repositories": [
            {
                "name": target.name,
                "checkout": target.checkout,
                "commit": repository_commit(top / target.checkout),
                "tag_created": False,
                "tag_pushed": False,
            }
            for target in targets
        ],
    }
    if not dry_run:
        write_json(path, state)
        snapshot = path.with_suffix(".toml")
        snapshot.write_text(state_to_toml(load_resolved(top)), encoding="utf-8")
    return continue_release(top, state, path, dry_run)


def continue_release(top: Path, state: dict[str, Any], path: Path, dry_run: bool) -> int:
    name = state.get("name")
    push = bool(state.get("push", False))
    repositories = state.get("repositories")
    if not isinstance(name, str) or not isinstance(repositories, list):
        raise RepoMgrError("E_RELEASE", f"invalid release state: {path}")
    for item in repositories:
        if not isinstance(item, dict):
            raise RepoMgrError("E_RELEASE", f"invalid release state: {path}")
        checkout = item.get("checkout")
        commit = item.get("commit")
        name_item = item.get("name")
        if not all(isinstance(value, str) for value in (checkout, commit, name_item)):
            raise RepoMgrError("E_RELEASE", f"invalid release entry: {path}")
        repo_path = top / checkout
        if repository_commit(repo_path) != commit:
            raise RepoMgrError("E_RELEASE", f"release commit changed: {name_item}")
        tag_commit = run_git(["rev-parse", "--verify", f"refs/tags/{name}^{{commit}}"], repo_path)
        if item.get("tag_created"):
            if tag_commit.returncode != 0 or tag_commit.stdout.strip() != commit:
                raise RepoMgrError("E_RELEASE", f"release tag mismatch: {name_item}: {name}")
        elif dry_run:
            print(f"[plan] {name_item}: create tag {name}")
        else:
            if tag_commit.returncode == 0:
                raise RepoMgrError("E_RELEASE", f"release tag already exists: {name_item}: {name}")
            git_output(["tag", "-a", name, "-m", f"git_repo_mgr release {name}"], repo_path)
            item["tag_created"] = True
            write_json(path, state)
            print(f"[ok] {name_item}: tagged {name}")
        if push and not item.get("tag_pushed"):
            if dry_run:
                print(f"[plan] {name_item}: push tag {name}")
            else:
                git_output(["push", "origin", f"refs/tags/{name}"], repo_path)
                item["tag_pushed"] = True
                write_json(path, state)
                print(f"[ok] {name_item}: pushed {name}")
    if not dry_run:
        state["status"] = "complete"
        state["completed_at"] = now_text()
        write_json(path, state)
        append_audit(top, {"operation": "release", "name": name, "state": str(path)})
    return 0


def command_admin_release_resume(top_arg: str, config_arg: str | None, name: str, dry_run: bool) -> int:
    top, config, targets = admin_context(top_arg, config_arg)
    path = release_state_path(top, name)
    state = read_json(path)
    if state.get("operation") != "release":
        raise RepoMgrError("E_RELEASE", f"not a release state: {path}")
    if state.get("branch") != config.branch:
        raise RepoMgrError("E_RELEASE", f"release branch differs from admin config: {path}")
    release_precheck_resume(top, config, targets, state)
    return continue_release(top, state, path, dry_run)


def release_precheck_resume(
    top: Path,
    config: AdminConfig,
    targets: list[RepositoryTarget],
    state: dict[str, Any],
) -> None:
    target_names = {target.name for target in targets}
    repositories = state.get("repositories")
    if not isinstance(repositories, list):
        raise RepoMgrError("E_RELEASE", "invalid release repository list")
    for item in repositories:
        if not isinstance(item, dict) or item.get("name") not in target_names:
            raise RepoMgrError("E_RELEASE", "workspace does not match release state")
        checkout = item.get("checkout")
        commit = item.get("commit")
        if not isinstance(checkout, str) or not isinstance(commit, str):
            raise RepoMgrError("E_RELEASE", "invalid release repository entry")
        repo_path = top / checkout
        if repository_commit(repo_path) != commit or resolve_ref(repo_path, config.branch) != commit:
            raise RepoMgrError(
                "E_RELEASE_PRECHECK",
                f"release commit is no longer origin/{config.branch}: {item.get('name')}",
            )
    for status in admin_statuses(config, targets):
        if not status.protected:
            raise RepoMgrError("E_RELEASE_PRECHECK", f"{status.target.name}: {config.branch} is not protected")


def command_admin_audit(top_arg: str) -> int:
    top = ensure_git_repository(Path(top_arg).resolve())
    path = admin_state_dir(top) / "audit.jsonl"
    try:
        print(path.read_text(encoding="utf-8"), end="")
    except FileNotFoundError:
        print("no admin audit records")
    return 0


def read_flat_snapshot(path: Path) -> dict[str, Any]:
    data = read_toml(path, "git_deps_flat.toml")
    workspace = data.get("workspace")
    repositories = data.get("repository")
    if not isinstance(workspace, dict) or not isinstance(repositories, list):
        raise RepoMgrError("E_FLAT", f"invalid flat snapshot: {path}")
    required_workspace = ("top_name", "top_repository", "top_commit")
    if any(not isinstance(workspace.get(key), str) for key in required_workspace):
        raise RepoMgrError("E_FLAT", f"invalid workspace section: {path}")
    seen_repositories: set[str] = set()
    seen_names: set[str] = set()
    for item in repositories:
        if not isinstance(item, dict):
            raise RepoMgrError("E_FLAT", f"invalid repository entry: {path}")
        required = ("name", "repository", "ref", "commit", "checkout")
        if any(not isinstance(item.get(key), str) for key in required):
            raise RepoMgrError("E_FLAT", f"invalid repository entry: {path}")
        name = validate_checkout_name(item["name"])
        repository_key = normalize_repository(item["repository"])
        if repository_key in seen_repositories or name in seen_names:
            raise RepoMgrError("E_FLAT", f"duplicate repository or checkout name: {path}")
        seen_repositories.add(repository_key)
        seen_names.add(name)
    return {"workspace": workspace, "repositories": repositories}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage a recursively declared multi-Git workspace.",
    )
    parser.add_argument("--version", action="version", version="git_repo_mgr 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="recursively sync git_deps.toml")
    sync_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    sync_parser.add_argument("--flat", help="restore a generated git_deps_flat.toml snapshot")
    sync_parser.add_argument("--shallow", action="store_true", help="use depth-1 clone for new checkouts")

    status_parser = subparsers.add_parser("status", help="show resolved checkout status")
    status_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")

    forall_parser = subparsers.add_parser("forall", help="run one shell command in every checkout")
    forall_parser.add_argument(
        "-c",
        "--command",
        dest="shell_command",
        required=True,
        help="shell command to execute",
    )
    forall_parser.add_argument("projects", nargs="*", help="optional top/import project names")
    forall_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    forall_parser.add_argument("--fail-fast", action="store_true", help="stop after the first failed command")
    forall_parser.add_argument("--dry-run", action="store_true", help="show planned commands only")

    graph_parser = subparsers.add_parser("graph", help="show saved dependency graph")
    graph_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    graph_parser.add_argument("--format", choices=("tree", "json"), default="tree")

    flat_parser = subparsers.add_parser("export-flat", help="export the resolved commit snapshot")
    flat_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    flat_parser.add_argument("-o", "--output", default="git_deps_flat.toml", help="snapshot output path")

    switch_parser = subparsers.add_parser("switch", help="switch every checkout to one branch, tag, or commit")
    switch_parser.add_argument("ref", help="branch, tag, or commit")
    switch_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    switch_parser.add_argument("--dry-run", action="store_true", help="show planned changes only")

    tag_parser = subparsers.add_parser("tag", help="create one annotated tag in every checkout")
    tag_parser.add_argument("name", help="tag name")
    tag_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    tag_parser.add_argument("-m", "--message", help="annotated tag message")
    tag_parser.add_argument("--push", action="store_true", help="push tags after local creation")
    tag_parser.add_argument("--dry-run", action="store_true", help="show planned changes only")

    admin_parser = subparsers.add_parser("admin", help="run provider-backed integration authority commands")
    admin_subparsers = admin_parser.add_subparsers(dest="admin_command", required=True)

    policy_status_parser = admin_subparsers.add_parser("policy-status", help="show main branch protection")
    policy_status_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    policy_status_parser.add_argument("--config", help="admin TOML configuration path")

    policy_diff_parser = admin_subparsers.add_parser("policy-diff", help="compare main policy with baseline")
    policy_diff_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    policy_diff_parser.add_argument("--config", help="admin TOML configuration path")

    policy_apply_parser = admin_subparsers.add_parser("policy-apply", help="apply baseline main policy")
    policy_apply_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    policy_apply_parser.add_argument("--config", help="admin TOML configuration path")
    policy_apply_parser.add_argument("--dry-run", action="store_true", help="show planned changes only")

    lock_parser = admin_subparsers.add_parser("lock-main", help="temporarily lock main across all repositories")
    lock_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    lock_parser.add_argument("--config", help="admin TOML configuration path")
    lock_parser.add_argument("--mode", choices=("read-only", "integration-only"), default="read-only")
    lock_parser.add_argument("--lock-id", help="stable lock state identifier")
    lock_parser.add_argument("--dry-run", action="store_true", help="show planned changes only")

    unlock_parser = admin_subparsers.add_parser("unlock-main", help="restore a saved main branch policy")
    unlock_parser.add_argument("lock_id", help="lock identifier returned by lock-main")
    unlock_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    unlock_parser.add_argument("--config", help="admin TOML configuration path")
    unlock_parser.add_argument("--dry-run", action="store_true", help="show planned changes only")

    release_parser = admin_subparsers.add_parser("release", help="snapshot and tag the protected main integration")
    release_parser.add_argument("name", help="release tag name")
    release_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    release_parser.add_argument("--config", help="admin TOML configuration path")
    release_parser.add_argument("--push", action="store_true", help="push release tags after local creation")
    release_parser.add_argument("--dry-run", action="store_true", help="show planned actions only")

    resume_parser = admin_subparsers.add_parser("release-resume", help="continue an interrupted release")
    resume_parser.add_argument("name", help="release tag name")
    resume_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    resume_parser.add_argument("--config", help="admin TOML configuration path")
    resume_parser.add_argument("--dry-run", action="store_true", help="show planned actions only")

    audit_parser = admin_subparsers.add_parser("audit", help="print local admin audit records")
    audit_parser.add_argument("--top", default=".", help="top Git repository, default: current directory")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "sync":
            if args.flat:
                return command_sync_flat(args.top, args.flat, args.shallow)
            return command_sync(args.top, args.shallow)
        if args.command == "status":
            return command_status(args.top)
        if args.command == "forall":
            return command_forall(
                args.top,
                args.shell_command,
                args.projects,
                args.fail_fast,
                args.dry_run,
            )
        if args.command == "graph":
            return command_graph(args.top, args.format)
        if args.command == "export-flat":
            return command_export_flat(args.top, args.output)
        if args.command == "switch":
            return command_switch(args.top, args.ref, args.dry_run)
        if args.command == "tag":
            return command_tag(args.top, args.name, args.message, args.push, args.dry_run)
        if args.command == "admin":
            if args.admin_command == "policy-status":
                return command_admin_policy_status(args.top, args.config)
            if args.admin_command == "policy-diff":
                return command_admin_policy_diff(args.top, args.config)
            if args.admin_command == "policy-apply":
                return command_admin_policy_apply(args.top, args.config, args.dry_run)
            if args.admin_command == "lock-main":
                return command_admin_lock_main(args.top, args.config, args.mode, args.lock_id, args.dry_run)
            if args.admin_command == "unlock-main":
                return command_admin_unlock_main(args.top, args.config, args.lock_id, args.dry_run)
            if args.admin_command == "release":
                return command_admin_release(args.top, args.config, args.name, args.push, args.dry_run)
            if args.admin_command == "release-resume":
                return command_admin_release_resume(args.top, args.config, args.name, args.dry_run)
            if args.admin_command == "audit":
                return command_admin_audit(args.top)
    except (RepoMgrError, AdminError) as exc:
        print(f"ERROR [{exc.code}]: {exc.message}", file=sys.stderr)
        for detail in exc.details:
            print(detail, file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
