"""Publish SUMMARY.md as an ordered Feishu wiki tree without editing source files."""

import argparse
import copy
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import time
from urllib.parse import quote, unquote, urlsplit
import uuid

import requests
import markdown

from client import ApiError, Feishu
from tree_guard import check_remote_tree, node_at


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARENT = "https://my.feishu.cn/wiki/XwJPwteoEiu9hNkGCfkcvLaynGc"
FORMAT_VERSION = 1


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def parse_summary(path, root):
    entries = []
    group = "book"
    group_number = 0
    stack = []
    counters = {}
    seen = {"book"}
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip() or line.startswith("# "):
            continue
        if line.startswith("## "):
            title = line[3:].strip()
            group = "group:" + title
            if group in seen:
                raise ValueError(f"Duplicate group at line {number}: {title}")
            seen.add(group)
            group_number += 1
            entries.append({"key": group, "parent": "book", "title": f"{group_number} {title}"})
            counters[group] = 0
            stack = []
            continue
        match = re.fullmatch(r"( *)(?:\*|-) \[([^\]]+)\]\(([^)]+)\)\s*", line)
        if not match:
            raise ValueError(f"Unsupported SUMMARY syntax at line {number}: {line}")
        indent, label, target = match.groups()
        if len(indent) % 2:
            raise ValueError(f"Use two spaces per list level: line {number}")
        level = len(indent) // 2
        if level > len(stack):
            raise ValueError(f"Skipped parent level at line {number}")
        url = urlsplit(target)
        if url.scheme or url.netloc or url.fragment or url.query:
            raise ValueError(f"SUMMARY must reference local Markdown files: {target}")
        file = (path.parent / unquote(url.path)).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise ValueError(f"Missing source or outside root: {target}")
        key = file.relative_to(root).as_posix()
        if key in seen:
            raise ValueError(f"Duplicate document: {key}")
        seen.add(key)
        parent = group if level == 0 else stack[level - 1]["key"]
        counters[parent] = counters.get(parent, 0) + 1
        prefix = str(group_number) if level == 0 else stack[level - 1].get("number", "")
        numbering = f"{prefix}.{counters[parent]}" if group_number else ""
        entry = {"key": key, "parent": parent, "source": key,
                 "title": f"{numbering} {label}".strip(), "number": numbering}
        entries.append(entry)
        stack = stack[:level] + [entry]
    return entries


def local_target(url, source, root):
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    path = (source.parent / unquote(parsed.path)).resolve()
    return path if path.is_relative_to(root) else None


def resolve_link(url, source, root, pages, repository_url, warnings):
    path = local_target(url, source, root)
    if not path:
        return url
    key = path.relative_to(root).as_posix()
    if key in pages:
        if urlsplit(url).fragment:
            warnings.add(f"Heading link points to page top: {source.name}: {url}")
        return pages[key]["url"]
    route = "tree" if path.is_dir() else "blob"
    result = f"{repository_url}/{route}/main/{quote(key)}"
    if urlsplit(url).fragment:
        result += "#" + urlsplit(url).fragment
    if not path.exists():
        warnings.add(f"Source link may require generated files: {key}")
    return result


def prepare_links(content, source, root, pages, repository_url, warnings):
    # Collect real Markdown links with the parser; leave images and code alone.
    from markdown.extensions import Extension
    from markdown.treeprocessors import Treeprocessor

    targets = set()

    class Collector(Treeprocessor):
        def run(self, tree):
            targets.update(a.get("href") for a in tree.iter("a") if a.get("href"))

    class CollectLinks(Extension):
        def extendMarkdown(self, md):
            md.treeprocessors.register(Collector(md), "collect_links", 1)

    markdown.Markdown(extensions=["extra", CollectLinks()]).convert(content)
    replacements = {url: resolve_link(url, source, root, pages, repository_url, warnings) for url in targets}
    # Retain the original Markdown layout, protecting fenced and inline code.
    pattern = re.compile(r"(?P<code>^ {0,3}(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^ {0,3}(?P=fence)[ \t]*$|(?P<ticks>`+)[^`]*?(?P=ticks))|(?P<link>(?<!!)\]\(<?(?P<url>[^\s<>)]*)>?)|(?P<ref>^ {0,3}\[[^\]\n]+\]:[ \t]*<?(?P<refurl>[^\s<>]+)>?)", re.MULTILINE | re.DOTALL)

    def replace(match):
        if match.group("code"):
            return match.group()
        name = "url" if match.group("link") else "refurl"
        url = match.group(name)
        new = replacements.get(url, url)
        start, end = match.span(name)
        return match.group()[:start - match.start()] + new + match.group()[end - match.start():]

    return pattern.sub(replace, content)


def rewrite_links(value, source, root, pages, repository_url, warnings):
    if isinstance(value, list):
        for item in value:
            rewrite_links(item, source, root, pages, repository_url, warnings)
    elif isinstance(value, dict):
        link = value.get("link")
        if isinstance(link, dict) and isinstance(link.get("url"), str):
            url = link["url"]
            # Feishu encodes the complete URL, including its scheme separators.
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*%3[aA]", url):
                url = unquote(url)
            link["url"] = resolve_link(url, source, root, pages, repository_url, warnings)
        for item in value.values():
            rewrite_links(item, source, root, pages, repository_url, warnings)


def branch(block_id, blocks):
    block = copy.deepcopy(blocks[block_id])
    block.pop("parent_id", None)
    if "table" in block:
        block["table"].pop("cells", None)
        block["table"]["property"].pop("merge_info", None)
    result = [block]
    for child in block.get("children", []):
        result.extend(branch(child, blocks))
    return result


class Publisher:
    def __init__(self, args, entries):
        self.args, self.entries = args, entries
        self.warnings = set()
        self.cache = args.state.parent / "cache"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.state = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else {"pages": {}}
        identity = {"root": str(args.root), "parent_url": args.parent_url}
        if self.state.get("identity", identity) != identity:
            raise RuntimeError("State belongs to a different source root or destination")
        self.state["identity"] = identity
        if self.state.get("pending"):
            raise RuntimeError("Previous write outcome uncertain; inspect state.json before retrying")
        self.client = Feishu()
        token = urlsplit(args.parent_url).path.rstrip("/").split("/")[-1]
        node = self.client.call("GET", "/wiki/v2/spaces/get_node", params={"token": token})["node"]
        self.space, self.parent = node["space_id"], node["node_token"]
        parsed = urlsplit(args.parent_url)
        self.origin = f"{parsed.scheme}://{parsed.netloc}"

    def persist(self):
        save(self.args.state, self.state)

    def mutate(self, label, method, path, **kwargs):
        self.state["pending"] = label
        self.persist()
        try:
            result = self.client.call(method, path, **kwargs)
        except ApiError:
            # A reported API rejection is distinct from a timeout with unknown outcome.
            self.state.pop("pending")
            self.persist()
            raise
        self.state.pop("pending")
        return result

    def ensure_nodes(self):
        for entry in self.entries:
            key = entry["key"]
            parent = self.parent if key == "book" else self.state["pages"][entry["parent"]]["node_token"]
            page = self.state["pages"].get(key)
            if not page:
                siblings = self.client.items(f"/wiki/v2/spaces/{self.space}/nodes", parent_node_token=parent)
                if any(n["title"] == entry["title"] for n in siblings):
                    raise RuntimeError(f"Existing unmanaged title: {entry['title']}; restore state or change root title")
                node = self.mutate(f"create {key}", "POST", f"/wiki/v2/spaces/{self.space}/nodes", json={
                    "obj_type": "docx", "node_type": "origin", "parent_node_token": parent,
                    "title": entry["title"]})["node"]
                page = {"node_token": node["node_token"], "document_id": node["obj_token"],
                        "url": f"{self.origin}/wiki/{node['node_token']}",
                        "title": entry["title"], "parent": entry.get("parent")}
                self.state["pages"][key] = page
                self.persist()
                print(f"CREATE {entry['title']}", flush=True)
            if page.get("parent") != entry.get("parent") or page.get("archived"):
                if not self.args.sync_tree:
                    raise RuntimeError(f"Chapter parent changed: {key}; use --sync-tree")
                self.move_page(key, parent, entry.get("parent"))
                page.pop("archived", None)
                self.persist()
            if page["title"] != entry["title"]:
                self.mutate(f"rename {key}", "POST", f"/wiki/v2/spaces/{self.space}/nodes/{page['node_token']}/update_title",
                            json={"title": entry["title"]})
                page["title"] = entry["title"]
                if "revision" in page:
                    page["revision"] = self.revision(page["document_id"])
                self.persist()

    def preflight(self):
        keys = {e["key"] for e in self.entries}
        for key, page in self.state["pages"].items():
            if page.get("archived") and key not in keys:
                continue
            if page.get("job") and self.args.sync_tree:
                raise RuntimeError(f"Finish interrupted content upload before --sync-tree: {key}")
            if "revision" in page and not page.get("job"):
                if self.revision(page["document_id"]) != page["revision"]:
                    raise RuntimeError(f"Remote edits detected before syncing: {key}")
        if self.args.sync_tree:
            save(self.args.state.parent / f"state-before-tree-{time.time_ns()}.json", self.state)

    def archive_node(self):
        if not self.state.get("archive"):
            title = self.args.title + " - 历史归档"
            siblings = self.client.items(f"/wiki/v2/spaces/{self.space}/nodes", parent_node_token=self.parent)
            if any(n["title"] == title for n in siblings):
                raise RuntimeError("Unmanaged archive already exists; restore its state before syncing")
            node = self.mutate("create archive", "POST", f"/wiki/v2/spaces/{self.space}/nodes", json={
                "obj_type": "docx", "node_type": "origin", "parent_node_token": self.parent, "title": title})["node"]
            self.state["archive"] = {"node_token": node["node_token"],
                                     "url": f"{self.origin}/wiki/{node['node_token']}"}
            self.persist()
        node_at(self, self.state["archive"]["node_token"], self.parent)
        return self.state["archive"]["node_token"]

    def move_page(self, key, parent_token, parent_key):
        page = self.state["pages"][key]
        node_at(self, parent_token)
        self.mutate(f"move {key}", "POST", f"/wiki/v2/spaces/{self.space}/nodes/{page['node_token']}/move",
                    json={"target_parent_token": parent_token, "target_space_id": self.space})
        self.state["pending"] = f"verify move {key}"
        self.persist()
        node_at(self, page["node_token"], parent_token, page.get("document_id"))
        page["parent"] = parent_key
        self.state.pop("pending")
        self.persist()
        print(f"MOVE {key} -> {parent_key}", flush=True)

    def sync_tree(self):
        keys = {e["key"] for e in self.entries}
        removed = {key for key, page in self.state["pages"].items()
                   if key not in keys and not page.get("archived")}
        for key in sorted(removed):
            page = self.state["pages"][key]
            if page.get("parent") not in removed:
                self.move_page(key, self.archive_node(), "__archive")
        for key in removed:
            self.state["pages"][key]["archived"] = True
        self.persist()
        for entry in self.entries:
            children = [e["key"] for e in self.entries if e.get("parent") == entry["key"]]
            if not children:
                continue
            parent = self.state["pages"][entry["key"]]["node_token"]
            expected = [self.state["pages"][key]["node_token"] for key in children]
            nodes = self.client.items(f"/wiki/v2/spaces/{self.space}/nodes", parent_node_token=parent)
            if [n["node_token"] for n in nodes if n["node_token"] in expected] == expected:
                continue
            # The public move API has no position field; moving back appends nodes.
            for key in children:
                self.move_page(key, self.archive_node(), "__archive")
            for key in children:
                self.move_page(key, parent, entry["key"])

    def prune_archive(self):
        archive = self.state.get("archive")
        if not archive:
            return
        check_remote_tree(self)
        obsolete = {k for k, p in self.state["pages"].items() if p.get("archived")}
        active = {e["key"] for e in self.entries}
        if obsolete & active:
            raise RuntimeError("Refusing to delete a current chapter")
        while obsolete:
            leaves = [k for k in obsolete if not any(p.get("parent") == k for p in self.state["pages"].values())]
            if not leaves:
                raise RuntimeError("Archive is not a closed tree")
            for key in leaves:
                page = self.state["pages"][key]
                parent_key = page["parent"]
                parent = archive["node_token"] if parent_key == "__archive" else self.state["pages"][parent_key]["node_token"]
                self.delete_leaf(page["node_token"], parent)
                self.state.setdefault("deleted_pages", {})[key] = self.state["pages"].pop(key)
                self.state.pop("pending")
                self.persist()
                obsolete.remove(key)
                print(f"DELETE {key}", flush=True)
        self.delete_leaf(archive["node_token"], self.parent)
        self.state["deleted_archive"] = self.state.pop("archive")
        self.state.pop("pending")
        self.persist()

    def delete_leaf(self, token, parent):
        node_at(self, token, parent)
        if self.client.items(f"/wiki/v2/spaces/{self.space}/nodes", parent_node_token=token):
            raise RuntimeError(f"Refusing to delete nonempty node: {token}")
        result = self.mutate(f"delete {token}", "DELETE", f"/wiki/v2/spaces/{self.space}/nodes/{token}",
                             json={"obj_type": "wiki"})
        self.state["pending"] = f"verify delete {token}"
        self.state.setdefault("delete_tasks", {})[token] = result
        self.persist()
        for attempt in range(10):
            siblings = self.client.items(f"/wiki/v2/spaces/{self.space}/nodes", parent_node_token=parent)
            if token not in {n["node_token"] for n in siblings}:
                return
            time.sleep(1)
        raise RuntimeError(f"Deletion not yet confirmed: {token}; inspect task before retrying")

    def content(self, entry):
        if entry.get("source"):
            path = self.args.root / entry["source"]
            return path.read_text(encoding="utf-8-sig"), path
        lines = [f"# {entry['title']}", ""]
        for child in self.entries:
            if child.get("parent") == entry["key"]:
                lines.append(f"- [{child['title']}]({self.state['pages'][child['key']]['url']})")
        return "\n".join(lines), self.args.root / "SUMMARY.md"

    def revision(self, document):
        return self.client.call("GET", f"/docx/v1/documents/{document}")["document"]["revision_id"]

    def publish_page(self, entry):
        page = self.state["pages"][entry["key"]]
        document = page["document_id"]
        content, source = self.content(entry)
        source_hash = digest(content.encode("utf-8"))
        active_pages = {e["key"]: self.state["pages"][e["key"]] for e in self.entries}
        prepared = prepare_links(content, source, self.args.root, active_pages,
                                 self.args.repository_url, self.warnings)
        conversion_path = self.cache / f"{digest(entry['key'])}-{digest(prepared.encode('utf-8'))}.json"
        if conversion_path.exists():
            converted = json.loads(conversion_path.read_text(encoding="utf-8"))
        else:
            converted = self.client.call("POST", "/docx/v1/documents/blocks/convert",
                                         json={"content_type": "markdown", "content": prepared})
            save(conversion_path, converted)
        rewrite_links(converted["blocks"], source, self.args.root, active_pages,
                      self.args.repository_url, self.warnings)
        images = {}
        image_hashes = {}
        for item in converted.get("block_id_to_image_urls", []):
            path = local_target(item["image_url"], source, self.args.root)
            if not path or not path.is_file():
                raise RuntimeError(f"Image must be an existing local file inside source root: {item['image_url']} ({entry['key']})")
            images[item["block_id"]] = path
            image_hashes[item["block_id"]] = digest(path.read_bytes())
        desired = digest({"format": FORMAT_VERSION, "content": content, "blocks": converted,
                          "images": image_hashes})
        if page.get("synced_hash") == desired:
            if self.revision(document) != page["revision"]:
                raise RuntimeError(f"Remote edits detected: {entry['title']}; preserve changes before pushing")
            print(f"SKIP {entry['title']}", flush=True)
            return
        job = page.get("job")
        if job and job["hash"] != desired:
            raise RuntimeError(f"Source changed during partial upload: {entry['title']}")
        if not job:
            current_revision = self.revision(document)
            if page.get("revision") is not None and current_revision != page["revision"]:
                raise RuntimeError(f"Remote edits detected: {entry['title']}")
            previous = self.client.items(f"/docx/v1/documents/{document}/blocks/{document}/children")
            if not page.get("synced_hash") and previous:
                raise RuntimeError(f"Unexpected content in unsynced page: {entry['title']}")
            job = {"hash": desired, "old_count": len(previous), "written": 0,
                   "block_ids": {}, "images_done": [], "revision": current_revision}
            page["job"] = job
            self.persist()
        elif self.revision(document) != job["revision"]:
            raise RuntimeError(f"Remote page changed since interrupted upload: {entry['title']}")
        blocks = {b["block_id"]: b for b in converted["blocks"]}
        roots = converted["first_level_block_ids"]
        while job["written"] < len(roots):
            batch, children = [], []
            for block_id in roots[job["written"]:]:
                subtree = branch(block_id, blocks)
                if batch and (len(batch) + len(subtree) > 500 or len(children) >= 40):
                    break
                if len(subtree) > 1000:
                    raise RuntimeError(f"Single block tree exceeds API batch budget: {entry['title']}")
                batch.extend(subtree)
                children.append(block_id)
            result = self.mutate(f"append {entry['key']}:{job['written']}", "POST",
                f"/docx/v1/documents/{document}/blocks/{document}/descendant",
                params={"document_revision_id": job["revision"], "client_token": str(uuid.uuid4())},
                json={"children_id": children, "index": -1, "descendants": batch})
            job["block_ids"].update({r["temporary_block_id"]: r["block_id"] for r in result["block_id_relations"]})
            job["written"] += len(children)
            job["revision"] = result["document_revision_id"]
            self.persist()
            time.sleep(0.3)
        for temp_id, path in images.items():
            if temp_id in job["images_done"]:
                continue
            block = job["block_ids"][temp_id]
            with path.open("rb") as stream:
                uploaded = self.client.call("POST", "/drive/v1/medias/upload_all", data={
                    "file_name": path.name, "parent_type": "docx_image", "parent_node": block,
                    "size": str(path.stat().st_size), "extra": json.dumps({"drive_route_token": document})},
                    files={"file": (path.name, stream, mimetypes.guess_type(path.name)[0] or "application/octet-stream")})
            result = self.mutate(f"image {entry['key']}:{path.name}", "PATCH",
                f"/docx/v1/documents/{document}/blocks/{block}",
                params={"document_revision_id": job["revision"]},
                json={"replace_image": {"token": uploaded["file_token"]}})
            job["images_done"].append(temp_id)
            job["revision"] = result["document_revision_id"]
            self.persist()
        # Publish the new body before removing the previous generated body.
        while job["old_count"]:
            count = min(job["old_count"], 500)
            result = self.mutate(f"replace old body {entry['key']}", "DELETE",
                f"/docx/v1/documents/{document}/blocks/{document}/children/batch_delete",
                params={"document_revision_id": job["revision"]},
                json={"start_index": 0, "end_index": count})
            job["old_count"] -= count
            job["revision"] = result["document_revision_id"]
            self.persist()
        remote = self.client.items(f"/docx/v1/documents/{document}/blocks")
        by_id = {b["block_id"]: b for b in remote}
        for temp_id in images:
            if not by_id[job["block_ids"][temp_id]].get("image", {}).get("token"):
                raise RuntimeError(f"Image readback failed: {entry['title']}")
        actual = self.client.items(f"/docx/v1/documents/{document}/blocks/{document}/children")
        if [b["block_id"] for b in actual] != [job["block_ids"][b] for b in roots]:
            raise RuntimeError(f"Block order readback failed: {entry['title']}")
        page.update(synced_hash=desired, source_hash=source_hash, revision=job["revision"],
                    blocks=len(remote), images=len(images))
        page.pop("job")
        self.persist()
        print(f"OK {entry['title']}: {len(roots)} blocks, {len(images)} images", flush=True)

    def run(self):
        check_remote_tree(self, require_summary=not getattr(self.args, "sync_tree", False))
        self.preflight()
        self.ensure_nodes()
        if self.args.sync_tree:
            self.sync_tree()
        check_remote_tree(self)
        for entry in self.entries:
            self.publish_page(entry)
        for entry in self.entries:
            expected = [self.state["pages"][e["key"]]["node_token"] for e in self.entries
                        if e.get("parent") == entry["key"]]
            if not expected:
                continue
            nodes = self.client.items(f"/wiki/v2/spaces/{self.space}/nodes",
                                      parent_node_token=self.state["pages"][entry["key"]]["node_token"])
            actual = [n["node_token"] for n in nodes if n["node_token"] in expected]
            if actual != expected:
                raise RuntimeError(f"Wiki sibling order differs from SUMMARY: {entry['title']}")
        if self.args.delete_removed:
            self.prune_archive()
        check_remote_tree(self)
        report = {"url": self.state["pages"]["book"]["url"], "pages": len(self.entries),
                  "documents": sum(bool(e.get("source")) for e in self.entries),
                  "warnings": sorted(self.warnings), "verified_order": True}
        if self.state.get("archive"):
            report["archive_url"] = self.state["archive"]["url"]
        save(self.args.state.parent / "report.json", report)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--parent-url", default=DEFAULT_PARENT)
    parser.add_argument("--title", default="HW Tool 文档")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--repository-url", default="https://github.com/damagebro/py_tools_for_hw")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sync-tree", action="store_true",
                        help="Move/reorder managed pages to match SUMMARY; archive removed chapters")
    parser.add_argument("--check-tree", action="store_true", help="Read-only remote hierarchy and SUMMARY validation")
    parser.add_argument("--delete-removed", action="store_true", help="With --sync-tree, delete removed pages and temporary archive")
    args = parser.parse_args()
    if args.delete_removed and not args.sync_tree:
        parser.error("--delete-removed requires --sync-tree")
    args.root = args.root.resolve()
    summary = (args.summary or args.root / "SUMMARY.md").resolve()
    args.state = (args.state or args.root / "out/feishu_summary/state.json").resolve()
    entries = [{"key": "book", "title": args.title}] + parse_summary(summary, args.root)
    if args.check_tree:
        check_remote_tree(Publisher(args, entries))
        print("Remote tree and SUMMARY: OK; no changes made")
        return
    if args.dry_run:
        for entry in entries:
            print(f"{entry.get('parent', '-')} -> {entry['title']} [{entry.get('source', 'chapter')}]")
        print(f"{len(entries)} pages; no network requests")
        return
    Publisher(args, entries).run()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, requests.RequestException) as error:
        print(f"ERROR: {error}", flush=True)
        raise SystemExit(1)
