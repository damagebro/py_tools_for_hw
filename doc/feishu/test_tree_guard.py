import copy
import unittest
from types import SimpleNamespace
from tree_guard import check_remote_tree
from push_summary import Publisher


class TreeGuardTests(unittest.TestCase):
    def setUp(self):
        self.nodes = {
            "home": {"parent_node_token": ""},
            "root": {"parent_node_token": "home", "obj_token": "root-doc"},
            "a": {"parent_node_token": "root", "obj_token": "a-doc"},
            "b": {"parent_node_token": "root", "obj_token": "b-doc"}}
        for token, node in self.nodes.items():
            node.update(node_token=token, space_id="space")
        self.children = {"root": ["a", "b"], "a": [], "b": []}
        nodes, children = self.nodes, self.children
        class Client:
            def call(self, method, path, params=None, **kwargs):
                assert method == "GET", "Validation must not write"
                return {"node": nodes[params["token"]]}
            def items(self, path, parent_node_token):
                return [{"node_token": n} for n in children[parent_node_token]]
        self.p = SimpleNamespace(space="space", parent="home", client=Client(),
            entries=[{"key": "book"}, {"key": "a", "parent": "book"}, {"key": "b", "parent": "book"}],
            state={"pages": {
                "book": {"node_token": "root", "document_id": "root-doc", "parent": None},
                "a": {"node_token": "a", "document_id": "a-doc", "parent": "book"},
                "b": {"node_token": "b", "document_id": "b-doc", "parent": "book"}}})

    def test_normal_and_append(self):
        check_remote_tree(self.p)
        self.p.entries.append({"key": "new", "parent": "book"})
        check_remote_tree(self.p)

    def test_middle_insertion_and_reorder_stop_before_writes(self):
        self.p.entries.insert(2, {"key": "new", "parent": "book"})
        with self.assertRaisesRegex(RuntimeError, "order changed"):
            check_remote_tree(self.p)
        check_remote_tree(self.p, require_summary=False)

    def test_root_moved(self):
        self.nodes["root"]["parent_node_token"] = "elsewhere"
        with self.assertRaisesRegex(RuntimeError, "Remote tree mismatch"):
            check_remote_tree(self.p)

    def test_stale_archive_even_if_unused(self):
        self.p.state["archive"] = {"node_token": "archive"}
        self.nodes["archive"] = {"node_token": "drive-token", "parent_node_token": "home"}
        with self.assertRaisesRegex(RuntimeError, "Remote tree mismatch"):
            check_remote_tree(self.p)

    def test_archived_node_escaped_to_home(self):
        self.p.state["pages"]["a"]["archived"] = True
        self.p.entries = [e for e in self.p.entries if e["key"] != "a"]
        self.nodes["a"]["parent_node_token"] = "home"
        with self.assertRaisesRegex(RuntimeError, "Remote tree mismatch"):
            check_remote_tree(self.p, require_summary=False)

    def test_unmanaged_child_blocks(self):
        self.children["root"].append("manual")
        with self.assertRaisesRegex(RuntimeError, "Unexpected"):
            check_remote_tree(self.p)

    def test_removal_requires_explicit_tree_sync(self):
        self.p.entries.pop()
        with self.assertRaisesRegex(RuntimeError, "removed or reparented"):
            check_remote_tree(self.p)
        check_remote_tree(self.p, require_summary=False)

    def test_wrong_document_blocks(self):
        self.nodes["a"]["obj_token"] = "replacement"
        with self.assertRaisesRegex(RuntimeError, "Remote tree mismatch"):
            check_remote_tree(self.p)

    def test_failed_move_keeps_old_parent_and_pending(self):
        p = Publisher.__new__(Publisher)
        p.state = copy.deepcopy(self.p.state)
        p.space = "space"
        p.client = self.p.client
        p.persist = lambda: None
        p.mutate = lambda *a, **k: {}  # API claims success but tree does not move
        with self.assertRaisesRegex(RuntimeError, "Remote tree mismatch"):
            p.move_page("a", "home", None)
        self.assertEqual(p.state["pages"]["a"]["parent"], "book")
        self.assertIn("pending", p.state)

    def test_nonempty_delete_is_rejected(self):
        p = Publisher.__new__(Publisher)
        p.client = self.p.client
        p.space = "space"
        with self.assertRaisesRegex(RuntimeError, "nonempty"):
            p.delete_leaf("root", "home")
