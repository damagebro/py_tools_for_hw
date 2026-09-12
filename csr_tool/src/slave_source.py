"""Resolve Git-backed slave documents into immutable local snapshots."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit
import zipfile

from .reg_common import CSRValidationError


def parse_base_sources(rows: list[tuple[str, object]], label: str) -> list[dict[str, str]]:
    sources = []
    for key, value in rows:
        key = str(key).strip().lower()
        if key not in {"slave_dir", "slave_git"}:
            continue
        text = str(value or "").strip()
        if not text or text == "-":
            continue
        if key == "slave_dir":
            if not Path(text).is_absolute():
                raise CSRValidationError(f"{label}: slave_dir must be an absolute directory")
            sources.append({"directory": text})
            continue
        options = {}
        for part in text.split(","):
            name, separator, setting = part.partition("=")
            name, setting = name.strip().lower(), setting.strip()
            if not separator or name not in {"url", "path", "ref"} or not setting:
                raise CSRValidationError(f"{label}: slave_git expects url=..., path=..., ref=...")
            if name in options:
                raise CSRValidationError(f"{label}: duplicate slave_git attribute '{name}'")
            options[name] = setting
        if "url" not in options:
            raise CSRValidationError(f"{label}: slave_git requires url")
        SlaveSources.validate(options["url"], options.get("ref", "HEAD"), options.get("path", "."))
        source = {"git_url": options["url"]}
        if "ref" in options:
            source["git_ref"] = options["ref"]
        if "path" in options:
            source["path"] = options["path"]
        sources.append(source)
    return sources


def source_rows(sources: list[dict[str, str]]) -> list[list[str]]:
    rows = []
    for source in sources:
        if "directory" in source:
            rows.append(["slave_dir", source["directory"], "-"])
        else:
            parts = [f"url={source['git_url']}"]
            if "path" in source:
                parts.append(f"path={source['path']}")
            if "git_ref" in source:
                parts.append(f"ref={source['git_ref']}")
            rows.append(["slave_git", ", ".join(parts), "-"])
    return rows


class SlaveSources:
    def __init__(self, cache: Path, sources=None):
        self.cache = cache.resolve()
        self.repositories: dict[tuple[str, str], Path] = {}
        self.sources = list(sources or [])
        self.index: dict[str, set[Path]] | None = None
        self._root_indexes: dict[Path, dict[str, set[Path]]] = {}
        for source in self.sources:
            if not isinstance(source, dict) or any(not isinstance(v, str) or not v.strip() for v in source.values()):
                raise CSRValidationError("Each slave source must contain nonempty string settings")
            if "directory" in source:
                if set(source) != {"directory"} or not Path(source["directory"]).is_absolute():
                    raise CSRValidationError("directory must be an absolute local directory, without Git settings")
            else:
                if not source.get("git_url") or set(source) - {"git_url", "git_ref", "path"}:
                    raise CSRValidationError("Git slave source requires git_url; optional git_ref and path")
                self.validate(source["git_url"], source.get("git_ref", "HEAD"), source.get("path", "."))

    def reset(self):
        self.repositories.clear()
        self.index = None
        self._root_indexes.clear()

    def scoped(self, sources: list[dict[str, str]]) -> SlaveSources:
        if not sources:
            return self
        child = SlaveSources(self.cache, self.sources + sources)
        child.repositories = self.repositories
        child._root_indexes = self._root_indexes
        return child

    @staticmethod
    def validate_filename(filename: str):
        if not filename or any(c in filename for c in "/\\:") or filename in {".", ".."}:
            raise CSRValidationError("slv_filename must contain only a filename; configure slave_dir/slave_git in base_info")
        if Path(filename).suffix.lower() not in {".md", ".xlsx"}:
            raise CSRValidationError("slv_filename must be an .md or .xlsx filename")

    def resolve(self, filename: str, parent: Path) -> Path:
        self.validate_filename(filename)
        direct = (parent.parent / filename).resolve()
        if direct.is_file():
            for root in self.repositories.values():
                if parent.is_relative_to(root) and not direct.is_relative_to(root):
                    raise CSRValidationError("Slave file escapes downloaded repository")
            return direct
        if self.index is None:
            self.index = {}
            roots = set()
            for source in self.sources:
                if "directory" in source:
                    root = Path(source["directory"]).resolve()
                else:
                    checkout = self.checkout(source["git_url"], source.get("git_ref", "HEAD"))
                    root = (checkout / source.get("path", ".").replace("\\", "/")).resolve()
                    if not root.is_relative_to(checkout):
                        raise CSRValidationError("Git search path escapes downloaded repository")
                if not root.is_dir():
                    raise CSRValidationError(f"Slave search directory not found: {root}")
                roots.add(root)
            def fail(error):
                raise error
            for root in sorted(roots):
                if root not in self._root_indexes:
                    index: dict[str, set[Path]] = {}
                    for directory, children, files in os.walk(root, onerror=fail):
                        children[:] = sorted(n for n in children if n not in {".git", ".csr_tool", "__pycache__"})
                        for name in files:
                            if Path(name).suffix.lower() not in {".md", ".xlsx"}:
                                continue
                            path = (Path(directory) / name).resolve()
                            if path.is_relative_to(root) and path.is_file():
                                index.setdefault(name, set()).add(path)
                    self._root_indexes[root] = index
                for name, paths in self._root_indexes[root].items():
                    self.index.setdefault(name, set()).update(paths)
        matches = sorted(self.index.get(filename, set()))
        if not matches:
            raise FileNotFoundError(f"{parent.name}: slave file not found: {filename}; searched same directory and configured sources")
        if len(matches) != 1:
            raise CSRValidationError(f"{parent.name}: ambiguous slave filename '{filename}':\n" + "\n".join(str(p) for p in matches))
        return matches[0]

    @staticmethod
    def validate(url: str, ref: str, filename: str) -> None:
        parsed = urlsplit(url)
        scp = re.fullmatch(r"[\w.-]+@[\w.-]+:[^\s]+", url)
        if not scp and parsed.scheme not in {"https", "http", "ssh", "file"}:
            raise CSRValidationError("git_url must use HTTP(S), SSH, or file://")
        if parsed.password or parsed.query or parsed.fragment or (
            parsed.scheme in {"https", "http"} and parsed.username
        ):
            raise CSRValidationError("git_url must not contain credentials, query, or fragment; use Git authentication")
        if ref.startswith("-") or any(c.isspace() for c in ref):
            raise CSRValidationError("git_ref must be a branch, tag, or commit ID")
        path = Path(filename.replace("\\", "/"))
        if PurePosixPath(filename.replace("\\", "/")).is_absolute() or PureWindowsPath(filename).drive or ".." in path.parts:
            raise CSRValidationError("Git source path must be repository-relative without '..'")

    @staticmethod
    def git(directory: Path, *args: str) -> str:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
        try:
            result = subprocess.run(
                ["git", "-c", "core.hooksPath=/dev/null", "-C", str(directory), *args],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=120, env=env,
            )
        except FileNotFoundError as exc:
            raise CSRValidationError("Git is required for git_url slave references") from exc
        except subprocess.TimeoutExpired as exc:
            raise CSRValidationError("Git slave download timed out (120 seconds)") from exc
        if result.returncode:
            raise CSRValidationError(f"Git slave download failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def checkout(self, url: str, ref: str) -> Path:
        ref = ref or "HEAD"
        self.validate(url, ref, ".")
        key = (url, ref)
        if key not in self.repositories:
            self.cache.mkdir(parents=True, exist_ok=True)
            repository = self.cache / hashlib.sha256(url.encode()).hexdigest()
            repository.mkdir(exist_ok=True)
            # A private bare fetch avoids changing any developer checkout. Export
            # each commit once, so another invocation cannot change active files.
            work = Path(tempfile.mkdtemp(prefix="fetch-", dir=repository))
            try:
                self.git(work, "init", "--bare")
                self.git(work, "fetch", "--depth=1", "--", url, ref)
                commit = self.git(work, "rev-parse", "--verify", "FETCH_HEAD^{commit}")
                snapshot = repository / commit
                if not snapshot.exists():
                    archive = work / "source.zip"
                    self.git(work, "archive", "--format=zip", f"--output={archive}", commit)
                    exported = work / "export"
                    exported.mkdir()
                    with zipfile.ZipFile(archive) as source:
                        for item in source.infolist():
                            target = (exported / item.filename).resolve()
                            if not target.is_relative_to(exported) or PureWindowsPath(item.filename).drive:
                                raise CSRValidationError("Unsafe path in Git archive")
                            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                                raise CSRValidationError("Symlinks are not supported in Git slave repositories")
                        source.extractall(exported)
                    try:
                        exported.rename(snapshot)
                    except OSError:
                        if not snapshot.is_dir():
                            raise
                self.repositories[key] = snapshot
            finally:
                def remove_readonly(function, path, error):
                    if not isinstance(error[1], PermissionError):
                        raise error[1]
                    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                    function(path)

                shutil.rmtree(work, onerror=remove_readonly)
        return self.repositories[key]
