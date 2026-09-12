"""Read-only Feishu tree validation before publishing or moving managed nodes."""


def node_at(publisher, token, parent=None, document=None):
    node = publisher.client.call("GET", "/wiki/v2/spaces/get_node",
                                 params={"token": token})["node"]
    if (node.get("node_token") != token or node.get("space_id") != publisher.space or
            (parent is not None and node.get("parent_node_token") != parent) or
            (document is not None and node.get("obj_token") != document)):
        raise RuntimeError(f"Remote tree mismatch: {token}; inspect parent, space and document before syncing")
    return node


def check_remote_tree(publisher, require_summary=True):
    """Validate stored edges, including archived pages, then planned output order.

    No mutations: a moved/deleted archive or stale local state must stop publishing.
    New pages append, so inserting one before an existing page needs explicit tree sync.
    """
    pages = publisher.state["pages"]
    archive = publisher.state.get("archive")
    node_at(publisher, publisher.parent)
    if archive:
        node_at(publisher, archive["node_token"], publisher.parent)
    for key, page in pages.items():
        parent_key = page.get("parent")
        if key == "book":
            parent = publisher.parent
        elif parent_key == "__archive" and archive:
            parent = archive["node_token"]
        elif parent_key in pages:
            parent = pages[parent_key]["node_token"]
        else:
            raise RuntimeError(f"Missing parent in state: {key}")
        node_at(publisher, page["node_token"], parent, page.get("document_id"))

    children_by_parent = {}
    for key, page in pages.items():
        children_by_parent[page["node_token"]] = []
    if archive:
        children_by_parent[archive["node_token"]] = []
    for key, page in pages.items():
        parent_key = page.get("parent")
        if key == "book":
            continue
        parent = archive["node_token"] if parent_key == "__archive" else pages[parent_key]["node_token"]
        children_by_parent[parent].append(page["node_token"])
    actual_children = {}
    for parent, known in children_by_parent.items():
        nodes = publisher.client.items(f"/wiki/v2/spaces/{publisher.space}/nodes",
                                       parent_node_token=parent)
        actual = [n["node_token"] for n in nodes]
        if set(actual) != set(known) or len(actual) != len(known):
            raise RuntimeError(f"Unexpected or missing child under {parent}; inspect remote tree before syncing")
        actual_children[parent] = actual

    if not require_summary:
        return
    entries = publisher.entries
    desired = {e["key"]: e for e in entries}
    for key, page in pages.items():
        if page.get("archived") and key not in desired:
            continue
        if key not in desired or page.get("parent") != desired[key].get("parent") or page.get("archived"):
            raise RuntimeError(f"Chapter removed or reparented: {key}; explicit tree synchronization required")
    for entry in entries:
        key = entry["key"]
        if key not in pages:
            continue
        children = [e["key"] for e in entries if e.get("parent") == key]
        expected = [pages[k]["node_token"] if k in pages else ("new", k) for k in children]
        projected = actual_children[pages[key]["node_token"]] + [("new", k) for k in children if k not in pages]
        if projected != expected:
            raise RuntimeError(f"Chapter order changed: {key}; explicit tree synchronization required")
