"""
单元测试 — CFG生成器、路径提取器、完整流水线
"""

import unittest
import json
from src.cfg_generator import CFG, validate_cfg
from src.path_extractor import PathExtractor


class TestCFGValidation(unittest.TestCase):
    """CFG验证测试。"""

    def test_valid_cfg(self):
        """论文Figure 3中的示例CFG应该通过验证。"""
        cfg_data = {
            "nodes": [
                {"id": "S1", "Statement": "The system shows GUI for a list of items to borrow"},
                {"id": "S2", "Statement": "Member selects items to borrow"},
                {"id": "S3", "Statement": "Member confirms borrow items"},
                {"id": "A1", "Statement": "Click 'Cancel' button"},
                {"id": "E1", "Statement": "The system shows the warning 'Confirm cancellation?'"},
                {"id": "S4", "Statement": "The system records the borrowed items"},
                {"id": "S5", "Statement": "The system displays a list of borrowed items"},
            ],
            "edges": [
                {"from": "S1", "to": "S2", "weight": 1},
                {"from": "S2", "to": "S3", "weight": 2},
                {"from": "S3", "to": "A1", "condition": "Click 'Cancel' button", "weight": 3},
                {"from": "A1", "to": "E1", "weight": 4},
                {"from": "E1", "to": "S5", "condition": "'Cancel' confirmed", "weight": 5},
                {"from": "S3", "to": "S4", "condition": "No 'Cancel'", "weight": 3},
                {"from": "S4", "to": "S5", "weight": 4},
            ],
        }
        is_valid, errors = validate_cfg(cfg_data)
        self.assertTrue(is_valid, f"CFG should be valid, but got errors: {errors}")

    def test_isolated_node(self):
        """有孤立节点的CFG应该验证失败。"""
        cfg_data = {
            "nodes": [
                {"id": "S1", "Statement": "Step 1"},
                {"id": "S2", "Statement": "Step 2"},
                {"id": "S3", "Statement": "Isolated node"},
            ],
            "edges": [
                {"from": "S1", "to": "S2", "weight": 1},
            ],
        }
        is_valid, errors = validate_cfg(cfg_data)
        self.assertFalse(is_valid)
        self.assertTrue(any("Isolated" in e for e in errors))

    def test_orphaned_reference(self):
        """边引用不存在节点的CFG应该验证失败。"""
        cfg_data = {
            "nodes": [
                {"id": "S1", "Statement": "Step 1"},
                {"id": "S2", "Statement": "Step 2"},
            ],
            "edges": [
                {"from": "S1", "to": "S3", "weight": 1},  # S3 不存在
            ],
        }
        is_valid, errors = validate_cfg(cfg_data)
        self.assertFalse(is_valid)
        self.assertTrue(any("Orphaned" in e for e in errors))

    def test_unreachable_node(self):
        """不可达节点应该验证失败。"""
        cfg_data = {
            "nodes": [
                {"id": "S1", "Statement": "Step 1"},
                {"id": "S2", "Statement": "Step 2"},
                {"id": "S3", "Statement": "Unreachable"},
            ],
            "edges": [
                {"from": "S1", "to": "S2", "weight": 1},
                # S3没有入边
            ],
        }
        is_valid, errors = validate_cfg(cfg_data)
        self.assertFalse(is_valid)
        self.assertTrue(any("Unreachable" in e or "Isolated" in e for e in errors))

    def test_empty_cfg(self):
        """空CFG应该验证失败。"""
        is_valid, errors = validate_cfg({"nodes": [], "edges": []})
        self.assertFalse(is_valid)


class TestPathExtractor(unittest.TestCase):
    """路径提取测试。"""

    def _make_borrow_cfg(self) -> CFG:
        """构建论文Figure 3的CFG。"""
        cfg_data = {
            "nodes": [
                {"id": "S1", "Statement": "The system shows GUI for a list of items to borrow"},
                {"id": "S2", "Statement": "Member selects items to borrow"},
                {"id": "S3", "Statement": "Member confirms borrow items"},
                {"id": "A1", "Statement": "Click 'Cancel' button"},
                {"id": "E1", "Statement": "The system shows the warning 'Confirm cancellation?'"},
                {"id": "S4", "Statement": "The system records the borrowed items"},
                {"id": "S5", "Statement": "The system displays a list of borrowed items"},
            ],
            "edges": [
                {"from": "S1", "to": "S2", "weight": 1},
                {"from": "S2", "to": "S3", "weight": 2},
                {"from": "S3", "to": "A1", "condition": "Click 'Cancel' button", "weight": 3},
                {"from": "A1", "to": "E1", "weight": 4},
                {"from": "E1", "to": "S5", "condition": "'Cancel' confirmed", "weight": 5},
                {"from": "S3", "to": "S4", "condition": "No 'Cancel'", "weight": 3},
                {"from": "S4", "to": "S5", "weight": 4},
            ],
        }
        return CFG(cfg_data["nodes"], cfg_data["edges"])

    def test_borrow_item_paths(self):
        """论文示例应该生成2条测试路径。"""
        cfg = self._make_borrow_cfg()
        extractor = PathExtractor()
        paths = extractor.extract_paths(cfg)

        # 论文中此用例应有2条路径:
        # 路径1: S1→S2→S3→S4→S5 (正常借书)
        # 路径2: S1→S2→S3→A1→E1→S5 (取消借书)
        self.assertEqual(len(paths), 2, f"Expected 2 paths, got {len(paths)}: {paths}")

    def test_path_content(self):
        """验证路径内容包含关键语句。"""
        cfg = self._make_borrow_cfg()
        extractor = PathExtractor()
        paths = extractor.extract_paths(cfg)

        # 至少一条路径包含cancel相关内容
        cancel_found = any(
            any("Cancel" in stmt or "cancel" in stmt for stmt in path)
            for path in paths
        )
        self.assertTrue(cancel_found, "At least one path should contain cancel flow")

    def test_linear_cfg(self):
        """线性CFG（无分支）应该只有1条路径。"""
        cfg_data = {
            "nodes": [
                {"id": "S1", "Statement": "Step 1"},
                {"id": "S2", "Statement": "Step 2"},
                {"id": "S3", "Statement": "Step 3"},
            ],
            "edges": [
                {"from": "S1", "to": "S2", "weight": 1},
                {"from": "S2", "to": "S3", "weight": 2},
            ],
        }
        cfg = CFG(cfg_data["nodes"], cfg_data["edges"])
        extractor = PathExtractor()
        paths = extractor.extract_paths(cfg)
        self.assertEqual(len(paths), 1)

    def test_diamond_cfg(self):
        """菱形CFG（if-else-merge）应该有2条路径。"""
        cfg_data = {
            "nodes": [
                {"id": "S1", "Statement": "Step 1"},
                {"id": "S2", "Statement": "Step 2 (true)"},
                {"id": "S3", "Statement": "Step 3 (false)"},
                {"id": "S4", "Statement": "Step 4 (merge)"},
            ],
            "edges": [
                {"from": "S1", "to": "S2", "condition": "condition is true", "weight": 1},
                {"from": "S1", "to": "S3", "condition": "condition is false", "weight": 1},
                {"from": "S2", "to": "S4", "weight": 2},
                {"from": "S3", "to": "S4", "weight": 2},
            ],
        }
        cfg = CFG(cfg_data["nodes"], cfg_data["edges"])
        extractor = PathExtractor()
        paths = extractor.extract_paths(cfg)
        self.assertEqual(len(paths), 2)


class TestCFGDataStructure(unittest.TestCase):
    """CFG数据结构测试。"""

    def test_adjacency_list(self):
        """邻接表应该正确构建。"""
        cfg_data = {
            "nodes": [
                {"id": "S1", "Statement": "Step 1"},
                {"id": "S2", "Statement": "Step 2"},
            ],
            "edges": [
                {"from": "S1", "to": "S2", "weight": 1},
            ],
        }
        cfg = CFG(cfg_data["nodes"], cfg_data["edges"])
        self.assertEqual(cfg.root, "S1")
        self.assertEqual(cfg.adj["S1"], [("S2", None)])
        self.assertEqual(cfg.adj["S2"], [])
        self.assertEqual(cfg.node_map["S1"], "Step 1")

    def test_to_json(self):
        """to_json应该返回原始数据。"""
        cfg_data = {
            "nodes": [{"id": "S1", "Statement": "Step 1"}],
            "edges": [],
        }
        cfg = CFG(cfg_data["nodes"], cfg_data["edges"])
        self.assertEqual(cfg.to_json(), cfg_data)


if __name__ == "__main__":
    unittest.main()
