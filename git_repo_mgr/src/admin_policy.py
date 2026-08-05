from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ADMIN_CONFIG_NAME = "git_repo_admin.toml"
ADMIN_STATE_DIR = "admin"
VALID_MODES = {"read-only", "integration-only"}
SSH_URL_RE = re.compile(r"^(?:[^@]+@)?(?P<host>[^:]+):(?P<path>.+)$")


class AdminError(Exception):
    def __init__(self, code: str, message: str, details: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    kind: str
    host: str
    api_url: str
    token_env: str
    github_users: tuple[str, ...]
    github_teams: tuple[str, ...]
    github_apps: tuple[str, ...]
    gitlab_allowed_to_push: tuple[dict[str, int], ...]
    gitlab_allowed_to_merge: tuple[dict[str, int], ...]
    gitlab_allowed_to_unprotect: tuple[dict[str, int], ...]


@dataclass(frozen=True)
class AdminConfig:
    branch: str
    baseline_mode: str
    providers: tuple[ProviderConfig, ...]
    source: Path


@dataclass(frozen=True)
class RepositoryTarget:
    name: str
    repository: str
    checkout: str
    commit: str
    ref: str


@dataclass(frozen=True)
class PolicyStatus:
    target: RepositoryTarget
    provider: ProviderConfig
    project: str
    protected: bool
    mode: str
    raw: dict[str, Any] | None


class HttpStatusError(Exception):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(body)
        self.status = status
        self.body = body


def now_text() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_admin_config(top: Path, config_arg: str | None, toml_loader: Any) -> AdminConfig:
    path = Path(config_arg).resolve() if config_arg else top / ADMIN_CONFIG_NAME
    try:
        data = toml_loader(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AdminError("E_ADMIN_CONFIG", f"admin config not found: {path}") from exc
    except Exception as exc:
        raise AdminError("E_ADMIN_CONFIG", f"failed to read admin config: {path}", (str(exc),)) from exc
    if not isinstance(data, dict):
        raise AdminError("E_ADMIN_CONFIG", f"admin config must be a table: {path}")

    policy = data.get("policy", {})
    if not isinstance(policy, dict):
        raise AdminError("E_ADMIN_CONFIG", f"[policy] must be a table: {path}")
    branch = policy.get("branch", "main")
    baseline_mode = policy.get("baseline_mode", "integration-only")
    if not isinstance(branch, str) or not branch:
        raise AdminError("E_ADMIN_CONFIG", "policy.branch must be a non-empty string")
    if baseline_mode not in VALID_MODES:
        raise AdminError("E_ADMIN_CONFIG", f"unsupported policy.baseline_mode: {baseline_mode}")

    raw_providers = data.get("provider", [])
    if not isinstance(raw_providers, list) or not raw_providers:
        raise AdminError("E_ADMIN_CONFIG", "admin config requires one or more [[provider]] entries")
    providers = tuple(parse_provider(item, path) for item in raw_providers)
    hosts = [provider.host for provider in providers]
    if len(hosts) != len(set(hosts)):
        raise AdminError("E_ADMIN_CONFIG", "provider hosts must be unique")
    return AdminConfig(branch, baseline_mode, providers, path)


def parse_provider(item: object, path: Path) -> ProviderConfig:
    if not isinstance(item, dict):
        raise AdminError("E_ADMIN_CONFIG", f"invalid [[provider]] entry: {path}")
    name = item.get("name")
    kind = item.get("type")
    host = item.get("host")
    token_env = item.get("token_env")
    if not all(isinstance(value, str) and value for value in (name, kind, host, token_env)):
        raise AdminError("E_ADMIN_CONFIG", f"provider requires name, type, host, token_env: {path}")
    if kind not in {"github", "gitlab"}:
        raise AdminError("E_ADMIN_CONFIG", f"unsupported provider type: {kind}")
    api_url = item.get("api_url")
    if api_url is None:
        api_url = "https://api.github.com" if kind == "github" and host == "github.com" else None
    if api_url is None and kind == "gitlab" and host == "gitlab.com":
        api_url = "https://gitlab.com/api/v4"
    if not isinstance(api_url, str) or not api_url:
        raise AdminError("E_ADMIN_CONFIG", f"provider '{name}' requires api_url")
    return ProviderConfig(
        name=name,
        kind=kind,
        host=host.casefold(),
        api_url=api_url.rstrip("/"),
        token_env=token_env,
        github_users=string_tuple(item.get("github_users", []), "github_users", name),
        github_teams=string_tuple(item.get("github_teams", []), "github_teams", name),
        github_apps=string_tuple(item.get("github_apps", []), "github_apps", name),
        gitlab_allowed_to_push=access_tuple(item.get("gitlab_allowed_to_push", []), name),
        gitlab_allowed_to_merge=access_tuple(item.get("gitlab_allowed_to_merge", []), name),
        gitlab_allowed_to_unprotect=access_tuple(item.get("gitlab_allowed_to_unprotect", []), name),
    )


def string_tuple(value: object, field: str, provider: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise AdminError("E_ADMIN_CONFIG", f"provider '{provider}' {field} must be a string array")
    return tuple(value)


def access_tuple(value: object, provider: str) -> tuple[dict[str, int], ...]:
    if not isinstance(value, list):
        raise AdminError("E_ADMIN_CONFIG", f"provider '{provider}' GitLab access must be an array")
    result: list[dict[str, int]] = []
    allowed = {"access_level", "user_id", "group_id", "deploy_key_id"}
    for item in value:
        if not isinstance(item, dict) or not item:
            raise AdminError("E_ADMIN_CONFIG", f"provider '{provider}' has invalid GitLab access entry")
        parsed: dict[str, int] = {}
        for key, raw in item.items():
            if key not in allowed or not isinstance(raw, int):
                raise AdminError("E_ADMIN_CONFIG", f"provider '{provider}' has invalid GitLab access field")
            parsed[key] = raw
        result.append(parsed)
    return tuple(result)


def split_repository_url(repository: str) -> tuple[str, str]:
    value = repository.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme:
        host = parsed.hostname
        path = parsed.path
    else:
        match = SSH_URL_RE.fullmatch(value)
        if match is None:
            raise AdminError("E_PROVIDER", f"cannot parse Git repository URL: {repository}")
        host = match.group("host")
        path = match.group("path")
    if not host or not path:
        raise AdminError("E_PROVIDER", f"cannot parse Git repository URL: {repository}")
    project = path.strip("/")
    if project.endswith(".git"):
        project = project[:-4]
    if not project:
        raise AdminError("E_PROVIDER", f"repository URL has no project path: {repository}")
    return host.casefold(), project


def provider_for_repository(config: AdminConfig, repository: str) -> tuple[ProviderConfig, str]:
    host, project = split_repository_url(repository)
    for provider in config.providers:
        if provider.host == host:
            return provider, project
    raise AdminError("E_PROVIDER", f"no provider matches repository host '{host}'", (repository,))


class ProviderClient:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        token = os.environ.get(config.token_env)
        if not token:
            raise AdminError(
                "E_PRIVILEGE",
                f"provider '{config.name}' token is not available: {config.token_env}",
            )
        self.token = token

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        allow_not_found: bool = False,
    ) -> dict[str, Any] | None:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if self.config.kind == "github":
            headers["Authorization"] = f"Bearer {self.token}"
            headers["X-GitHub-Api-Version"] = "2026-03-10"
        else:
            headers["PRIVATE-TOKEN"] = self.token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.config.api_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            if allow_not_found and exc.code == 404:
                return None
            raise AdminError(
                "E_PROVIDER_API",
                f"{self.config.name} API {method} {path} failed: HTTP {exc.code}",
                (text,) if text else (),
            ) from exc
        except urllib.error.URLError as exc:
            raise AdminError(
                "E_PROVIDER_API",
                f"{self.config.name} API {method} {path} failed",
                (str(exc.reason),),
            ) from exc
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdminError("E_PROVIDER_API", f"invalid JSON from {self.config.name} API") from exc
        if not isinstance(data, dict):
            raise AdminError("E_PROVIDER_API", f"unexpected response from {self.config.name} API")
        return data

    def identity(self) -> str:
        data = self.request_json("GET", "/user")
        assert data is not None
        name = data.get("login") if self.config.kind == "github" else data.get("username")
        return str(name) if isinstance(name, str) else "unknown"

    def get_policy(self, project: str, branch: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def apply_mode(self, project: str, branch: str, mode: str, current: dict[str, Any] | None) -> None:
        raise NotImplementedError

    def restore(self, project: str, branch: str, raw: dict[str, Any] | None) -> None:
        raise NotImplementedError

    def status(self, target: RepositoryTarget, branch: str) -> PolicyStatus:
        project = split_repository_url(target.repository)[1]
        raw = self.get_policy(project, branch)
        return PolicyStatus(
            target=target,
            provider=self.config,
            project=project,
            protected=raw is not None,
            mode=self.policy_mode(raw),
            raw=raw,
        )

    def policy_mode(self, raw: dict[str, Any] | None) -> str:
        return "unprotected" if raw is None else "protected"


def github_object_names(value: object, key: str) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get(key), str):
            result.append(item[key])
    return result


def github_restrictions(value: object) -> dict[str, list[str]] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return {"users": [], "teams": [], "apps": []}
    return {
        "users": github_object_names(value.get("users"), "login"),
        "teams": github_object_names(value.get("teams"), "slug"),
        "apps": github_object_names(value.get("apps"), "slug"),
    }


def github_review_payload(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    restrictions = value.get("dismissal_restrictions")
    bypass = value.get("bypass_pull_request_allowances")
    result: dict[str, Any] = {
        "dismissal_restrictions": github_restrictions(restrictions) or {"users": [], "teams": [], "apps": []},
        "dismiss_stale_reviews": bool(value.get("dismiss_stale_reviews", False)),
        "require_code_owner_reviews": bool(value.get("require_code_owner_reviews", False)),
        "required_approving_review_count": int(value.get("required_approving_review_count", 0)),
        "require_last_push_approval": bool(value.get("require_last_push_approval", False)),
    }
    if isinstance(bypass, dict):
        result["bypass_pull_request_allowances"] = github_restrictions(bypass) or {
            "users": [],
            "teams": [],
            "apps": [],
        }
    return result


def enabled(value: object) -> bool:
    return bool(value.get("enabled", False)) if isinstance(value, dict) else bool(value)


def github_protection_payload(
    current: dict[str, Any] | None,
    config: ProviderConfig,
    mode: str,
) -> dict[str, Any]:
    base = current or {}
    status_checks = base.get("required_status_checks")
    if isinstance(status_checks, dict):
        status_payload: dict[str, Any] | None = {
            "strict": bool(status_checks.get("strict", False)),
            "contexts": [item for item in status_checks.get("contexts", []) if isinstance(item, str)],
        }
    else:
        status_payload = None
    restrictions = github_restrictions(base.get("restrictions"))
    if mode == "integration-only":
        if not (config.github_users or config.github_teams or config.github_apps):
            raise AdminError(
                "E_ADMIN_CONFIG",
                f"provider '{config.name}' integration-only requires github_users, github_teams, or github_apps",
            )
        restrictions = {
            "users": list(config.github_users),
            "teams": list(config.github_teams),
            "apps": list(config.github_apps),
        }
    if mode == "read-only":
        restrictions = restrictions or {"users": [], "teams": [], "apps": []}
    return {
        "required_status_checks": status_payload,
        "enforce_admins": enabled(base.get("enforce_admins")),
        "required_pull_request_reviews": github_review_payload(base.get("required_pull_request_reviews")),
        "restrictions": restrictions,
        "required_linear_history": enabled(base.get("required_linear_history")),
        "allow_force_pushes": enabled(base.get("allow_force_pushes")),
        "allow_deletions": enabled(base.get("allow_deletions")),
        "block_creations": enabled(base.get("block_creations")),
        "required_conversation_resolution": enabled(base.get("required_conversation_resolution")),
        "lock_branch": mode == "read-only",
        "allow_fork_syncing": enabled(base.get("allow_fork_syncing")),
    }


class GitHubClient(ProviderClient):
    def protection_path(self, project: str, branch: str) -> str:
        return f"/repos/{project}/branches/{urllib.parse.quote(branch, safe='')}/protection"

    def get_policy(self, project: str, branch: str) -> dict[str, Any] | None:
        return self.request_json("GET", self.protection_path(project, branch), allow_not_found=True)

    def apply_mode(self, project: str, branch: str, mode: str, current: dict[str, Any] | None) -> None:
        self.request_json(
            "PUT",
            self.protection_path(project, branch),
            github_protection_payload(current, self.config, mode),
        )

    def restore(self, project: str, branch: str, raw: dict[str, Any] | None) -> None:
        path = self.protection_path(project, branch)
        if raw is None:
            self.request_json("DELETE", path, allow_not_found=True)
            return
        self.request_json("PUT", path, github_protection_payload(raw, self.config, "protected"))

    def policy_mode(self, raw: dict[str, Any] | None) -> str:
        if raw is None:
            return "unprotected"
        if enabled(raw.get("lock_branch")):
            return "read-only"
        restrictions = github_restrictions(raw.get("restrictions"))
        wanted = {
            "users": list(self.config.github_users),
            "teams": list(self.config.github_teams),
            "apps": list(self.config.github_apps),
        }
        if restrictions == wanted and any(wanted.values()):
            return "integration-only"
        return "protected"


def gitlab_access_payload(value: object) -> list[dict[str, int]]:
    if not isinstance(value, list):
        return []
    allowed = {"access_level", "user_id", "group_id", "deploy_key_id"}
    result: list[dict[str, int]] = []
    for item in value:
        if isinstance(item, dict):
            parsed = {key: raw for key, raw in item.items() if key in allowed and isinstance(raw, int)}
            if parsed:
                result.append(parsed)
    return result


class GitLabClient(ProviderClient):
    def protection_path(self, project: str, branch: str) -> str:
        project_id = urllib.parse.quote(project, safe="")
        return f"/projects/{project_id}/protected_branches/{urllib.parse.quote(branch, safe='')}"

    def get_policy(self, project: str, branch: str) -> dict[str, Any] | None:
        return self.request_json("GET", self.protection_path(project, branch), allow_not_found=True)

    def apply_mode(self, project: str, branch: str, mode: str, current: dict[str, Any] | None) -> None:
        if mode == "integration-only":
            if not self.config.gitlab_allowed_to_push:
                raise AdminError(
                    "E_ADMIN_CONFIG",
                    f"provider '{self.config.name}' integration-only requires gitlab_allowed_to_push",
                )
            push = list(self.config.gitlab_allowed_to_push)
            merge = list(self.config.gitlab_allowed_to_merge)
        else:
            push = [{"access_level": 0}]
            merge = [{"access_level": 0}]
        unprotect = list(self.config.gitlab_allowed_to_unprotect) or [{"access_level": 40}]
        path = self.protection_path(project, branch)
        if current is not None:
            self.request_json("DELETE", path)
        self.request_json(
            "POST",
            f"/projects/{urllib.parse.quote(project, safe='')}/protected_branches",
            {
                "name": branch,
                "allow_force_push": False,
                "allowed_to_push": push,
                "allowed_to_merge": merge,
                "allowed_to_unprotect": unprotect,
            },
        )

    def restore(self, project: str, branch: str, raw: dict[str, Any] | None) -> None:
        path = self.protection_path(project, branch)
        current = self.get_policy(project, branch)
        if current is not None:
            self.request_json("DELETE", path)
        if raw is None:
            return
        self.request_json(
            "POST",
            f"/projects/{urllib.parse.quote(project, safe='')}/protected_branches",
            {
                "name": branch,
                "allow_force_push": bool(raw.get("allow_force_push", False)),
                "allowed_to_push": gitlab_access_payload(raw.get("push_access_levels")),
                "allowed_to_merge": gitlab_access_payload(raw.get("merge_access_levels")),
                "allowed_to_unprotect": gitlab_access_payload(raw.get("unprotect_access_levels")),
            },
        )

    def policy_mode(self, raw: dict[str, Any] | None) -> str:
        if raw is None:
            return "unprotected"
        push = gitlab_access_payload(raw.get("push_access_levels"))
        merge = gitlab_access_payload(raw.get("merge_access_levels"))
        if push == [{"access_level": 0}] and merge == [{"access_level": 0}]:
            return "read-only"
        if push == list(self.config.gitlab_allowed_to_push):
            return "integration-only"
        return "protected"


def provider_client(config: ProviderConfig) -> ProviderClient:
    if config.kind == "github":
        return GitHubClient(config)
    if config.kind == "gitlab":
        return GitLabClient(config)
    raise AdminError("E_PROVIDER", f"unsupported provider: {config.kind}")


def admin_state_dir(top: Path) -> Path:
    return top / ".git_repo" / ADMIN_STATE_DIR


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AdminError("E_ADMIN_STATE", f"admin state not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AdminError("E_ADMIN_STATE", f"failed to read admin state: {path}", (str(exc),)) from exc
    if not isinstance(data, dict):
        raise AdminError("E_ADMIN_STATE", f"invalid admin state: {path}")
    return data


def append_audit(top: Path, event: dict[str, Any]) -> None:
    path = admin_state_dir(top) / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    item = {"timestamp": now_text(), **event}
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(item, ensure_ascii=False) + "\n")
