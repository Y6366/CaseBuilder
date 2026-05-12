"""
端到端流水线 — LLMCFG-TGen 完整流程

论文 Section 3.1 实现的三步流水线:
Step ❶ CFG Generation: NL用例 → LLM → JSON格式CFG → 自动验证
Step ❷ Test-Path Extraction: CFG → DFS枚举所有执行路径 → 去环
Step ❸ Test Case Creation: 执行路径 → LLM → 结构化测试用例
"""

import json
import logging
import argparse
from datetime import datetime

from .llm_client import LLMClient
from .cfg_generator import CFGGenerator, CFG, validate_cfg
from .path_extractor import PathExtractor
from .test_creator import TestCaseCreator, TestCase

logger = logging.getLogger(__name__)


class PipelineResult:
    """流水线执行结果。"""

    def __init__(self):
        self.use_case: str = ""
        self.cfg: CFG = None
        self.test_paths: list[list[str]] = []
        self.test_cases: list[TestCase] = []
        self.timestamp: str = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "use_case": self.use_case,
            "cfg": self.cfg.to_json() if self.cfg else None,
            "test_paths": self.test_paths,
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "summary": {
                "cfg_nodes": len(self.cfg.nodes) if self.cfg else 0,
                "cfg_edges": len(self.cfg.edges) if self.cfg else 0,
                "total_paths": len(self.test_paths),
                "total_test_cases": len(self.test_cases),
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class LLMCFGTGenPipeline:
    """
    LLMCFG-TGen 端到端流水线。

    使用方式:
        pipeline = LLMCFGTGenPipeline(model="gpt-4o")
        result = pipeline.run(use_case_text)
        print(result.to_json())
    """

    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        max_cfg_retries: int = 3,
    ):
        self.llm = LLMClient(model=model, api_key=api_key, base_url=base_url)
        self.cfg_generator = CFGGenerator(self.llm, max_retries=max_cfg_retries)
        self.path_extractor = PathExtractor()

    def run(self, use_case: str, start_tc_id: int = 1) -> PipelineResult:
        """
        执行完整的LLMCFG-TGen流水线。

        Args:
            use_case: 自然语言用例描述
            start_tc_id: 测试用例起始编号

        Returns:
            PipelineResult 包含CFG、路径和测试用例
        """
        result = PipelineResult()
        result.use_case = use_case

        # Step ❶ CFG Generation
        logger.info("=" * 60)
        logger.info("Step ❶: CFG Generation")
        logger.info("=" * 60)
        cfg = self.cfg_generator.generate(use_case)
        result.cfg = cfg
        logger.info(f"  CFG: {cfg}")

        # Step ❷ Test-Path Extraction
        logger.info("=" * 60)
        logger.info("Step ❷: Test-Path Extraction")
        logger.info("=" * 60)
        paths = self.path_extractor.extract_paths(cfg)
        result.test_paths = paths
        logger.info(f"  Extracted {len(paths)} test paths")

        # Step ❸ Test Case Creation
        logger.info("=" * 60)
        logger.info("Step ❸: Test Case Creation")
        logger.info("=" * 60)
        creator = TestCaseCreator(self.llm, start_id=start_tc_id)
        test_cases = creator.create_all_test_cases(paths, use_case)
        result.test_cases = test_cases
        logger.info(f"  Generated {len(test_cases)} test cases")

        # Summary
        logger.info("=" * 60)
        logger.info("Pipeline Complete")
        logger.info(f"  CFG: {len(cfg.nodes)} nodes, {len(cfg.edges)} edges")
        logger.info(f"  Paths: {len(paths)}")
        logger.info(f"  Test Cases: {len(test_cases)}")
        logger.info("=" * 60)

        return result

    def run_from_file(self, use_case_file: str) -> PipelineResult:
        """从文件读取用例并执行流水线。"""
        with open(use_case_file, "r", encoding="utf-8") as f:
            if use_case_file.endswith(".json"):
                data = json.load(f)
                # 支持多种JSON格式
                use_case = data.get("use_case", data.get("text", json.dumps(data, indent=2, ensure_ascii=False)))
            else:
                use_case = f.read()

        return self.run(use_case)


def main():
    parser = argparse.ArgumentParser(description="LLMCFG-TGen: 从用例自动生成测试用例")
    parser.add_argument("--use-case", type=str, help="用例文本")
    parser.add_argument("--file", type=str, help="用例文件路径（.txt或.json）")
    parser.add_argument("--model", type=str, default=None, help="LLM模型名称")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    parser.add_argument("--api-key", type=str, default=None, help="API密钥")
    parser.add_argument("--base-url", type=str, default=None, help="API base URL")
    parser.add_argument("--verbose", action="store_true", help="详细日志")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not args.use_case and not args.file:
        parser.error("请提供 --use-case 或 --file 参数")

    pipeline = LLMCFGTGenPipeline(
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
    )

    if args.file:
        result = pipeline.run_from_file(args.file)
    else:
        result = pipeline.run(args.use_case)

    output = result.to_json()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"结果已保存到: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
