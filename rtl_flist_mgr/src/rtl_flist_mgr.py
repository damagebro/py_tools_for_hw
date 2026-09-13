#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any


STATE_DIR = ".rtl_flist"
SKIP_DIRS = {".git", ".rtl_flist", "__pycache__", "build", "out"}
VARIABLE_RE = re.compile(r"\$(?:\{(?P<braced>[A-Za-z_][A-Za-z0-9_]*)\}|(?P<plain>[A-Za-z_][A-Za-z0-9_]*))")
CONDITION_RE = re.compile(r"^(?P<condition>.+?)\s*\?\s*\((?P<value>.*)\)$")
FIRST_PREFIX = "first: "
MODE_FLAGS = {
    "sim": frozenset({"is_sim"}),
    "synth": frozenset({"is_synth"}),
    "lint": frozenset({"is_lint"}),
    "emu": frozenset({"is_emu"}),
    "fpga": frozenset({"is_fpga"}),
}


class FlistError(Exception):
    def __init__(self, code: str, message: str, details: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class WorkspaceRepository:
    name: str
    root: Path
    checkout: str


@dataclass(frozen=True)
class FileSet:
    name: str
    directory: str | None
    files: tuple[str, ...]
    depend: tuple[str, ...]
    legacy_f: str | None


@dataclass(frozen=True)
class Core:
    core_id: str
    manifest: Path
    git_root: Path
    format_name: str
    filesets: dict[str, FileSet]
    selected_filesets: tuple[str, ...]


@dataclass(frozen=True)
class CoreIndexEntry:
    core_id: str
    manifest: Path
    git_root: Path
    format_name: str


@dataclass(frozen=True)
class OutputLine:
    kind: str
    value: str
    root: Path | None
    core_id: str
    manifest: Path


def toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def read_toml(path: Path, purpose: str) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FlistError("E_INPUT", f"{purpose} not found: {path}") from exc
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise FlistError("E_TOML", f"failed to read {purpose}: {path}", (str(exc),)) from exc
    if not isinstance(data, dict):
        raise FlistError("E_TOML", f"{purpose} must contain a TOML table: {path}")
    return data


def string_tuple(value: object, field: str, path: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise FlistError("E_MANIFEST", f"{field} must be a string array: {path}")
    return tuple(value)


def string_optional(value: object, field: str, path: Path) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise FlistError("E_MANIFEST", f"{field} must be a non-empty string: {path}")
    return value


def validate_keys(table: dict[str, Any], allowed: set[str], scope: str, path: Path) -> None:
    unsupported = sorted(set(table) - allowed)
    if unsupported:
        raise FlistError("E_MANIFEST", f"unsupported {scope} property: {unsupported[0]} ({path})")


def has_first_marker(value: str) -> bool:
    if value.startswith(FIRST_PREFIX):
        return True
    match = CONDITION_RE.match(value)
    return match is not None and match.group("value").strip().startswith(FIRST_PREFIX)


def split_first_marker(value: str, source: Path) -> tuple[str, bool]:
    if not value.startswith(FIRST_PREFIX):
        return value, False
    result = value[len(FIRST_PREFIX):].strip()
    if not result:
        raise FlistError("E_FIRST", f"first: requires a file or fileset value: {source}")
    return result, True


def load_workspace(workspace_arg: str) -> tuple[Path, tuple[WorkspaceRepository, ...]]:
    workspace = Path(workspace_arg).resolve()
    if not workspace.is_dir():
        raise FlistError("E_WORKSPACE", f"workspace directory not found: {workspace}")

    repositories = [WorkspaceRepository("top", workspace, ".")]
    import_root = workspace / "import"
    if import_root.is_dir():
        for checkout_root in sorted(import_root.iterdir(), key=lambda item: item.name):
            if checkout_root.is_dir():
                repositories.append(
                    WorkspaceRepository(
                        checkout_root.name,
                        checkout_root.resolve(),
                        f"import/{checkout_root.name}",
                    )
                )
    return workspace, tuple(repositories)


def find_workspace_root(start: Path) -> tuple[Path, str]:
    current = start.resolve()
    markers = []
    candidates = []
    for candidate in (current, *current.parents):
        if (candidate / STATE_DIR / "workspace.toml").is_file():
            markers.append(candidate)
        evidence = []
        if (candidate / STATE_DIR / "core_index.toml").is_file():
            evidence.append("core_index.toml")
        if (candidate / ".git").exists() and (candidate / "import").is_dir():
            evidence.append(".git + import/")
        if evidence:
            candidates.append(f"candidate: {candidate} ({', '.join(evidence)})")
    if len(markers) > 1:
        raise FlistError("E_ROOT_AMBIGUOUS", "multiple workspace markers; specify -w <root>", tuple(str(p) for p in markers))
    if markers:
        marker = markers[0] / STATE_DIR / "workspace.toml"
        if read_toml(marker, "workspace marker").get("schema_version") != 1:
            raise FlistError("E_ROOT_MARKER", f"unsupported workspace marker: {marker}")
        return markers[0], ".rtl_flist/workspace.toml"
    raise FlistError("E_ROOT_REQUIRED", "no workspace marker; specify -w <root> or initialize with --init-root -w <root>", tuple(candidates))


def workspace_selection(workspace_arg: str | None) -> tuple[Path, str]:
    if workspace_arg is not None:
        root = Path(workspace_arg).resolve()
        if not root.is_dir():
            raise FlistError("E_WORKSPACE", f"workspace directory not found: {root}")
        return root, "--workspace"
    return find_workspace_root(Path.cwd())


def command_root(args: argparse.Namespace) -> int:
    root, source = workspace_selection(args.workspace)
    if args.init_root:
        marker = root / STATE_DIR / "workspace.toml"
        marker.parent.mkdir(parents=True, exist_ok=True)
        if marker.exists():
            if read_toml(marker, "workspace marker").get("schema_version") != 1:
                raise FlistError("E_ROOT_MARKER", f"unsupported workspace marker: {marker}")
        else:
            with marker.open("x", encoding="utf-8") as stream:
                stream.write("schema_version = 1\n")
        source = ".rtl_flist/workspace.toml"
    print(f"root_dir: {root} ({source})")
    return 0


def iter_descriptors(
    workspace: Path,
    repositories: tuple[WorkspaceRepository, ...],
    skip_workspace_import: bool = True,
) -> list[tuple[Path, Path]]:
    result: list[tuple[Path, Path]] = []
    seen: set[Path] = set()
    for repository in repositories:
        for path in sorted(repository.root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file() or path.suffix not in {".toml", ".core"}:
                continue
            relative = path.relative_to(repository.root)
            if any(part in SKIP_DIRS for part in relative.parts):
                continue
            if skip_workspace_import and repository.root == workspace and relative.parts and relative.parts[0] == "import":
                continue
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                result.append((resolved, repository.root))
    return result


def parse_toml_core(path: Path, git_root: Path) -> Core | None:
    text = path.read_text(encoding="utf-8")
    if "[core]" not in text:
        return None
    data = read_toml(path, "core manifest")
    raw_core = data.get("core")
    if not isinstance(raw_core, dict):
        return None
    validate_keys(data, {"core", "fileset"}, "core manifest", path)
    validate_keys(raw_core, {"id", "filesets"}, "[core]", path)
    core_id = raw_core.get("id")
    if not isinstance(core_id, str) or not core_id:
        raise FlistError("E_MANIFEST", f"core.id must be a non-empty string: {path}")

    raw_filesets = data.get("fileset", {})
    if not isinstance(raw_filesets, dict) or not raw_filesets:
        raise FlistError("E_MANIFEST", f"core requires at least one [fileset.*]: {path}")
    filesets: dict[str, FileSet] = {}
    for name, raw in raw_filesets.items():
        if not isinstance(name, str) or not isinstance(raw, dict):
            raise FlistError("E_MANIFEST", f"invalid fileset in {path}")
        validate_keys(
            raw,
            {"dir", "files", "depend", "legacy_f"},
            f"[fileset.{name}]",
            path,
        )
        files = string_tuple(raw.get("files", []), f"fileset.{name}.files", path)
        legacy_f = string_optional(raw.get("legacy_f"), f"fileset.{name}.legacy_f", path)
        depend = string_tuple(raw.get("depend", []), f"fileset.{name}.depend", path)
        if any(has_first_marker(value) for value in depend):
            raise FlistError("E_MANIFEST", f"first: is not supported in fileset.{name}.depend: {path}")
        if legacy_f is not None and has_first_marker(legacy_f):
            raise FlistError("E_MANIFEST", f"first: is not supported in fileset.{name}.legacy_f: {path}")
        if not files and legacy_f is None and not depend:
            raise FlistError("E_MANIFEST", f"fileset '{name}' has no files, depend, or legacy_f: {path}")
        directory = string_optional(raw.get("dir"), f"fileset.{name}.dir", path)
        if directory is not None and (
            Path(directory).is_absolute() or PureWindowsPath(directory).drive or PureWindowsPath(directory).root
        ):
            raise FlistError("E_MANIFEST", f"fileset.{name}.dir must be relative to the TOML directory: {path}: {directory}")
        filesets[name] = FileSet(
            name=name,
            directory=directory,
            files=files,
            depend=depend,
            legacy_f=legacy_f,
        )

    selected = string_tuple(raw_core.get("filesets"), "core.filesets", path) or tuple(filesets)
    return Core(
        core_id=core_id,
        manifest=path,
        git_root=git_root,
        format_name="toml",
        filesets=filesets,
        selected_filesets=selected,
    )


def yaml_scalar(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def parse_capi2_core(path: Path, git_root: Path) -> Core:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        content = raw.split("#", maxsplit=1)[0].rstrip()
        if content.strip():
            lines.append((len(content) - len(content.lstrip()), content.strip()))
    if not lines or lines[0][1] != "CAPI=2:":
        raise FlistError("E_CORE", f"unsupported legacy .core format: {path}")

    name = next((yaml_scalar(text.split(":", maxsplit=1)[1]) for _, text in lines if text.startswith("name:")), None)
    if not name:
        raise FlistError("E_CORE", f"legacy .core has no name: {path}")

    def section_range(header: str) -> list[tuple[int, str]]:
        start = next((index for index, (_, text) in enumerate(lines) if text == f"{header}:"), None)
        if start is None:
            return []
        indent = lines[start][0]
        end = start + 1
        while end < len(lines) and lines[end][0] > indent:
            end += 1
        return lines[start + 1:end]

    filesets: dict[str, FileSet] = {}
    raw_filesets = section_range("filesets")
    index = 0
    while index < len(raw_filesets):
        indent, text = raw_filesets[index]
        if not text.endswith(":"):
            index += 1
            continue
        fileset_name = text[:-1]
        index += 1
        block: list[tuple[int, str]] = []
        while index < len(raw_filesets) and raw_filesets[index][0] > indent:
            block.append(raw_filesets[index])
            index += 1
        files: list[str] = []
        depend: list[str] = []
        in_files = False
        files_indent = 0
        in_depend = False
        depend_indent = 0
        for item_indent, item_text in block:
            if item_text == "files:":
                in_files = True
                files_indent = item_indent
                continue
            if item_text.startswith("depend:"):
                value = item_text.split(":", maxsplit=1)[1].strip()
                if value.startswith("[") and value.endswith("]"):
                    depend.extend(yaml_scalar(item.strip()) for item in value[1:-1].split(",") if item.strip())
                else:
                    in_depend = True
                    depend_indent = item_indent
                continue
            if in_files and item_indent <= files_indent:
                in_files = False
            if in_depend and item_indent <= depend_indent:
                in_depend = False
            if in_files and item_text.startswith("- "):
                files.append(yaml_scalar(item_text[2:].split(":", maxsplit=1)[0].strip()))
            if in_depend and item_text.startswith("- "):
                depend.append(yaml_scalar(item_text[2:]))
        if files or depend:
            filesets[fileset_name] = FileSet(fileset_name, None, tuple(files), tuple(depend), None)

    target_filesets: dict[str, tuple[str, ...]] = {}
    raw_targets = section_range("targets")
    index = 0
    while index < len(raw_targets):
        indent, text = raw_targets[index]
        if not text.endswith(":"):
            index += 1
            continue
        target_name = text[:-1]
        index += 1
        block: list[tuple[int, str]] = []
        while index < len(raw_targets) and raw_targets[index][0] > indent:
            block.append(raw_targets[index])
            index += 1
        selected: list[str] = []
        for _, item_text in block:
            if item_text.startswith("filesets:"):
                value = item_text.split(":", maxsplit=1)[1].strip()
                if value.startswith("[") and value.endswith("]"):
                    selected.extend(yaml_scalar(item.strip()) for item in value[1:-1].split(",") if item.strip())
        if selected:
            target_filesets[target_name] = tuple(selected)
    selected = target_filesets.get("default") or next(iter(target_filesets.values()), tuple(filesets))
    if not filesets:
        raise FlistError("E_CORE", f"unsupported CAPI2 filesets: {path}")
    return Core(name, path, git_root, "fusesoc-core", filesets, selected)


def scan_cores(
    workspace: Path,
    repositories: tuple[WorkspaceRepository, ...],
    skip_workspace_import: bool = True,
) -> dict[str, Core]:
    cores: dict[str, Core] = {}
    for descriptor, git_root in iter_descriptors(workspace, repositories, skip_workspace_import):
        core = parse_toml_core(descriptor, git_root) if descriptor.suffix == ".toml" else parse_capi2_core(descriptor, git_root)
        if core is None:
            continue
        previous = cores.get(core.core_id)
        if previous is not None:
            raise FlistError("E_CORE_ID_CONFLICT", f"duplicate core ID '{core.core_id}'", (str(previous.manifest), str(core.manifest)))
        cores[core.core_id] = core
    return cores


def core_index_path(workspace: Path) -> Path:
    return workspace / STATE_DIR / "core_index.toml"


def core_index_entries(cores: dict[str, Core]) -> dict[str, CoreIndexEntry]:
    return {
        core_id: CoreIndexEntry(core_id, core.manifest, core.git_root, core.format_name)
        for core_id, core in cores.items()
    }


def write_core_index(workspace: Path, cores: dict[str, Core]) -> Path:
    output = core_index_path(workspace)
    output.parent.mkdir(parents=True, exist_ok=True)
    import_root = workspace / "import"
    import_checkouts = [
        f"import/{item.name}"
        for item in sorted(import_root.iterdir(), key=lambda item: item.name)
        if item.is_dir()
    ] if import_root.is_dir() else []
    lines = [
        "schema_version = 1",
        f"generated_at = {toml_quote(datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S'))}",
        f"import_checkouts = {toml_quote(import_checkouts)}",
        "",
    ]
    for core_id in sorted(cores):
        core = cores[core_id]
        lines.extend((
            f"[core.{toml_quote(core_id)}]",
            f"manifest = {toml_quote(core.manifest.relative_to(workspace).as_posix())}",
            f"format = {toml_quote(core.format_name)}",
            f"git_root = {toml_quote(core.git_root.relative_to(workspace).as_posix() or '.')}",
            "",
        ))
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def resolve_index_path(workspace: Path, value: object, field: str, index: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise FlistError("E_CORE_CACHE", f"invalid {field} in {index}; run --rescan")
    path = (workspace / value).resolve()
    try:
        path.relative_to(workspace)
    except ValueError as exc:
        raise FlistError("E_CORE_CACHE", f"cached {field} escapes workspace in {index}; run --rescan") from exc
    return path


def read_core_index(workspace: Path) -> dict[str, CoreIndexEntry]:
    index = core_index_path(workspace)
    data = read_toml(index, "core index")
    if data.get("schema_version") != 1:
        raise FlistError("E_CORE_CACHE", f"unsupported core index schema: {index}; run --rescan")
    raw_cores = data.get("core")
    if not isinstance(raw_cores, dict):
        raise FlistError("E_CORE_CACHE", f"core index has no core entries: {index}; run --rescan")

    entries: dict[str, CoreIndexEntry] = {}
    for core_id, raw_entry in raw_cores.items():
        if not isinstance(core_id, str) or not isinstance(raw_entry, dict):
            raise FlistError("E_CORE_CACHE", f"invalid core entry in {index}; run --rescan")
        format_name = raw_entry.get("format")
        if not isinstance(format_name, str) or not format_name:
            raise FlistError("E_CORE_CACHE", f"invalid core format in {index}; run --rescan")
        entries[core_id] = CoreIndexEntry(
            core_id,
            resolve_index_path(workspace, raw_entry.get("manifest"), "manifest", index),
            resolve_index_path(workspace, raw_entry.get("git_root"), "git_root", index),
            format_name,
        )
    return entries


def load_cached_cores(workspace: Path, entries: dict[str, CoreIndexEntry]) -> dict[str, Core]:
    cores: dict[str, Core] = {}
    for core_id, entry in entries.items():
        if not entry.manifest.is_file():
            raise FlistError("E_CORE_CACHE", f"cached core manifest is missing: {entry.manifest}; run --rescan")
        if not entry.git_root.is_dir():
            raise FlistError("E_CORE_CACHE", f"cached Git root is missing: {entry.git_root}; run --rescan")
        core = parse_toml_core(entry.manifest, entry.git_root) if entry.manifest.suffix == ".toml" else parse_capi2_core(entry.manifest, entry.git_root)
        if core is None or core.core_id != core_id or core.format_name != entry.format_name:
            raise FlistError("E_CORE_CACHE", f"cached core entry changed: {entry.manifest}; run --rescan")
        cores[core_id] = core
    return cores


def load_or_scan_core_index(
    workspace: Path,
    repositories: tuple[WorkspaceRepository, ...],
    rescan: bool,
) -> tuple[dict[str, CoreIndexEntry], str]:
    index = core_index_path(workspace)
    if index.is_file() and not rescan:
        return read_core_index(workspace), "cache"
    cores = scan_cores(workspace, repositories)
    if not cores:
        raise FlistError("E_CORE_NOT_FOUND", f"no core manifests found under {workspace}")
    write_core_index(workspace, cores)
    return core_index_entries(cores), "rescan" if rescan else "scan"


def condition_value(value: str, active_flags: frozenset[str], source: Path) -> str | None:
    match = CONDITION_RE.match(value)
    if match is None:
        return value
    condition = match.group("condition").strip()
    result = match.group("value").strip()
    if not condition or not result:
        raise FlistError("E_FLAG", f"invalid conditional value in {source}: {value}")
    for group in condition.split("||"):
        terms = group.split("&&")
        if all(_condition_term(term.strip(), active_flags, value, source) for term in terms):
            return result
    return None


def _condition_term(term: str, active_flags: frozenset[str], value: str, source: Path) -> bool:
    matched = re.fullmatch(r"(?P<neg>!)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)", term)
    if matched is None:
        raise FlistError("E_FLAG", f"invalid flag expression in {source}: {value}")
    enabled = matched.group("name") in active_flags
    return not enabled if matched.group("neg") else enabled


def substitute_variables(value: str, variables: dict[str, str], source: Path, preserve_unknown: bool = False) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group("braced") or match.group("plain")
        assert name is not None
        replacement = variables.get(name)
        if replacement is None:
            if preserve_unknown:
                return match.group(0)
            raise FlistError("E_VARIABLE", f"undefined variable '{name}' in {source}")
        return replacement
    return VARIABLE_RE.sub(replace, value)


def resolve_local_path(value: str, base: Path, variables: dict[str, str], source: Path) -> Path:
    path = Path(substitute_variables(value, variables, source))
    result = path.resolve() if path.is_absolute() else (base / path).resolve()
    return result


def resolve_legacy_path(value: str, base: Path, variables: dict[str, str], source: Path) -> Path:
    path = Path(substitute_variables(value, variables, source))
    return path.resolve() if path.is_absolute() else (base / path).resolve()


class Resolver:
    def __init__(self, workspace: Path, cores: dict[str, Core], mode: str, variables: dict[str, str], cached_index: bool) -> None:
        self.workspace = workspace
        self.cores = cores
        self.mode = mode
        self.active_flags = MODE_FLAGS[mode]
        self.legacy_variables = variables
        self.variables = dict(os.environ) | variables
        self.cached_index = cached_index
        self.first_lines: list[OutputLine] = []
        self.lines: list[OutputLine] = []
        self.emitted_files: dict[Path, tuple[OutputLine, bool]] = {}
        self.first_path_by_name: dict[str, Path] = {}
        self.warned_file_names: set[str] = set()
        self.emitted_options: set[tuple[str, str]] = set()
        self.visited: set[str] = set()
        self.active: list[str] = []
        self.tree_edges: list[tuple[str, str]] = []

    def resolve(self, top_core: str) -> tuple[OutputLine, ...]:
        self.resolve_core(top_core)
        return tuple((*self.first_lines, *self.lines))

    def resolve_core(self, core_id: str) -> None:
        if core_id in self.active:
            cycle = (*self.active[self.active.index(core_id):], core_id)
            raise FlistError("E_CORE_CYCLE", "core dependency cycle detected", (" -> ".join(cycle),))
        core = self.cores.get(core_id)
        if core is None:
            if self.cached_index:
                raise FlistError("E_CORE_NOT_FOUND", f"core '{core_id}' is absent from cached core index; run --rescan")
            raise FlistError("E_CORE_NOT_FOUND", f"core '{core_id}' was not found")
        if core_id in self.visited:
            return
        self.active.append(core_id)
        for fileset_value in core.selected_filesets:
            fileset_name = condition_value(fileset_value, self.active_flags, core.manifest)
            if fileset_name is not None:
                fileset_name, first_fileset = split_first_marker(fileset_name, core.manifest)
                self.resolve_fileset(core, fileset_name, first_fileset)
        self.active.pop()
        self.visited.add(core_id)

    def resolve_fileset(self, core: Core, fileset_name: str, first_fileset: bool) -> None:
        fileset = core.filesets.get(fileset_name)
        if fileset is None:
            raise FlistError("E_FILESET", f"core '{core.core_id}' has no fileset '{fileset_name}'")
        for dependency_value in fileset.depend:
            self.resolve_dependency(core, dependency_value)
        base = core.manifest.parent / (fileset.directory or ".")
        base = base.resolve()
        for file_name in fileset.files:
            selected = condition_value(file_name, self.active_flags, core.manifest)
            if selected is not None:
                selected, first_file = split_first_marker(selected, core.manifest)
                self.emit_file(
                    resolve_local_path(selected, base, self.variables, core.manifest),
                    core,
                    first_fileset or first_file,
                )
        if fileset.legacy_f is not None:
            selected = condition_value(fileset.legacy_f, self.active_flags, core.manifest)
            if selected is not None:
                selected = substitute_variables(selected, self.legacy_variables, core.manifest, preserve_unknown=True)
                if VARIABLE_RE.search(selected):
                    self.emit_option("raw", "-f " + selected, core)
                    return
                self.resolve_legacy_f(
                    resolve_legacy_path(selected, base, self.variables, core.manifest),
                    core,
                )

    def resolve_dependency(self, parent: Core, dependency_value: str) -> None:
        dependency_id = condition_value(dependency_value, self.active_flags, parent.manifest)
        if dependency_id is None:
            return
        if has_first_marker(dependency_id):
            raise FlistError("E_FIRST", f"first: is not supported in depend: {parent.manifest}")
        self.tree_edges.append((parent.core_id, dependency_id))
        self.resolve_core(dependency_id)

    def resolve_legacy_f(self, path: Path, core: Core, stack: tuple[Path, ...] = ()) -> None:
        path = path.resolve()
        if path in stack:
            raise FlistError("E_LEGACY_CYCLE", "legacy_f include cycle", tuple(str(p) for p in (*stack, path)))
        try:
            raw_lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise FlistError("E_LEGACY_F", f"failed to read legacy_f: {path}", (str(exc),)) from exc
        for raw in raw_lines:
            line = raw.split("#", maxsplit=1)[0].strip()
            if not line or line.startswith("//"):
                continue
            line = substitute_variables(line, self.legacy_variables, path, preserve_unknown=True)
            if line.startswith(("-y", "+libext+", "-work", "-L ")):
                raise FlistError("E_LEGACY_F", f"unsupported legacy_f option in {path}: {line}")
            if VARIABLE_RE.search(line):
                self.emit_option("raw", line, core)
                continue
            if line.startswith("+incdir+"):
                for item in line[len("+incdir+"):].split("+"):
                    if item:
                        self.emit_option("incdir", str(resolve_legacy_path(item, path.parent, self.variables, path)), core)
                continue
            if line.startswith("+define+"):
                for item in line[len("+define+"):].split("+"):
                    if item:
                        self.emit_option("define", substitute_variables(item, self.variables, path), core)
                continue
            if line.startswith(("-f ", "-F ", "-f\t", "-F\t")):
                self.resolve_legacy_f(
                    resolve_legacy_path(line[3:].strip(), path.parent, self.variables, path),
                    core, (*stack, path),
                )
                continue
            if line in {"-f", "-F"}:
                raise FlistError("E_LEGACY_F", f"{line} requires one filelist in {path}")
            if line == "-v" or line.startswith(("-v ", "-v\t")):
                value = line[2:].strip()
                if not value:
                    raise FlistError("E_LEGACY_F", f"-v requires one Verilog file in {path}")
                library = resolve_legacy_path(value, path.parent, self.variables, path)
                if not library.is_file():
                    raise FlistError("E_FILE_MISSING", f"Verilog library file not found: {library}")
                self.emit_option("vfile", str(library), core)
                continue
            if line.startswith(("-y", "+libext+", "-work", "-L ")):
                raise FlistError("E_LEGACY_F", f"unsupported legacy_f option in {path}: {line}")
            self.emit_file(resolve_legacy_path(line, path.parent, self.variables, path), core, False)

    def emit_option(self, kind: str, value: str, core: Core) -> None:
        key = (kind, value)
        if key in self.emitted_options:
            return
        self.emitted_options.add(key)
        self.lines.append(OutputLine(kind, value, core.git_root, core.core_id, core.manifest))

    def emit_file(self, path: Path, core: Core, first_output: bool) -> None:
        if not path.is_file():
            raise FlistError("E_FILE_MISSING", f"RTL file not found: {path}", (f"core: {core.core_id}",))
        self._emit_file(path, core.git_root, core.core_id, core.manifest, first_output)


    def _emit_file(self, path: Path, root: Path | None, core_id: str, manifest: Path, first_output: bool) -> None:
        previous = self.emitted_files.get(path)
        if previous is not None:
            line, previous_first = previous
            if first_output and not previous_first:
                self.lines.remove(line)
                self.first_lines.append(line)
                self.emitted_files[path] = (line, True)
            return
        first_path = self.first_path_by_name.setdefault(path.name, path)
        if first_path != path and path.name not in self.warned_file_names:
            self.warned_file_names.add(path.name)
            print(
                f"WARNING [W_FILE_NAME_CONFLICT]: '{path.name}' appears in multiple paths: "
                f"{first_path.as_posix()} ; {path.as_posix()}",
                file=sys.stderr,
            )
        line = OutputLine("file", str(path), root, core_id, manifest)
        self.emitted_files[path] = (line, first_output)
        (self.first_lines if first_output else self.lines).append(line)

    def tree_text(self, top_core: str) -> str:
        children: dict[str, list[str]] = {}
        for parent, child in self.tree_edges:
            children.setdefault(parent, []).append(child)
        lines = [top_core]
        seen = {top_core}

        def append_children(parent: str, prefix: str) -> None:
            entries = children.get(parent, [])
            for index, child in enumerate(entries):
                last = index == len(entries) - 1
                connector = "`-- " if last else "|-- "
                shared = child in seen
                suffix = " [shared]" if shared else ""
                lines.append(f"{prefix}{connector}{child}{suffix}")
                if not shared:
                    seen.add(child)
                    append_children(child, prefix + ("    " if last else "|   "))

        append_children(top_core, "")
        return "\n".join(lines) + "\n"


def parse_variables(values: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise FlistError("E_VARIABLE", f"--var requires NAME=VALUE: {value}")
        name, content = value.split("=", maxsplit=1)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or not content:
            raise FlistError("E_VARIABLE", f"invalid --var value: {value}")
        variables[name] = content
    return variables


def render_flist(lines: tuple[OutputLine, ...]) -> str:
    chunks = []
    for line in lines:
        if line.kind == "raw":
            value = line.value
        elif line.kind == "define":
            value = "+define+" + line.value
        else:
            prefix = {"file": "", "incdir": "+incdir+", "vfile": "-v "}[line.kind]
            value = prefix + Path(line.value).as_posix()
        chunks.append(value if value.endswith("\n") else value + "\n")
    return "".join(chunks)


def build_resolver(
    workspace_arg: str,
    mode: str,
    variables: dict[str, str],
    rescan: bool,
) -> tuple[Path, dict[str, Core], Resolver, str]:
    workspace, repositories = load_workspace(workspace_arg)
    entries, cache_source = load_or_scan_core_index(workspace, repositories, rescan)
    cores = load_cached_cores(workspace, entries)
    return workspace, cores, Resolver(workspace, cores, mode, variables, cache_source == "cache"), cache_source


def core_from_name(name: str, cores: dict[str, Core]) -> Core:
    if name in cores:
        return cores[name]
    matches = sorted(
        (core for core in cores.values() if ":" not in name and core.core_id.split(":")[2:3] == [name]),
        key=lambda core: core.core_id,
    )
    if not matches:
        raise FlistError("E_CORE_NOT_FOUND", f"core ID/name not found: {name}; use --list-core --all or --rescan")
    if len(matches) > 1:
        raise FlistError("E_CORE_AMBIGUOUS", f"core name '{name}' is ambiguous; use a full core ID", tuple(
            f"  {core.core_id}  {core.manifest}" for core in matches
        ))
    return matches[0]


def command_generate(args: argparse.Namespace) -> int:
    root, root_source = workspace_selection(args.workspace)
    print(f"root_dir: {root} ({root_source})")
    workspace, cores, resolver, cache_source = build_resolver(str(root), args.mode, parse_variables(args.variables), args.rescan)
    core = core_from_name(args.core, cores)
    output = Path(args.output).resolve()
    lines = resolver.resolve(core.core_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_flist(lines), encoding="utf-8")
    (workspace / STATE_DIR / "core_tree.txt").write_text(resolver.tree_text(core.core_id), encoding="utf-8")
    print(f"core_index: {core_index_path(workspace)} ({cache_source})")
    print(f"resolved {len(lines)} line(s): {output}")
    return 0


def command_list_core(args: argparse.Namespace) -> int:
    if args.directory:
        directory = Path(args.directory).resolve()
        if not directory.is_dir():
            raise FlistError("E_DIRECTORY", f"core directory not found: {directory}")
        repositories = (WorkspaceRepository("query", directory, "."),)
        cores = scan_cores(directory, repositories, skip_workspace_import=False)
        display_root = directory
        root_source = "--directory"
    else:
        root, root_source = workspace_selection(args.workspace)
        print(f"root_dir: {root} ({root_source})")
        workspace, repositories = load_workspace(str(root))
        entries, cache_source = load_or_scan_core_index(workspace, repositories, args.rescan)
        cores = {
            core_id: entry
            for core_id, entry in entries.items()
            if args.all or entry.git_root == workspace
        }
        display_root = workspace
    if args.directory:
        print(f"root_dir: {display_root} ({root_source})")
    if not args.directory:
        print(f"core_index: {core_index_path(display_root)} ({cache_source})")
    for core_id in sorted(cores):
        core = cores[core_id]
        print(f"{core_id:<40}  {core.manifest.relative_to(display_root).as_posix()}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a deterministic RTL filelist from a core ID or unique name.")
    parser.add_argument("--version", action="version", version="rtl_flist_mgr 0.11.0")
    parser.add_argument("--core", help="full core ID or unique name (third ID segment)")
    parser.add_argument("-w", "--workspace", help="workspace root; import/* directories are scanned as checkout roots")
    parser.add_argument("-m", "--mode", choices=tuple(MODE_FLAGS), default="sim", help="output mode, default: sim")
    parser.add_argument("--var", dest="variables", action="append", default=[], help="legacy path variable NAME=VALUE")
    parser.add_argument("-o", "--output", help="generated filelist path")
    parser.add_argument("--show-root", action="store_true", help="show root without scanning or writing state")
    parser.add_argument("--init-root", action="store_true", help="create workspace marker; requires -w")
    parser.add_argument("--rescan", action="store_true", help="rescan workspace corefiles and overwrite .rtl_flist/core_index.toml")
    parser.add_argument("-d", "--directory", help="directory for --list-core; recursively list core IDs below it")
    parser.add_argument("--list-core", action="store_true", help="list workspace core IDs outside import/")
    parser.add_argument("--all", action="store_true", help="include import/ cores with --list-core")
    args = parser.parse_args(argv)
    if args.show_root or args.init_root:
        if args.show_root and args.init_root:
            parser.error("--show-root and --init-root are mutually exclusive")
        if args.core or args.output or args.list_core or args.directory or args.all or args.rescan or args.variables:
            parser.error("root commands do not accept generation or listing options")
        if args.init_root and args.workspace is None:
            parser.error("--init-root requires -w <root>")
    elif args.list_core:
        if args.core is not None or args.output is not None:
            parser.error("--list-core does not accept --core or --output")
        if args.all and args.directory is not None:
            parser.error("--all and --directory cannot be used together")
        if args.directory is not None and args.workspace is not None:
            parser.error("--directory and --workspace cannot be used together with --list-core")
        if args.directory is not None and args.rescan:
            parser.error("--rescan cannot be used with --directory")
    elif args.core is None or args.output is None:
        parser.error("--core and --output are required unless --list-core is used")
    elif args.directory is not None:
        parser.error("--directory requires --list-core")
    elif args.all:
        parser.error("--all requires --list-core")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.show_root or args.init_root:
            return command_root(args)
        return command_list_core(args) if args.list_core else command_generate(args)
    except FlistError as exc:
        print(f"ERROR [{exc.code}]: {exc.message}", file=sys.stderr)
        for detail in exc.details:
            print(detail, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
