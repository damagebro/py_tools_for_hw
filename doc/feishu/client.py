"""Feishu API client; credentials stay in the environment or Windows user registry."""

import os
import time

import requests


class ApiError(RuntimeError):
    pass


def credential(name):
    value = os.environ.get(name)
    if not value and os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value = winreg.QueryValueEx(key, name)[0]
        except FileNotFoundError:
            pass
    if not value:
        raise RuntimeError(f"Missing credential: {name}")
    return value


class Feishu:
    def __init__(self):
        self.session = requests.Session()
        self.expiry = 0
        self.authenticate()

    def authenticate(self):
        result = self.call("POST", "/auth/v3/tenant_access_token/internal", root=True,
                           json={"app_id": credential("FEISHU_APP_ID"),
                                 "app_secret": credential("FEISHU_APP_SECRET")})
        self.session.headers["Authorization"] = "Bearer " + result["tenant_access_token"]
        self.expiry = time.monotonic() + result.get("expire", 7200) - 120

    def call(self, method, path, root=False, **kwargs):
        if self.expiry and time.monotonic() >= self.expiry and not path.startswith("/auth/"):
            self.authenticate()
        for attempt in range(5):
            response = self.session.request(method, "https://open.feishu.cn/open-apis" + path,
                                            timeout=(15, 60), **kwargs)
            if response.status_code == 429 and "files" not in kwargs and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            if response.status_code >= 500:
                raise RuntimeError(f"{path}: HTTP {response.status_code}; write outcome may be uncertain")
            try:
                result = response.json()
            except ValueError:
                raise RuntimeError(f"{path}: HTTP {response.status_code}, non-JSON response; verify write outcome") from None
            if response.status_code >= 400 or result.get("code", 0):
                raise ApiError(f"{path}: code={result.get('code')}, {result.get('msg')}")
            return result if root else result.get("data", {})

    def items(self, path, **params):
        result = []
        params.setdefault("page_size", 50)
        while True:
            data = self.call("GET", path, params=params)
            result.extend(data.get("items", []))
            if not data.get("has_more"):
                return result
            params["page_token"] = data["page_token"]
