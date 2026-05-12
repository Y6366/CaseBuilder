"""
Step 2: Test-Path Extraction — 从CFG枚举所有执行路径

论文 Section 3.3 实现:
- 使用DFS（深度优先搜索）从根节点开始遍历CFG
- 枚举所有从根到叶子节点的完整执行路径
- 环检测与剪枝：如果当前路径中已包含某节点，跳过（保持无环）
- 节点ID替换为对应的NL语句

输出: List[List[str]]，每条路径是一个NL语句序列
"""

import logging
from typing import Optional

from .cfg_generator import CFG

logger = logging.getLogger(__name__)


class PathExtractor:
    """
    Step 2: 从CFG中提取所有完整执行路径。

    论文方法:
    1. 从根节点开始DFS遍历
    2. 沿着邻接表探索所有分支
    3. 到达叶子节点（无出边）时记录一条完整路径
    4. 环检测: 如果目标节点已在当前路径中，跳过该边（去环）
    5. 将节点ID替换为对应的自然语言语句
    """

    def extract_paths(self, cfg: CFG) -> list[list[str]]:
        """
        从CFG提取所有完整执行路径。

        Args:
            cfg: 控制流图对象

        Returns:
            路径列表，每条路径是NL语句序列
        """
        if not cfg.root:
            return []

        node_paths = self._dfs_enumerate(cfg)
        statement_paths = self._convert_to_statements(cfg, node_paths)

        logger.info(f"Extracted {len(statement_paths)} test paths from CFG")
        for i, path in enumerate(statement_paths):
            logger.debug(f"  Path {i+1}: {' → '.join(path[:3])}{'...' if len(path) > 3 else ''}")

        return statement_paths

    def _dfs_enumerate(self, cfg: CFG) -> list[list[str]]:
        """
        DFS枚举所有从根到叶的路径。

        环检测: 如果目标节点已在当前路径中，跳过该边。
        """
        all_paths = []
        self._dfs(cfg.root, [], set(), cfg, all_paths)
        return all_paths

    def _dfs(
        self,
        current: str,
        path: list[str],
        visited: set[str],
        cfg: CFG,
        all_paths: list[list[str]],
    ):
        """递归DFS遍历。"""
        path.append(current)
        visited.add(current)

        neighbors = cfg.adj.get(current, [])

        if not neighbors:
            # 叶子节点 — 记录完整路径
            all_paths.append(list(path))
        else:
            for dst, condition in neighbors:
                if dst in visited:
                    # 环检测: 跳过已在路径中的节点
                    # 但仍然记录一条到该节点的路径（论文中去环处理）
                    continue
                self._dfs(dst, path, visited, cfg, all_paths)

        path.pop()
        visited.discard(current)

    def _convert_to_statements(
        self, cfg: CFG, node_paths: list[list[str]]
    ) -> list[list[str]]:
        """将节点ID路径转换为自然语言语句路径，包含条件文本。"""
        statement_paths = []

        for node_path in node_paths:
            stmt_path = []
            for i, node_id in enumerate(node_path):
                # 添加节点的自然语言语句
                stmt = cfg.node_map.get(node_id, node_id)
                stmt_path.append(stmt)

                # 如果有到下一个节点的条件边，也添加条件文本
                if i < len(node_path) - 1:
                    next_id = node_path[i + 1]
                    for dst, condition in cfg.adj.get(node_id, []):
                        if dst == next_id and condition:
                            stmt_path.append(condition)
                            break

            statement_paths.append(stmt_path)

        return statement_paths

    def get_adjacency_list(self, cfg: CFG) -> dict:
        """获取CFG的邻接表表示（用于调试和可视化）。"""
        return {
            node_id: [(dst, cond) for dst, cond in neighbors]
            for node_id, neighbors in cfg.adj.items()
        }
