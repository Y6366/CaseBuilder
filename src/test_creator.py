"""
Step 3: Test Case Creation — 从执行路径生成结构化测试用例

论文 Section 3.4 实现:
- 使用Prompt #2将每条执行路径转换为结构化测试用例
- 测试用例包含: ID、描述、前置条件、测试步骤（步骤号 + 输入 + 预期结果）
- 支持批量生成
"""

import json
import logging
from typing import Optional

from .llm_client import LLMClient

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from prompts.prompt_templates import TESTCASE_SYSTEM_PROMPT, TESTCASE_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class TestCase:
    """结构化测试用例。"""

    def __init__(self, data: dict):
        self.id = data.get("id", "")
        self.description = data.get("Description", "")
        self.precondition = data.get("Precondition", "")
        self.steps = data.get("Test", [])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "Description": self.description,
            "Precondition": self.precondition,
            "Test": self.steps,
        }

    def __repr__(self):
        return f"TestCase(id={self.id}, steps={len(self.steps)})"


class TestCaseCreator:
    """
    Step 3: 将执行路径转换为结构化测试用例。

    对每条执行路径:
    1. 构建Prompt #2（路径 + 原始用例上下文）
    2. LLM生成结构化测试用例（JSON格式）
    3. 解析并返回TestCase对象
    """

    def __init__(self, llm_client: LLMClient, start_id: int = 1):
        self.llm = llm_client
        self.next_id = start_id

    def create_test_case(
        self, test_path: list[str], use_case: str
    ) -> Optional[TestCase]:
        """
        从单条执行路径生成一个测试用例。

        Args:
            test_path: 执行路径（NL语句列表）
            use_case: 原始用例文本（提供上下文）

        Returns:
            TestCase对象，或None（生成失败时）
        """
        path_text = " → ".join(test_path)
        tc_id = f"TC-{self.next_id:03d}"
        self.next_id += 1

        user_prompt = TESTCASE_USER_PROMPT_TEMPLATE.format(
            use_case=use_case,
            test_path=path_text,
        )

        try:
            tc_data = self.llm.generate_json(
                system_prompt=TESTCASE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
            )
            # 覆盖ID
            tc_data["id"] = tc_id
            tc = TestCase(tc_data)
            logger.info(f"Created test case: {tc}")
            return tc

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {tc_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating test case {tc_id}: {e}")
            return None

    def create_all_test_cases(
        self, test_paths: list[list[str]], use_case: str
    ) -> list[TestCase]:
        """
        批量从所有执行路径生成测试用例。

        Args:
            test_paths: 所有执行路径
            use_case: 原始用例文本

        Returns:
            TestCase对象列表
        """
        test_cases = []
        total = len(test_paths)

        for i, path in enumerate(test_paths):
            logger.info(f"Generating test case {i+1}/{total}...")
            tc = self.create_test_case(path, use_case)
            if tc:
                test_cases.append(tc)

        logger.info(f"Generated {len(test_cases)}/{total} test cases successfully")
        return test_cases
