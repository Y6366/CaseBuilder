#!/usr/bin/env python3
"""
CaseBuilder 快速Demo
演示完整的用例生成流程（无需真实测试工程）
"""

import json
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.codegen_agent import CodeGenAgent
from agents.intent_agent import IntentAgent
from agents.retrieval_agent import RetrievalAgent
from agents.review_agent import ReviewAgent


def print_banner():
    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║   CaseBuilder - 测试用例自动生成系统 Demo            ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()


def print_stage(stage_num, stage_name):
    print(f"\n{'─' * 50}")
    print(f"  Stage {stage_num}: {stage_name}")
    print(f"{'─' * 50}")


def print_result_box(title, content, max_lines=20):
    print(f"\n  📦 {title}:")
    print("  " + "┌" + "─" * 48 + "┐")
    lines = str(content).split("\n")
    for line in lines[:max_lines]:
        print(f"  │ {line[:46]:<46} │")
    if len(lines) > max_lines:
        print(f"  │ {'... (省略 ' + str(len(lines) - max_lines) + ' 行)':<46} │")
    print("  " + "└" + "─" * 48 + "┘")


def main():
    print_banner()

    # 配置日志
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_dir / "demo.log", encoding="utf-8"), logging.StreamHandler()],
    )

    # Demo用例描述
    demo_cases = [
        "deepseek r1 671b，vllm推理，bf16权重，910b3环境32p，CEVAL一致性测试",
        "deepseek v3 671b，vllm推理，int8权重，910b3环境16p，性能验证",
        "deepseek r1 671b，vllm推理，w4a8量化，910b3环境8p，性能精度验证",
    ]

    print("  可选Demo场景:")
    for i, case in enumerate(demo_cases):
        print(f"  [{i + 1}] {case}")
    print()

    choice = input("  请选择 [1-3] (默认1): ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(demo_cases):
            idx = 0
    except (ValueError, IndexError):
        idx = 0

    user_description = demo_cases[idx]
    print(f"\n  📝 选择的场景: {user_description}")

    # 初始化Agent
    print("\n  初始化Agent...")
    intent_agent = IntentAgent(
        method_glossary_path=str(PROJECT_ROOT / "knowledge/method_glossary.json"),
        scene_patterns_path=str(PROJECT_ROOT / "knowledge/rules/scene_patterns.md"),
    )
    retrieval_agent = RetrievalAgent(
        context_dir=str(PROJECT_ROOT / "context_output"),
        method_glossary_path=str(PROJECT_ROOT / "knowledge/method_glossary.json"),
        templates_dir=str(PROJECT_ROOT / "knowledge/templates"),
        rules_dir=str(PROJECT_ROOT / "knowledge/rules"),
    )
    codegen_agent = CodeGenAgent(
        templates_dir=str(PROJECT_ROOT / "knowledge/templates"),
        rules_path=str(PROJECT_ROOT / "knowledge/rules/coding_rules.md"),
    )
    review_agent = ReviewAgent(
        method_glossary_path=str(PROJECT_ROOT / "knowledge/method_glossary.json"),
        rules_path=str(PROJECT_ROOT / "knowledge/rules/coding_rules.md"),
    )
    print("  ✓ 所有Agent就绪")

    input("\n  按Enter开始生成...")

    # Stage 1: 意图识别
    print_stage(1, "意图识别")
    start = time.time()
    intent = intent_agent.recognize(user_description)
    elapsed = time.time() - start

    print_result_box("意图识别结果", json.dumps(intent, indent=2, ensure_ascii=False))
    print(f"  ⏱ 耗时: {elapsed:.2f}s")

    input("\n  按Enter继续...")

    # Stage 2: 知识检索
    print_stage(2, "知识检索")
    start = time.time()
    knowledge = retrieval_agent.retrieve(intent)
    elapsed = time.time() - start

    print("  📚 检索到:")
    print(f"     - 方法定义: {len(knowledge.get('method_details', []))} 个")
    print(f"     - 相似用例: {len(knowledge.get('similar_cases', []))} 个")
    print(f"  ⏱ 耗时: {elapsed:.2f}s")

    input("\n  按Enter继续...")

    # Stage 3: 代码生成
    print_stage(3, "代码生成")
    start = time.time()
    code_result = codegen_agent.generate(intent, knowledge)
    elapsed = time.time() - start

    print_result_box(f"生成代码 ({code_result['file_name']})", code_result["code"], max_lines=40)
    print(f"  ⏱ 耗时: {elapsed:.2f}s")
    if code_result.get("warnings"):
        for w in code_result["warnings"]:
            print(f"  ⚠️ {w}")

    input("\n  按Enter继续...")

    # Stage 4: 质量校验
    print_stage(4, "质量校验")
    start = time.time()
    review_report = review_agent.review(code_result["code"], intent)
    elapsed = time.time() - start

    passed_icon = "✅ 通过" if review_report["passed"] else "❌ 未通过"
    print(f"  {passed_icon}")
    print(f"  得分: {review_report['score']}/100")
    print(f"  {review_report['summary']}")
    if review_report["issues"]:
        print("  问题列表:")
        for issue in review_report["issues"]:
            icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue["severity"], "•")
            print(f"    {icon} [{issue['severity']}] {issue['message']}")
    print(f"  ⏱ 耗时: {elapsed:.2f}s")

    # 保存输出
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / code_result["file_name"]
    output_file.write_text(code_result["code"], encoding="utf-8")

    print(f"\n  💾 代码已保存到: {output_file}")

    print()
    print("╔══════════════════════════════════════════════════════╗")
    print("║   Demo 完成! 🎉                                      ║")
    print("╚══════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
