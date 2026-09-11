import tempfile
import unittest
from pathlib import Path

from push_summary import Publisher, branch, parse_summary, prepare_links, rewrite_links


class SummaryTests(unittest.TestCase):
    def test_tree_sync_archives_and_reorders_without_deleting(self):
        publisher = Publisher.__new__(Publisher)
        publisher.entries = [{"key": "book"}, {"key": "b", "parent": "book"},
                             {"key": "a", "parent": "book"}]
        publisher.state = {"pages": {
            "book": {"node_token": "root", "parent": None},
            "a": {"node_token": "a", "parent": "book"},
            "b": {"node_token": "b", "parent": "book"},
            "old": {"node_token": "old", "parent": "book"},
            "child": {"node_token": "child", "parent": "old"}}}
        publisher.space = "space"
        nodes = {"root": ["a", "old", "b"], "old": ["child"], "archive": []}
        moves = []

        class FakeClient:
            def items(self, path, parent_node_token):
                return [{"node_token": key} for key in nodes[parent_node_token]]

        def move(key, token, parent):
            for siblings in nodes.values():
                if key in siblings:
                    siblings.remove(key)
            nodes[token].append(key)
            publisher.state["pages"][key]["parent"] = parent
            moves.append(key)

        publisher.client = FakeClient()
        publisher.persist = lambda: None
        publisher.archive_node = lambda: "archive"
        publisher.move_page = move
        publisher.sync_tree()
        self.assertEqual(nodes["root"], ["b", "a"])
        self.assertEqual(nodes["archive"], ["old"])
        self.assertEqual(nodes["old"], ["child"])
        self.assertTrue(publisher.state["pages"]["child"]["archived"])
        self.assertEqual(len(publisher.state["pages"]), 5)
        count = len(moves)
        publisher.sync_tree()
        self.assertEqual(len(moves), count)

    def test_order_and_hierarchy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for name in ("a.md", "b.md", "c.md"):
                (root / name).touch()
            summary = root / "SUMMARY.md"
            summary.write_text("# Contents\n## Tools\n* [A](a.md)\n  * [B](b.md)\n* [C](c.md)\n", encoding="utf-8")
            entries = parse_summary(summary, root)
            self.assertEqual([e["key"] for e in entries], ["group:Tools", "a.md", "b.md", "c.md"])
            self.assertEqual(entries[2]["parent"], "a.md")
            self.assertEqual(entries[2]["title"], "1.1.1 B")
            self.assertEqual(entries[3]["title"], "1.2 C")
            summary.write_text("* [A](a.md)\n* [Again](a.md)\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                parse_summary(summary, root)
            summary.write_text("* [Outside](../outside.md)\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                parse_summary(summary, root)

    def test_rewrite_only_link_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            value = {"code": "![example](missing.png)", "text": {"link": {"url": "other.md#section"}}}
            warnings = set()
            rewrite_links(value, root / "README.md", root,
                          {"other.md": {"url": "https://example/wiki/other"}}, "https://example/repo", warnings)
            self.assertEqual(value["text"]["link"]["url"], "https://example/wiki/other")
            self.assertEqual(value["code"], "![example](missing.png)")
            self.assertEqual(len(warnings), 1)

    def test_table_sanitization_does_not_modify_cache(self):
        blocks = {"t": {"block_id": "t", "parent_id": "root", "children": ["c"],
                        "table": {"cells": ["c"], "property": {"merge_info": [], "row_size": 1}}},
                  "c": {"block_id": "c", "parent_id": "t"}}
        result = branch("t", blocks)
        self.assertEqual([b["block_id"] for b in result], ["t", "c"])
        self.assertNotIn("parent_id", result[0])
        self.assertNotIn("cells", result[0]["table"])
        self.assertNotIn("merge_info", result[0]["table"]["property"])
        self.assertIn("cells", blocks["t"]["table"])

    def test_prepare_local_links_preserves_examples_and_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            content = "[Doc](other.md)\n`[Doc](other.md)`\n![Image](image.png)\n```md\n[Doc](other.md)\n```\n[Reference][d]\n[d]: other.md\n"
            result = prepare_links(content, root / "README.md", root,
                                   {"other.md": {"url": "https://example/wiki/doc"}}, "https://example/repo", set())
            self.assertIn("[Doc](https://example/wiki/doc)", result)
            self.assertIn("`[Doc](other.md)`", result)
            self.assertIn("```md\n[Doc](other.md)\n```", result)
            self.assertIn("![Image](image.png)", result)
            self.assertIn("[d]: https://example/wiki/doc", result)

    def test_decode_feishu_link(self):
        root = Path.cwd()
        value = {"link": {"url": "https%3A%2F%2Fexample.com%2Fdoc"}}
        rewrite_links(value, root / "README.md", root, {}, "https://example/repo", set())
        self.assertEqual(value["link"]["url"], "https://example.com/doc")


if __name__ == "__main__":
    unittest.main()
