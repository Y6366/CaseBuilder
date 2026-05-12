"""
Step 1: CFG Generation — 从NL用例生成结构化CFG

论文 Section 3.2 实现:
- Prompt #1: 用例 → LLM → JSON格式CFG
- CFG验证: 检查孤立节点、不可达节点、孤儿引用
- 失败时自动重新生成（最多max_retries次）
"""

import json
import logging
from typing import Optional

from .llm_client import LLMClient

# 将prompts目录加入导入路径
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from prompts.prompt_templates import CFG_SYSTEM_PROMPT, CFG_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class CFG:
    """控制流图数据结构。"""

    def __init__(self, nodes: list[dict], edges: list[dict]):
        self.nodes = nodes  # [{"id": "S1", "Statement": "..."}, ...]
        self.edges = edges  # [{"from": "S1", "to": "S2", "weight": 1, "condition": "..."}, ...]

        # 构建邻接表
        self.adj: dict[str, list[tuple[str, Optional[str]]]] = {}
        self.node_map: dict[str, str] = {}  # id -> statement
        self.root: str = nodes[0]["id"] if nodes else None

        for node in nodes:
            self.adj[node["id"]] = []
            self.node_map[node["id"]] = node["Statement"]

        for edge in edges:
            src = edge["from"]
            dst = edge["to"]
            condition = edge.get("condition", None)
            self.adj[src].append((dst, condition))

    def to_json(self) -> dict:
        return {"nodes": self.nodes, "edges": self.edges}

    def __repr__(self):
        return f"CFG(nodes={len(self.nodes)}, edges={len(self.edges)}, root={self.root})"


def validate_cfg(cfg_data: dict) -> tuple[bool, list[str]]:
    """
    验证CFG的结构完整性。

    论文 Section 3.2.3 定义的三个无效条件:
    1. 孤立节点: 节点不出现在任何边中
    2. 不可达的"次根": 非根节点没有入边
    3. 孤儿引用: 边引用了不存在的节点ID

    Returns:
        (is_valid, error_messages)
    """
    errors = []
    nodes = cfg_data.get("nodes", [])
    edges = cfg_data.get("edges", [])

    if not nodes:
        errors.append("CFG has no nodes")
        return False, errors

    node_ids = {n["id"] for n in nodes}
    root_id = nodes[0]["id"]

    # 收集所有出现在边中的节点ID
    from_ids = set()
    to_ids = set()
    for edge in edges:
        from_ids.add(edge["from"])
        to_ids.add(edge["to"])

        # 检查孤儿引用
        if edge["from"] not in node_ids:
            errors.append(f"Orphaned reference: edge from '{edge['from']}' does not exist in nodes")
        if edge["to"] not in node_ids:
            errors.append(f"Orphaned reference: edge to '{edge['to']}' does not exist in nodes")

    # 检查孤立节点
    edge_node_ids = from_ids | to_ids
    for nid in node_ids:
        if nid not in edge_node_ids:
            errors.append(f"Isolated node: '{nid}' does not appear in any edge")

    # 检查不可达的次根
    for nid in node_ids:
        if nid != root_id and nid not in to_ids:
            errors.append(f"Unreachable node: '{nid}' has no incoming edges")

    return len(errors) == 0, errors


class CFGGenerator:
    """
    Step 1: 从NL用例描述生成CFG。

    流程:
    1. 构建Prompt #1（角色 + 指令 + 算法 + 输出格式 + 用例）
    2. 调用LLM生成JSON格式CFG
    3. 验证CFG结构完整性
    4. 若无效，重新生成（最多max_retries次）
    """

    def __init__(self, llm_client: LLMClient, max_retries: int = 3):
        self.llm = llm_client
        self.max_retries = max_retries

    def generate(self, use_case: str) -> CFG:
        """
        从NL用例描述生成CFG。

        Args:
            use_case: 自然语言用例描述文本

        Returns:
            CFG对象

        Raises:
            ValueError: 超过最大重试次数仍无法生成有效CFG
        """
        user_prompt = CFG_USER_PROMPT_TEMPLATE.format(use_case=use_case)

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"CFG generation attempt {attempt}/{self.max_retries}")

            try:
                cfg_data = self.llm.generate_json(
                    system_prompt=CFG_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                )

                is_valid, errors = validate_cfg(cfg_data)
                if is_valid:
                    logger.info(f"CFG generated successfully: {len(cfg_data['nodes'])} nodes, {len(cfg_data['edges'])} edges")
                    return CFG(cfg_data["nodes"], cfg_data["edges"])
                else:
                    logger.warning(f"CFG validation failed (attempt {attempt}): {errors}")
                    # 将错误信息反馈给LLM重新生成
                    user_prompt = CFG_USER_PROMPT_TEMPLATE.format(use_case=use_case) + \
                        f"\n\nNote: Previous attempt failed validation: {'; '.join(errors)}. Please fix these issues."

            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error (attempt {attempt}): {e}")
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt}): {e}")

        raise ValueError(f"Failed to generate valid CFG after {self.max_retries} attempts")
