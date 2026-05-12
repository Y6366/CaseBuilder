#!/usr/bin/env python3
"""
质量校验Agent - Review Agent
负责对生成的代码进行多维度质量校验
"""

import ast
import json
import logging
from pathlib import Path

logger = logging.getLogger("CaseBuilder.ReviewAgent")


class ReviewAgent:
    """
    质量校验Agent

    输入: 生成的测试用例代码
    输出: 校验报告 (pass/fail + 问题列表)

    校验维度:
    1. AST语法合法性
    2. 代码结构完整性（setup/test_run/teardown）
    3. 方法调用合法性（对比方法词典）
    4. import正确性
    5. 命名规范一致性
    6. 装饰器完整性
    7. 日志语句规范性
    """

    def __init__(
        self,
        method_glossary_path: str = "knowledge/method_glossary.json",
        rules_path: str = "knowledge/rules/coding_rules.md",
    ):
        self.method_glossary = self._load_json(method_glossary_path)
        self.coding_rules = self._load_md(rules_path)
        logger.info("ReviewAgent 初始化完成")

    def _load_json(self, path: str) -> dict:
        p = Path(path)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _load_md(self, path: str) -> str:
        p = Path(path)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def review(self, code: str, intent: dict = None) -> dict:
        """
        执行质量校验

        Args:
            code: 生成的代码字符串
            intent: 原始意图（用于交叉校验）

        Returns:
            {
                "passed": bool,
                "score": float (0-100),
                "issues": [{"severity": "error/warning/info", "message": str, "suggestion": str}],
                "summary": str
            }
        """
        logger.info("开始质量校验...")
        issues = []

        # 1. AST语法检查
        syntax_ok, syntax_issues = self._check_syntax(code)
        issues.extend(syntax_issues)
        if not syntax_ok:
            logger.error("AST语法检查失败，跳过后续检查")
            return self._build_report(issues, early_exit=True)

        # 2. 代码结构检查
        issues.extend(self._check_structure(code))

        # 3. 方法调用合法性检查
        issues.extend(self._check_method_calls(code))

        # 4. import检查
        issues.extend(self._check_imports(code, intent))

        # 5. 命名规范检查
        issues.extend(self._check_naming(code))

        # 6. 装饰器检查
        issues.extend(self._check_decorators(code))

        # 7. 日志规范性检查
        issues.extend(self._check_logging(code))

        # 8. 与意图交叉校验
        if intent:
            issues.extend(self._check_intent_alignment(code, intent))

        report = self._build_report(issues)
        logger.info(f"质量校验完成: {'通过' if report['passed'] else '未通过'}, 得分: {report['score']}")
        return report

    def _check_syntax(self, code: str) -> tuple[bool, list]:
        """AST语法检查"""
        issues = []
        try:
            ast.parse(code)
            logger.info("✓ AST语法检查通过")
            return True, issues
        except SyntaxError as e:
            msg = f"语法错误: 第{e.lineno}行 - {e.msg}"
            logger.error(f"✗ {msg}")
            issues.append({"severity": "error", "message": msg, "suggestion": "检查代码生成逻辑，修复语法错误"})
            return False, issues

    def _check_structure(self, code: str) -> list:
        """代码结构完整性检查"""
        issues = []
        tree = ast.parse(code)

        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        if not classes:
            issues.append({"severity": "error", "message": "未找到类定义", "suggestion": "确保代码包含测试类"})
            return issues

        cls = classes[0]
        methods = {node.name for node in cls.body if isinstance(node, ast.FunctionDef)}

        required_methods = {"setup", "test_run", "teardown"}
        missing = required_methods - methods
        if missing:
            for m in missing:
                issues.append({"severity": "error", "message": f"缺少必要方法: {m}", "suggestion": f"添加 {m} 方法"})
        else:
            logger.info("✓ 代码结构完整性检查通过")

        # 检查setup调用super
        if "setup" in methods:
            setup_func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "setup")
            setup_code = ast.unparse(setup_func) if hasattr(ast, "unparse") else ""
            if "super(" not in setup_code:
                issues.append(
                    {
                        "severity": "warning",
                        "message": "setup方法未调用super().setup()",
                        "suggestion": "添加父类setup调用",
                    }
                )

        # 检查teardown调用super
        if "teardown" in methods:
            teardown_func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "teardown")
            teardown_code = ast.unparse(teardown_func) if hasattr(ast, "unparse") else ""
            if "super(" not in teardown_code:
                issues.append(
                    {
                        "severity": "warning",
                        "message": "teardown方法未调用super().teardown()",
                        "suggestion": "添加父类teardown调用",
                    }
                )

        return issues

    def _check_method_calls(self, code: str) -> list:
        """方法调用合法性检查"""
        issues = []
        tree = ast.parse(code)

        known_methods = set(self.method_glossary.get("methods", {}).keys())
        known_methods.update({"setup", "teardown", "test_run"})

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
                if method_name.startswith("_"):
                    continue
                # ms_log的方法(info/step/error/warning)和pytest装饰器属性不算未知方法
                _whitelist = {
                    "info",
                    "step",
                    "error",
                    "warning",
                    "debug",
                    "critical",
                    "timeout",
                    "level1",
                    "skip",
                    "xfail",
                    "parametrize",
                    "format",
                    "append",
                    "extend",
                    "keys",
                    "values",
                    "items",
                }
                if method_name not in known_methods and method_name not in _whitelist:
                    issues.append(
                        {
                            "severity": "warning",
                            "message": f"调用了未知方法: {method_name}",
                            "suggestion": "检查方法名是否正确，或将其添加到方法词典",
                        }
                    )

        if not any(i["severity"] == "warning" and "未知方法" in i["message"] for i in issues):
            logger.info("✓ 方法调用合法性检查通过")

        return issues

    def _check_imports(self, code: str, intent: dict = None) -> list:
        """import正确性检查"""
        issues = []
        tree = ast.parse(code)

        has_pytest = False
        has_base_class_import = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "pytest":
                        has_pytest = True
            elif isinstance(node, ast.ImportFrom) and node.module and "network.net" in node.module:
                has_base_class_import = True

        if not has_pytest:
            issues.append({"severity": "error", "message": "缺少 pytest import", "suggestion": "添加 import pytest"})

        if not has_base_class_import:
            issues.append(
                {
                    "severity": "warning",
                    "message": "未找到网络基类import",
                    "suggestion": "添加如: from common.ms_aw.network.net.deepseek import Deepseek",
                }
            )

        if not issues:
            logger.info("✓ import检查通过")

        return issues

    def _check_naming(self, code: str) -> list:
        """命名规范检查"""
        issues = []
        tree = ast.parse(code)

        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        for cls in classes:
            if not cls.name.startswith("Test_"):
                issues.append(
                    {
                        "severity": "warning",
                        "message": f"类名不符合规范: {cls.name}（应以Test_开头）",
                        "suggestion": "重命名为 Test_...",
                    }
                )

        if not issues:
            logger.info("✓ 命名规范检查通过")

        return issues

    def _check_decorators(self, code: str) -> list:
        """装饰器完整性检查"""
        issues = []
        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "test_run":
                decorator_names = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Attribute):
                        decorator_names.append(dec.attr)
                    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        decorator_names.append(dec.func.attr)

                if "timeout" not in decorator_names:
                    issues.append(
                        {
                            "severity": "warning",
                            "message": "test_run缺少 @pytest.mark.timeout 装饰器",
                            "suggestion": "添加超时装饰器",
                        }
                    )
                if "level1" not in decorator_names:
                    issues.append(
                        {
                            "severity": "info",
                            "message": "test_run缺少 @pytest.mark.level1 装饰器",
                            "suggestion": "添加用例级别装饰器",
                        }
                    )

        if not issues:
            logger.info("✓ 装饰器检查通过")

        return issues

    def _check_logging(self, code: str) -> list:
        """日志规范性检查"""
        issues = []

        if "self.ms_log" not in code:
            issues.append(
                {
                    "severity": "warning",
                    "message": "未使用 ms_log 进行日志记录",
                    "suggestion": "使用 self.ms_log.step/info/error 记录日志",
                }
            )

        if "self.ms_log.step" not in code:
            issues.append(
                {
                    "severity": "info",
                    "message": "未使用 ms_log.step 标记步骤",
                    "suggestion": "使用 self.ms_log.step('1.描述') 标记测试步骤",
                }
            )

        if not issues:
            logger.info("✓ 日志规范性检查通过")

        return issues

    def _check_intent_alignment(self, code: str, intent: dict) -> list:
        """与意图交叉校验"""
        issues = []

        base_class = intent.get("case_metadata", {}).get("base_class", "")
        if base_class and base_class not in code:
            issues.append(
                {
                    "severity": "error",
                    "message": f"代码中未使用意图指定的基类: {base_class}",
                    "suggestion": f"确保继承 {base_class}",
                }
            )

        # 方法名别名映射（意图名 -> 代码中可能的变体）
        alias_map = {
            "start_vllm_server": ["vllm_server_start", "start_server"],
            "stop_vllm_server": ["stop_vllm_server", "teardown"],
        }

        logic_plan = intent.get("logic_plan", {})
        for phase in ["setup", "execution", "assertion", "teardown"]:
            for action in logic_plan.get(phase, []):
                action_name = action["action"]
                # 检查直接匹配和别名匹配
                aliases = alias_map.get(action_name, [])
                found = f"self.{action_name}" in code
                if not found:
                    for alias in aliases:
                        if f"self.{alias}" in code or alias in code:
                            found = True
                            break
                if not found:
                    issues.append(
                        {
                            "severity": "warning",
                            "message": f"意图中的action未在代码中出现: {action_name}",
                            "suggestion": f"确保调用了 self.{action_name}()",
                        }
                    )

        return issues

    def _build_report(self, issues: list, early_exit: bool = False) -> dict:
        """构建校验报告"""
        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]
        infos = [i for i in issues if i["severity"] == "info"]

        passed = len(errors) == 0 and not early_exit

        score = 100
        score -= len(errors) * 20
        score -= len(warnings) * 5
        score -= len(infos) * 2
        score = max(0, score)

        summary = (
            f"校验结果: {'通过' if passed else '未通过'} | 得分: {score}/100 | "
            f"错误: {len(errors)} | 警告: {len(warnings)} | 建议: {len(infos)}"
        )

        if early_exit:
            summary = "语法检查失败，校验提前终止"
            score = 0
            passed = False

        return {"passed": passed, "score": score, "issues": issues, "summary": summary}
