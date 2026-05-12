#!/usr/bin/env python3
"""
工作流编排器 - Workflow Orchestrator
串联所有Agent的执行流程，提供完整的用例生成Pipeline
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import contextlib

from agents.codegen_agent import CodeGenAgent
from agents.intent_agent import IntentAgent
from agents.retrieval_agent import RetrievalAgent
from agents.review_agent import ReviewAgent

logger = logging.getLogger("CaseBuilder.Orchestrator")


class Orchestrator:
    """
    工作流编排器

    执行流程:
    用户输入 -> 意图识别 -> 知识检索 -> 代码生成 -> 质量校验 -> 输出

    每个阶段之间设置检查点，支持人工确认。
    """

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config = self._load_config(config_path)
        self.project_root = PROJECT_ROOT
        self._setup_logging()
        self._init_agents()
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.artifacts = {}
        logger.info(f"Orchestrator 初始化完成, run_id={self.run_id}")

    def _load_config(self, config_path: str) -> dict:
        """加载配置（简单YAML解析，无第三方依赖）"""
        config_file = self.project_root / config_path
        if config_file.exists():
            config = {}
            with open(config_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if ":" in line and not line.startswith("#"):
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if value.lower() in ("true", "false"):
                            value = value.lower() == "true"
                        elif value.isdigit():
                            value = int(value)
                        elif value and "." in value:
                            with contextlib.suppress(ValueError):
                                value = float(value)
                        if key and value != "":
                            config[key] = value
            return config

        logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
        return {
            "enable_human_checkpoint": True,
            "enable_review": True,
            "max_review_retries": 2,
            "keep_artifacts": True,
            "log_dir": "logs",
            "output_dir": "output",
        }

    def _setup_logging(self):
        """配置日志"""
        log_dir = self.project_root / self.config.get("log_dir", "logs")
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        root_logger = logging.getLogger("CaseBuilder")
        root_logger.setLevel(logging.INFO)

        # 避免重复添加handler
        if not root_logger.handlers:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            root_logger.addHandler(fh)

            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            root_logger.addHandler(ch)

        self.log_file = log_file

    def _init_agents(self):
        """初始化所有Agent"""
        logger.info("=" * 60)
        logger.info("初始化Agent集合...")
        logger.info("=" * 60)

        self.intent_agent = IntentAgent(
            method_glossary_path=str(self.project_root / "knowledge/method_glossary.json"),
            scene_patterns_path=str(self.project_root / "knowledge/rules/scene_patterns.md"),
        )

        context_dir = self.project_root / self.config.get("context_output_dir", "context_output")
        self.retrieval_agent = RetrievalAgent(
            context_dir=str(context_dir),
            method_glossary_path=str(self.project_root / "knowledge/method_glossary.json"),
            templates_dir=str(self.project_root / "knowledge/templates"),
            rules_dir=str(self.project_root / "knowledge/rules"),
        )

        self.codegen_agent = CodeGenAgent(
            templates_dir=str(self.project_root / "knowledge/templates"),
            rules_path=str(self.project_root / "knowledge/rules/coding_rules.md"),
        )

        self.review_agent = ReviewAgent(
            method_glossary_path=str(self.project_root / "knowledge/method_glossary.json"),
            rules_path=str(self.project_root / "knowledge/rules/coding_rules.md"),
        )

        logger.info("所有Agent初始化完成 ✓")

    def run(self, user_description: str, output_path: str = None) -> dict:
        """
        执行完整的用例生成流程

        Args:
            user_description: 用户的测试场景描述
            output_path: 可选的输出路径

        Returns:
            完整的执行结果
        """
        start_time = time.time()
        logger.info("=" * 60)
        logger.info(f"开始用例生成流程 | run_id={self.run_id}")
        logger.info(f"用户描述: {user_description}")
        logger.info("=" * 60)

        # ============ Stage 1: 意图识别 ============
        logger.info("\n" + "─" * 40)
        logger.info("Stage 1/4: 意图识别")
        logger.info("─" * 40)

        intent = self.intent_agent.recognize(user_description)
        self.artifacts["intent"] = intent

        logger.info("意图识别结果:")
        logger.info(json.dumps(intent, indent=2, ensure_ascii=False, default=str))

        if self.config.get("enable_human_checkpoint", True) and not self._checkpoint("意图识别"):
            logger.info("用户在意图识别阶段终止流程")
            return self._build_result("cancelled", intent=intent)

        # ============ Stage 2: 知识检索 ============
        logger.info("\n" + "─" * 40)
        logger.info("Stage 2/4: 知识检索")
        logger.info("─" * 40)

        knowledge = self.retrieval_agent.retrieve(intent)
        self.artifacts["knowledge"] = knowledge

        logger.info(f"检索到 {len(knowledge.get('method_details', []))} 个方法定义")
        logger.info(f"检索到 {len(knowledge.get('similar_cases', []))} 个相似用例")

        if self.config.get("enable_human_checkpoint", True) and not self._checkpoint("知识检索"):
            logger.info("用户在知识检索阶段终止流程")
            return self._build_result("cancelled", intent=intent, knowledge=knowledge)

        # ============ Stage 3: 代码生成 ============
        logger.info("\n" + "─" * 40)
        logger.info("Stage 3/4: 代码生成")
        logger.info("─" * 40)

        code_result = self.codegen_agent.generate(intent, knowledge)
        self.artifacts["code_result"] = code_result

        logger.info(f"生成代码: {code_result['file_name']}")
        logger.info(f"代码行数: {code_result['code'].count(chr(10))}")
        if code_result.get("warnings"):
            for w in code_result["warnings"]:
                logger.warning(f"⚠ {w}")

        # ============ Stage 4: 质量校验 ============
        logger.info("\n" + "─" * 40)
        logger.info("Stage 4/4: 质量校验")
        logger.info("─" * 40)

        max_retries = int(self.config.get("max_review_retries", 2))
        review_passed = False

        if not self.config.get("enable_review", True):
            review_passed = True
            review_report = {"passed": True, "score": 100, "issues": [], "summary": "校验已跳过"}
        else:
            for attempt in range(1, max_retries + 1):
                logger.info(f"校验尝试 {attempt}/{max_retries}")

                review_report = self.review_agent.review(code_result["code"], intent)
                self.artifacts[f"review_report_attempt_{attempt}"] = review_report

                logger.info(f"校验结果: {review_report['summary']}")

                if review_report["passed"]:
                    review_passed = True
                    break
                else:
                    if attempt < max_retries:
                        logger.warning(f"校验未通过，准备第{attempt + 1}次重试...")
                        for issue in review_report["issues"]:
                            if issue["severity"] in ("error", "warning"):
                                logger.warning(f"  [{issue['severity']}] {issue['message']}")
                    else:
                        logger.error("校验未通过，已达到最大重试次数")

        self.artifacts["review_report"] = review_report

        # ============ 输出结果 ============
        logger.info("\n" + "=" * 60)

        output_dir = self.project_root / self.config.get("output_dir", "output")
        output_dir.mkdir(exist_ok=True)

        file_name = code_result["file_name"]
        file_path = output_dir / file_name

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code_result["code"])
        logger.info(f"代码已保存: {file_path}")

        # 保存中间产物
        if self.config.get("keep_artifacts", True):
            artifacts_dir = output_dir / f".artifacts_{self.run_id}"
            artifacts_dir.mkdir(exist_ok=True)

            for name, data in self.artifacts.items():
                artifact_path = artifacts_dir / f"{name}.json"
                with open(artifact_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"中间产物已保存: {artifacts_dir}")

        elapsed = time.time() - start_time
        status = "success" if review_passed else "review_failed"

        logger.info(f"流程完成 | 状态: {status} | 耗时: {elapsed:.2f}s")
        logger.info("=" * 60)

        return self._build_result(
            status=status,
            intent=intent,
            knowledge=knowledge,
            code_result=code_result,
            review_report=review_report,
            output_file=str(file_path),
            elapsed=elapsed,
        )

    def _checkpoint(self, stage_name: str) -> bool:
        """人工检查点"""
        logger.info(f"📋 检查点 [{stage_name}]: 查看上方输出，是否继续？")
        try:
            response = input("  继续？[Y/n]: ").strip().lower()
            if response in ("n", "no"):
                return False
        except EOFError:
            pass
        return True

    def _build_result(self, status: str, **kwargs) -> dict:
        """构建执行结果"""
        return {"run_id": self.run_id, "status": status, "timestamp": datetime.now().isoformat(), **kwargs}


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="CaseBuilder - 测试用例自动生成系统")
    parser.add_argument("description", nargs="?", help="测试场景描述")
    parser.add_argument("--config", default="config/settings.yaml", help="配置文件路径")
    parser.add_argument("--no-checkpoint", action="store_true", help="跳过人工检查点")
    parser.add_argument("--no-review", action="store_true", help="跳过质量校验")
    parser.add_argument("--output", "-o", help="输出文件路径")

    args = parser.parse_args()

    if not args.description:
        print("=" * 50)
        print("  CaseBuilder - 测试用例自动生成系统")
        print("=" * 50)
        print()
        args.description = input("请输入测试场景描述: ").strip()
        if not args.description:
            print("错误: 描述不能为空")
            sys.exit(1)

    orchestrator = Orchestrator(config_path=args.config)

    if args.no_checkpoint:
        orchestrator.config["enable_human_checkpoint"] = False
    if args.no_review:
        orchestrator.config["enable_review"] = False

    result = orchestrator.run(args.description, output_path=args.output)

    print()
    print("=" * 50)
    if result["status"] == "success":
        print("✅ 用例生成成功!")
        print(f"   输出文件: {result.get('output_file', 'N/A')}")
    elif result["status"] == "review_failed":
        print("⚠️  用例已生成但校验未通过")
        print(f"   输出文件: {result.get('output_file', 'N/A')}")
        print("   请检查校验报告并手动修复")
    else:
        print("❌ 流程已取消")
    print("=" * 50)

    return result


if __name__ == "__main__":
    main()
