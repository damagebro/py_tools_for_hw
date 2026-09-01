#!/usr/bin/env python3
"""Build a self-contained, source-based hw_tool release directory."""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Mapping


HW_TOOL_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = HW_TOOL_ROOT.parent
OUTPUT_ROOT = HW_TOOL_ROOT / "publish" / "out"
TOOL_REGISTRY_PATH = HW_TOOL_ROOT / "hw_tool_de" / "src" / "tool_registry.py"


def load_tool_registry() -> object:
    module_name = "_hw_tool_release_registry"
    spec = importlib.util.spec_from_file_location(module_name, TOOL_REGISTRY_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load tool registry: {TOOL_REGISTRY_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


TOOL_REGISTRY = load_tool_registry()
REPOSITORY_MAP = TOOL_REGISTRY.REPOSITORY_MAP
RepositorySpec = TOOL_REGISTRY.RepositorySpec


PY_TOOLS_PATHS = (
    "csr_tool",
    "gen_rtl_dummy",
    "gen_rtl_inst",
    "git_repo_mgr",
    "py_md2html",
    "py_rtl_sim/gen_tb_demo",
    "rtl_flist_mgr",
)
EXTERNAL_REPOSITORY_PATHS = {
    "com": ("impl_template/memory/mem_tool",),
}


@dataclass(frozen=True)
class ResolvedRepository:
    name: str
    root: Path
    source: str
    repository: str
    ref: str
    commit: str
    dirty: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a standalone source release of hw_tool."
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Release version used in the output directory name.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=OUTPUT_ROOT,
        help="Parent directory for the generated release (default: publish/out).",
    )
    parser.add_argument(
        "--repo-ref",
        action="append",
        default=[],
        metavar="NAME=REF",
        help="Override an external repository branch, tag, or commit.",
    )
    parser.add_argument(
        "--repo-path",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Use a local repository checkout instead of cloning its URL.",
    )
    parser.add_argument(
        "--shallow",
        action="store_true",
        help="Fetch only the selected external repository revision.",
    )
    parser.add_argument(
        "--linux-install-root",
        default="/tools/hw_tool",
        help="Linux install root embedded in the generated modulefile.",
    )
    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Create only the release directory; do not create a zip archive.",
    )
    return parser.parse_args()


def parse_named_values(values: list[str], option: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    valid_names = set(EXTERNAL_REPOSITORY_PATHS)
    for value in values:
        name, separator, item = value.partition("=")
        if not separator or not name.strip() or not item.strip():
            raise ValueError(f"{option} expects NAME=VALUE: {value}")
        name = name.strip()
        if name not in valid_names:
            raise ValueError(f"{option} references unknown repository: {name}")
        if name in parsed:
            raise ValueError(f"{option} repeats repository: {name}")
        parsed[name] = item.strip()
    return parsed


def ignore_hw_tool_copy(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    current = Path(directory).resolve()
    if current == HW_TOOL_ROOT:
        ignored.update({"groups", "repository"})
    if current == HW_TOOL_ROOT / "publish":
        ignored.add("out")
    if current == HW_TOOL_ROOT / "publish" / "vscode":
        ignored.update({"node_modules", "out", "runtime"})
    ignored.update(name for name in names if name == "__pycache__" or name.endswith(".pyc"))
    return ignored


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"release source does not exist: {source}")
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".rtl_flist",
            "__pycache__",
            "*.pyc",
            "_work",
            "out",
        ),
    )


def remove_readonly(function: object, path: str, exception: tuple[object, object, object]) -> None:
    del exception
    os.chmod(path, stat.S_IWRITE)
    function(path)


def run_git(arguments: list[str], cwd: Path | None = None) -> str:
    command = ["git", *arguments]
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"git command failed ({' '.join(command)}): {detail}")
    return result.stdout.strip()


def repository_state(root: Path) -> tuple[str, bool]:
    if not root.is_dir():
        raise FileNotFoundError(f"repository path does not exist: {root}")
    commit = run_git(["rev-parse", "HEAD"], root)
    dirty = bool(run_git(["status", "--porcelain"], root))
    return commit, dirty


def clone_repository(repository: str, ref: str, destination: Path, shallow: bool) -> None:
    if shallow:
        destination.mkdir(parents=True)
        run_git(["init", "--quiet"], destination)
        run_git(["remote", "add", "origin", repository], destination)
        run_git(["fetch", "--quiet", "--depth", "1", "origin", ref], destination)
        run_git(["checkout", "--quiet", "--detach", "FETCH_HEAD"], destination)
        return

    run_git(["clone", "--quiet", "--no-checkout", repository, str(destination)])
    candidates = (ref, f"origin/{ref}")
    commit = ""
    for candidate in candidates:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{candidate}^{{commit}}"],
            cwd=destination,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            break
    if not commit:
        raise ValueError(f"repository ref does not exist: {repository} @ {ref}")
    run_git(["checkout", "--quiet", "--detach", commit], destination)


@contextmanager
def resolve_external_repository(
    spec: RepositorySpec,
    ref: str,
    local_path: Path | None,
    shallow: bool,
) -> Iterator[ResolvedRepository]:
    if local_path is not None:
        root = local_path.expanduser().resolve()
        commit, dirty = repository_state(root)
        yield ResolvedRepository(
            name=spec.name,
            root=root,
            source="path",
            repository=spec.repository,
            ref="working-tree",
            commit=commit,
            dirty=dirty,
        )
        return

    with tempfile.TemporaryDirectory(prefix=f"hw_tool_{spec.name}_") as temporary_directory:
        root = Path(temporary_directory) / spec.name
        clone_repository(spec.repository, ref, root, shallow)
        commit, dirty = repository_state(root)
        yield ResolvedRepository(
            name=spec.name,
            root=root,
            source="url",
            repository=spec.repository,
            ref=ref,
            commit=commit,
            dirty=dirty,
        )


def workspace_repository() -> ResolvedRepository:
    spec = REPOSITORY_MAP["py_tools_for_hw"]
    commit, dirty = repository_state(SOURCE_ROOT)
    return ResolvedRepository(
        name=spec.name,
        root=SOURCE_ROOT,
        source="workspace",
        repository=spec.repository,
        ref="working-tree",
        commit=commit,
        dirty=dirty,
    )


def toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def write_release_info(
    path: Path,
    version: str,
    repositories: list[ResolvedRepository],
) -> None:
    lines = [
        "[release]",
        f'version = "{toml_string(version)}"',
        f'built_at = "{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"',
    ]
    for repository in repositories:
        lines.extend([
            "",
            f'[repository.{repository.name}]',
            f'source = "{repository.source}"',
            f'url = "{toml_string(repository.repository)}"',
            f'ref = "{toml_string(repository.ref)}"',
            f'commit = "{repository.commit}"',
            f"dirty = {str(repository.dirty).lower()}",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_linux_modulefile(
    release_root: Path,
    version: str,
    linux_install_root: str,
) -> Path:
    install_root = linux_install_root.rstrip("/") or "/"
    tool_root = (
        f"/{version}/hw_tool"
        if install_root == "/"
        else f"{install_root}/{version}/hw_tool"
    )
    modulefile = release_root / "modulefiles" / "hw_tool" / version
    modulefile.parent.mkdir(parents=True, exist_ok=True)
    modulefile.write_text(
        "#%Module\n"
        f'module-whatis "Hardware development tool hub {version}"\n\n'
        f"set root {tool_root}\n"
        "prepend-path PATH $root/bin\n"
        "setenv HW_TOOL_HOME $root\n"
        f"setenv HW_TOOL_VERSION {version}\n",
        encoding="utf-8",
    )
    return modulefile


def build_release(
    version: str,
    output_root: Path,
    create_archive: bool,
    repository_refs: Mapping[str, str] | None = None,
    repository_paths: Mapping[str, Path] | None = None,
    shallow: bool = False,
    linux_install_root: str = "/tools/hw_tool",
) -> tuple[Path, Path | None]:
    repository_refs = repository_refs or {}
    repository_paths = repository_paths or {}
    release_root = output_root.resolve() / f"hw_tool-{version}"
    tool_root = release_root / "hw_tool"

    with ExitStack() as stack:
        external_repositories: dict[str, ResolvedRepository] = {}
        for name in EXTERNAL_REPOSITORY_PATHS:
            spec = REPOSITORY_MAP[name]
            resolved = stack.enter_context(resolve_external_repository(
                spec,
                repository_refs.get(name, spec.branch),
                repository_paths.get(name),
                shallow,
            ))
            external_repositories[name] = resolved

        if release_root.exists():
            shutil.rmtree(release_root, onerror=remove_readonly)
        shutil.copytree(HW_TOOL_ROOT, tool_root, ignore=ignore_hw_tool_copy)
        repository_root = tool_root / "repository"

        for relative_path in PY_TOOLS_PATHS:
            copy_tree(
                SOURCE_ROOT / relative_path,
                repository_root / "py_tools_for_hw" / relative_path,
            )
        for name, relative_paths in EXTERNAL_REPOSITORY_PATHS.items():
            for relative_path in relative_paths:
                copy_tree(
                    external_repositories[name].root / relative_path,
                    repository_root / name / relative_path,
                )

        repositories = [workspace_repository(), *external_repositories.values()]
        write_release_info(tool_root / "release_info.toml", version, repositories)
        write_linux_modulefile(release_root, version, linux_install_root)

    archive_path = None
    if create_archive:
        archive_path = Path(
            shutil.make_archive(str(release_root), "zip", root_dir=release_root)
        )
    return tool_root, archive_path


def main() -> int:
    args = parse_args()
    try:
        repository_refs = parse_named_values(args.repo_ref, "--repo-ref")
        repository_paths = {
            name: Path(value)
            for name, value in parse_named_values(args.repo_path, "--repo-path").items()
        }
        tool_root, archive_path = build_release(
            args.version,
            args.output_root,
            not args.no_archive,
            repository_refs=repository_refs,
            repository_paths=repository_paths,
            shallow=args.shallow,
            linux_install_root=args.linux_install_root,
        )
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    modulefile = tool_root.parent / "modulefiles" / "hw_tool" / args.version
    print(f"[OK] source release: {tool_root}")
    print(f"[OK] Linux modulefile: {modulefile}")
    if archive_path is not None:
        print(f"[OK] source archive: {archive_path}")
    print(
        "[INFO] Python 3.11+ with jinja2, openpyxl, and Markdown "
        "is required on the target host."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
