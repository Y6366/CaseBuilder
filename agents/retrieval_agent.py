#!/usr/bin/env python3
"""
知识检索Agent - Knowledge Retrieval Agent
负责从多维上下文中检索与当前用例相关的知识
"""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("CaseBuilder.RetrievalAgent")


class RetrievalAgent:
    """
    知识检索Agent

    输入: 意图JSON (来自IntentAgent)
    输出: 检索到的相关上下文（方法签名、调用链、依赖关系、已有用例参考）

    职责:
    1. 从V1视图获取仓库骨架和模块签名
    2. 从V2视图获取依赖关系和调用链
    3. 从方法词典获取方法详细定义
    4. 从场景模式库获取匹配的流程模板
    5. 检索最相似的已有用例作为参考
    """

    def __init__(
        self,
        context_dir: str = "context_output",
        method_glossary_path: str = "knowledge/method_glossary.json",
        templates_dir: str = "knowledge/templates",
        rules_dir: str = "knowledge/rules",
    ):
        self.context_dir = Path(context_dir)
        self.method_glossary = self._load_json(method_glossary_path)
        self.templates_dir = Path(templates_dir)
        self.rules_dir = Path(rules_dir)

        # 加载上下文视图
        self.skeleton = self._load_md(self.context_dir / "V1_REPO_SKELETON.md")
        self.signatures = self._load_md(self.context_dir / "V1_MODULE_SIGNATURES.md")
        self.dependencies = self._load_md(self.context_dir / "V2_DEPENDENCY_GRAPH.md")
        self.call_trace = self._load_md(self.context_dir / "V2_CALL_TRACE.md")

        logger.info("RetrievalAgent 初始化完成")

    def _load_json(self, path: str) -> dict:
        p = Path(path)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_md(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def retrieve(self, intent: dict) -> dict:
        """
        执行知识检索

        Args:
            intent: 意图识别结果JSON

        Returns:
            检索到的相关上下文
        """
        logger.info("开始知识检索...")

        metadata = intent.get("case_metadata", {})
        tags = intent.get("identified_tags", [])
        logic_plan = intent.get("logic_plan", {})

        result = {
            "base_class_info": self._get_base_class_info(metadata),
            "method_details": self._get_method_details(logic_plan),
            "similar_cases": self._find_similar_cases(tags, metadata),
            "call_chain_examples": self._get_call_chain_examples(tags),
            "import_references": self._get_import_references(tags, metadata),
            "scene_rules": self._get_scene_rules(tags),
            "template": self._get_template(intent),
        }

        logger.info(f"知识检索完成: {len(result['method_details'])}个方法, {len(result['similar_cases'])}个相似用例")
        return result

    def _get_base_class_info(self, metadata: dict) -> dict:
        """获取基类信息"""
        base_class = metadata.get("base_class", "Deepseek")
        info = {"name": base_class, "methods": [], "file": ""}

        # 从signatures中提取基类方法
        if self.signatures:
            pattern = rf"- \*\*{base_class}\*\*.*?(?=##|\Z)"
            match = re.search(pattern, self.signatures, re.DOTALL)
            if match:
                info["signature_section"] = match.group(0)[:2000]

        # 从dependencies中提取基类文件位置
        if self.dependencies:
            pattern = rf"- `{base_class}` 实现在 -> `([^`]+)`"
            matches = re.findall(pattern, self.dependencies)
            if matches:
                info["file"] = matches[0]

        logger.info(f"基类信息: {base_class}, 文件: {info.get('file', '未知')}")
        return info

    def _get_method_details(self, logic_plan: dict) -> list:
        """获取logic_plan中所有方法的详细定义"""
        methods_info = []
        all_actions = []
        for phase in ["setup", "execution", "assertion", "teardown"]:
            all_actions.extend(logic_plan.get(phase, []))

        glossary_methods = self.method_glossary.get("methods", {})

        for action in all_actions:
            action_name = action.get("action", "")
            if action_name in glossary_methods:
                method_def = glossary_methods[action_name]
                methods_info.append(
                    {"name": action_name, "definition": method_def, "params_from_intent": action.get("params", {})}
                )
            else:
                methods_info.append(
                    {
                        "name": action_name,
                        "definition": {"desc": "未在词典中找到定义", "category": "unknown"},
                        "params_from_intent": action.get("params", {}),
                    }
                )

        return methods_info

    def _find_similar_cases(self, tags: list, metadata: dict) -> list:
        """从上下文中查找相似用例"""
        similar = []
        network = metadata.get("network", "")

        if self.skeleton:
            lines = self.skeleton.split("\n")
            for line in lines:
                if network in line.lower() and line.strip().startswith("- test_"):
                    similar.append({"file": line.strip("- ").strip(), "relevance": "high"})
                elif line.strip().startswith("- test_") and any(t in line.lower() for t in ["deepseek", "vllm"]):
                    similar.append({"file": line.strip("- ").strip(), "relevance": "medium"})

        return similar[:5]

    def _get_call_chain_examples(self, tags: list) -> str:
        """获取相关调用链示例"""
        if not self.call_trace:
            return ""

        relevant_sections = []
        sections = self.call_trace.split("### 来源文件:")

        for section in sections:
            if any(tag in section.lower() for tag in tags[:3]):
                relevant_sections.append("### 来源文件:" + section[:1000])

        result = "\n".join(relevant_sections[:3])
        logger.info(f"找到 {len(relevant_sections)} 个相关调用链")
        return result

    def _get_import_references(self, tags: list, metadata: dict) -> list:
        """获取import参考"""
        imports = metadata.get("imports", [])
        references = list(imports)

        if self.dependencies:
            for tag in tags[:3]:
                pattern = rf"### `([^`]*{tag}[^`]*)` 依赖于:(.*?)(?=###|\Z)"
                matches = re.findall(pattern, self.dependencies, re.DOTALL)
                for match in matches[:2]:
                    references.append(f"参考: {match[0]} -> {match[1][:200]}")

        return references[:10]

    def _get_scene_rules(self, tags: list) -> str:
        """获取场景规则"""
        rules_path = self.rules_dir / "scene_patterns.md"
        if rules_path.exists():
            content = rules_path.read_text(encoding="utf-8")
            if any(t in tags for t in ["det"]) and "模式3:" in content:
                idx = content.find("模式3:")
                return content[idx : idx + 800]
            if any(t in tags for t in ["perf"]) and "模式1:" in content:
                idx = content.find("模式1:")
                return content[idx : idx + 800]
            if any(t in tags for t in ["acc"]) and "模式2:" in content:
                idx = content.find("模式2:")
                return content[idx : idx + 800]
            return content[:2000]
        return ""

    def _get_template(self, intent: dict) -> str:
        """获取匹配的代码模板"""
        tags = intent.get("identified_tags", [])

        if "det" in tags:
            template_path = self.templates_dir / "vllm_det_template.py"
        else:
            template_path = self.templates_dir / "vllm_perf_acc_template.py"

        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return ""
