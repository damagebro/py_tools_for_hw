from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolSpec:
    name: str
    script: str
    description: str
    usage: str
    kind: str = "script"
    tool_home: str | None = None
    source: str = "local"
    repository: str | None = None
    branch: str | None = None
    doc_url: str | None = None
    readme: str | None = None
    checkout: str | None = None
    repository_name: str | None = None


@dataclass(frozen=True)
class RepositorySpec:
    name: str
    repository: str
    branch: str
    checkout: str
    workspace: str | None = None


def config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "groups.toml"


def load_tool_specs() -> tuple[ToolSpec, ...]:
    try:
        config = tomllib.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(f"failed to load group config: {exc}") from exc

    groups = config.get("group")
    if not isinstance(groups, dict) or not groups:
        raise RuntimeError("group config must define at least one [group.<name>] section")

    specs: list[ToolSpec] = []
    for name, item in groups.items():
        if not isinstance(item, dict):
            raise RuntimeError(f"group '{name}' must be a table")
        path = item.get("path")
        entry = item.get("entry")
        description = item.get("description")
        source = item.get("source", "local")
        if not all(isinstance(value, str) and value for value in (path, entry, description)):
            raise RuntimeError(f"group '{name}' requires path, entry, and description")
        if source not in {"local", "git"}:
            raise RuntimeError(f"group '{name}' has unsupported source: {source}")

        repository = item.get("repository")
        branch = item.get("branch")
        doc_url = item.get("doc_url")
        readme = item.get("readme")
        checkout = item.get("checkout")
        if source == "git":
            if not isinstance(repository, str) or not repository:
                raise RuntimeError(f"git group '{name}' requires repository")
            if not isinstance(branch, str) or not branch:
                raise RuntimeError(f"git group '{name}' requires branch")

        specs.append(
            ToolSpec(
                name=name,
                script=str(Path(path) / entry),
                description=description,
                usage=f"hw_tool {name} <tool> [args]",
                kind="hub",
                tool_home=path,
                source=source,
                repository=repository if isinstance(repository, str) else None,
                branch=branch if isinstance(branch, str) else None,
                doc_url=doc_url if isinstance(doc_url, str) else None,
                readme=readme if isinstance(readme, str) else None,
                checkout=checkout if isinstance(checkout, str) else None,
            )
        )
    return tuple(specs)


TOOL_SPECS = load_tool_specs()
TOOL_MAP = {tool.name: tool for tool in TOOL_SPECS}
REPOSITORY_SPECS: tuple[RepositorySpec, ...] = ()
REPOSITORY_MAP: dict[str, RepositorySpec] = {}


def load_default_group() -> str | None:
    try:
        config = tomllib.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeError(f"failed to load group config: {exc}") from exc

    hub = config.get("hub", {})
    default_group = hub.get("default_group") if isinstance(hub, dict) else None
    if default_group is None:
        return None
    if not isinstance(default_group, str) or default_group not in TOOL_MAP:
        raise RuntimeError("hub.default_group must name a registered group")
    return default_group


DEFAULT_GROUP = load_default_group()
