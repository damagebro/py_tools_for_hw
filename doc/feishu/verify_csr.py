"""Publish one CSR README to a dedicated Feishu wiki test page."""

import hashlib
import copy
import json
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urlsplit, unquote

import requests


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "csr_tool/README.md"
OUT = ROOT / "out/feishu_csr"
STATE = OUT / "state.json"
PARENT = "XwJPwteoEiu9hNkGCfkcvLaynGc"
API = "https://open.feishu.cn/open-apis"
RAW = "https://raw.githubusercontent.com/damagebro/py_tools_for_hw/main/csr_tool/"


def credential(name):
    value = os.environ.get(name)
    if not value and os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value = winreg.QueryValueEx(key, name)[0]
    if not value:
        raise RuntimeError(f"Missing credential: {name}")
    return value


class Feishu:
    def __init__(self):
        self.session = requests.Session()
        auth = self.call("POST", "/auth/v3/tenant_access_token/internal", json={
            "app_id": credential("FEISHU_APP_ID"),
            "app_secret": credential("FEISHU_APP_SECRET"),
        }, root=True)
        self.session.headers["Authorization"] = "Bearer " + auth["tenant_access_token"]

    def call(self, method, path, root=False, **kwargs):
        response = self.session.request(method, API + path, timeout=60, **kwargs)
        try:
            result = response.json()
        except ValueError:
            raise RuntimeError(f"{path}: HTTP {response.status_code}") from None
        if response.status_code >= 400 or result.get("code", 0):
            (OUT / "last_error.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            raise RuntimeError(f"{path}: code={result.get('code')}, {result.get('msg')}")
        return result if root else result.get("data", {})


def save(state):
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATE)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = SOURCE.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {
        "source_sha256": digest, "completed_roots": 0, "images_done": []}
    if state["source_sha256"] != digest:
        raise RuntimeError("README changed since initial run; inspect the test page before restarting")
    client = Feishu()
    if state.get("pending"):
        document = state.get("document_id")
        if document and state["completed_roots"] == 0:
            children = client.call("GET", f"/docx/v1/documents/{document}/blocks/{document}/children")
            if not children.get("items"):
                state.pop("pending")
                save(state)
        if state.get("pending"):
            raise RuntimeError("Previous write outcome is uncertain; inspect state.json and remote page first")
    node = client.call("GET", "/wiki/v2/spaces/get_node", params={"token": PARENT})["node"]
    print("Authentication and parent access: OK", flush=True)

    converted_file = OUT / "converted.json"
    if converted_file.exists():
        converted = json.loads(converted_file.read_text(encoding="utf-8"))
    else:
        content = source.decode("utf-8-sig")
        for name in ("csr_bus_timing.png", "reg_type_dff_arch.png"):
            content = content.replace(f"(doc/assets/{name})", f"({RAW}doc/assets/{name})")
        content = content.replace("(doc/assets/csr_bus_timing.json)",
                                  "(https://github.com/damagebro/py_tools_for_hw/blob/main/csr_tool/doc/assets/csr_bus_timing.json)")
        converted = client.call("POST", "/docx/v1/documents/blocks/convert",
                                json={"content_type": "markdown", "content": content})
        converted_file.write_text(json.dumps(converted, ensure_ascii=False), encoding="utf-8")
    blocks = {b["block_id"]: b for b in converted["blocks"]}
    roots = converted["first_level_block_ids"]
    print(f"Converted: {len(roots)} root blocks, {len(blocks)} total blocks", flush=True)

    if not state.get("document_id"):
        state["pending"] = "create wiki test node"
        save(state)
        result = client.call("POST", f"/wiki/v2/spaces/{node['space_id']}/nodes", json={
            "obj_type": "docx", "node_type": "origin", "parent_node_token": PARENT,
            "title": "CSR README 导入验证"})["node"]
        state.update(document_id=result["obj_token"], node_token=result["node_token"],
                     url=f"https://my.feishu.cn/wiki/{result['node_token']}")
        state.pop("pending")
        save(state)
    document = state["document_id"]
    print(state["url"], flush=True)

    def descendants(block_id):
        block = copy.deepcopy(blocks[block_id])
        block.pop("parent_id", None)
        if "table" in block:
            block["table"].pop("cells", None)
            block["table"]["property"].pop("merge_info", None)
        result = [block]
        for child in block.get("children", []):
            result.extend(descendants(child))
        return result

    while state["completed_roots"] < len(roots):
        start = state["completed_roots"]
        batch_roots, batch = [], []
        for block_id in roots[start:]:
            branch = descendants(block_id)
            if batch and (len(batch) + len(branch) > 500 or len(batch_roots) >= 40):
                break
            batch_roots.append(block_id)
            batch.extend(branch)
        state["pending"] = f"append root blocks {start}:{start + len(batch_roots)}"
        save(state)
        result = client.call("POST", f"/docx/v1/documents/{document}/blocks/{document}/descendant",
                             params={"document_revision_id": -1, "client_token": str(uuid.uuid4())},
                             json={"children_id": batch_roots, "index": -1, "descendants": batch})
        state.setdefault("block_ids", {}).update({r["temporary_block_id"]: r["block_id"]
                                                  for r in result["block_id_relations"]})
        state["completed_roots"] += len(batch_roots)
        state.pop("pending")
        save(state)
        print(f"Written roots: {state['completed_roots']}/{len(roots)}", flush=True)
        time.sleep(0.3)

    for item in converted.get("block_id_to_image_urls", []):
        temp_id = item["block_id"]
        if temp_id in state["images_done"]:
            continue
        image_url = item["image_url"]
        if image_url.startswith(RAW):
            relative_image = image_url[len(RAW):]
        elif not urlsplit(image_url).scheme and not image_url.startswith(("/", "\\")):
            relative_image = unquote(urlsplit(image_url).path)
        else:
            raise RuntimeError("Unexpected image URL in conversion output")
        image = (ROOT / "csr_tool" / relative_image).resolve()
        if not image.is_relative_to((ROOT / "csr_tool").resolve()):
            raise RuntimeError("Image outside CSR source directory")
        block_id = state["block_ids"][temp_id]
        with image.open("rb") as stream:
            uploaded = client.call("POST", "/drive/v1/medias/upload_all", data={
                "file_name": image.name, "parent_type": "docx_image", "parent_node": block_id,
                "size": str(image.stat().st_size), "extra": json.dumps({"drive_route_token": document})
            }, files={"file": (image.name, stream, "image/png")})
        client.call("PATCH", f"/docx/v1/documents/{document}/blocks/{block_id}",
                    params={"document_revision_id": -1},
                    json={"replace_image": {"token": uploaded["file_token"]}})
        state["images_done"].append(temp_id)
        save(state)
        print(f"Uploaded image: {image.name}", flush=True)

    content = client.call("GET", f"/docx/v1/documents/{document}/raw_content")["content"]
    required = ("CSR Autogen Tool", "工具概览", "安装与快速开始")
    if not all(text in content for text in required):
        raise RuntimeError("Readback verification failed")
    state["verified"] = True
    state["readback_characters"] = len(content)
    save(state)
    print(f"Readback verified: {len(content)} characters; {state['url']}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, requests.RequestException) as error:
        print(f"ERROR: {error}", flush=True)
        raise SystemExit(1)
