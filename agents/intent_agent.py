#!/usr/bin/env python3
"""
意图识别Agent - Intent Recognition Agent
负责将用户自然语言描述转换为结构化的用例意图JSON
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("CaseBuilder.IntentAgent")


class IntentAgent:
    """
    意图识别Agent

    输入: 用户自然语言描述
    输出: 结构化用例意图JSON (case_metadata + logic_plan + identified_tags)

    职责:
    1. 识别网络类型（deepseek/qwen/llama等）
    2. 识别测试类型（性能/精度/一致性）
    3. 识别推理框架（vllm/mindie）
    4. 识别模型规格（参数量/量化方式/卡数）
    5. 根据场景模式生成logic_plan
    6. 匹配公共方法词典生成action列表
    """

    def __init__(self, method_glossary_path: str = None, scene_patterns_path: str = None):
        self.method_glossary = self._load_json(method_glossary_path or "knowledge/method_glossary.json")
        self.scene_patterns = self._load_md(scene_patterns_path or "knowledge/rules/scene_patterns.md")
        logger.info("IntentAgent 初始化完成")

    def _load_json(self, path: str) -> dict:
        p = Path(path)
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        logger.warning(f"词典文件不存在: {path}，使用空词典")
        return {}

    def _load_md(self, path: str) -> str:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    def recognize(self, user_description: str, context: dict = None) -> dict:
        """
        执行意图识别

        Args:
            user_description: 用户自然语言描述
            context: 可选的额外上下文（如已有用例信息）

        Returns:
            结构化意图JSON
        """
        logger.info(f"开始意图识别，输入: {user_description[:100]}...")

        # 第一步：提取关键词标签
        tags = self._extract_tags(user_description)
        logger.info(f"提取标签: {tags}")

        # 第二步：识别场景模式
        scene_pattern = self._match_scene_pattern(user_description, tags)
        logger.info(f"匹配场景模式: {scene_pattern}")

        # 第三步：构建case_metadata
        metadata = self._build_metadata(user_description, tags)
        logger.info(f"构建元数据: case_name={metadata.get('case_name', 'N/A')}")

        # 第四步：构建logic_plan
        logic_plan = self._build_logic_plan(scene_pattern, tags, user_description)
        logger.info(
            f"构建逻辑计划: setup={len(logic_plan.get('setup', []))}步, "
            f"execution={len(logic_plan.get('execution', []))}步, "
            f"assertion={len(logic_plan.get('assertion', []))}步"
        )

        # 第五步：组装完整意图
        intent = {
            "case_metadata": metadata,
            "logic_plan": logic_plan,
            "identified_tags": tags,
            "planner_comments": self._generate_comments(scene_pattern, tags),
        }

        logger.info("意图识别完成")
        return intent

    def _extract_tags(self, description: str) -> list:
        """从描述中提取标签"""
        tags = []
        tag_patterns = {
            "deepseek_r1": ["deepseek r1", "deepseek-r1", "deepseekr1", "r1"],
            "deepseek_v3": ["deepseek v3", "deepseek-v3", "deepseekv3", "v3"],
            "qwen": ["qwen"],
            "llama": ["llama"],
            "vllm": ["vllm", "vllm-mindspore"],
            "mindie": ["mindie"],
            "perf": ["性能", "performance", "perf", "吞吐", "throughput", "tokens"],
            "acc": ["精度", "accuracy", "acc", "准确率"],
            "det": ["一致性", "deterministic", "det", "重复性", "一致性测试"],
            "bf16": ["bf16", "bfloat16"],
            "int8": ["int8", "w8a8"],
            "w4a8": ["w4a8", "4bit"],
            "gptq_w4a16": ["gptq", "w4a16"],
            "910b3": ["910b3", "910b"],
            "ceval": ["ceval"],
            "gsm8k": ["gsm8k"],
        }

        desc_lower = description.lower()
        for tag, patterns in tag_patterns.items():
            if any(p in desc_lower for p in patterns):
                tags.append(tag)

        # 提取卡数
        for np_val in ["8p", "16p", "32p", "64p"]:
            if np_val in description.lower():
                tags.append(np_val)

        # 提取模型规格
        import re

        size_match = re.search(r"(\d+b)", description.lower())
        if size_match:
            tags.append(size_match.group(1))

        return list(set(tags))

    def _match_scene_pattern(self, description: str, tags: list) -> str:
        """匹配场景模式"""
        has_perf = any(t in tags for t in ["perf"])
        has_acc = any(t in tags for t in ["acc"])
        has_det = any(t in tags for t in ["det"])
        has_mindie = "mindie" in tags

        if has_det:
            return "vllm_det"
        if has_perf and has_acc:
            return "vllm_perf_acc"
        if has_perf:
            return "vllm_perf"
        if has_acc:
            if has_mindie:
                return "mindie_acc"
            return "vllm_acc"

        # 默认：性能+精度
        return "vllm_perf_acc"

    def _build_metadata(self, description: str, tags: list) -> dict:
        """构建用例元数据"""
        # 确定网络基类
        base_class = "Deepseek"
        if "qwen" in tags:
            base_class = "Qwen"
        elif "llama" in tags:
            base_class = "Llama"

        # 确定网络模块
        network_map = {"Deepseek": "deepseek", "Qwen": "qwen", "Llama": "llama"}
        network = network_map.get(base_class, base_class.lower())

        # 构建case_name的各部分
        framework = "vllm" if "vllm" in tags else ("mindie" if "mindie" in tags else "vllm")

        # 提取量化方式
        quantize = "bf16"
        for q in ["w4a8", "int8", "w8a8", "gptq_w4a16"]:
            if q in tags:
                quantize = q
                break

        # 提取卡数
        np_val = "8p"
        for n in ["8p", "16p", "32p", "64p"]:
            if n in tags:
                np_val = n
                break

        # 提取模型规格
        size = "671b"
        for s in tags:
            if s.endswith("b") and s[:-1].isdigit():
                size = s
                break

        # 确定任务类型
        task_type = "infer"

        # 提取测试子类型
        sub_type = "perf" if "perf" in tags else ("acc" if "acc" in tags else ("det" if "det" in tags else "perf"))

        # 确定网络子型号
        sub_model = ""
        if "deepseek_r1" in tags:
            sub_model = "r1"
        elif "deepseek_v3" in tags:
            sub_model = "v3"

        return {
            "case_name": f"test_ms_{sub_model or network}{size}_{framework}_{task_type}_v1_{sub_type}_{quantize}_910b3_{np_val}_XXXX",
            "base_class": base_class,
            "imports": [f"from common.ms_aw.network.net.{network} import {base_class}"],
            "framework": framework,
            "network": sub_model or network,
            "model_size": size,
            "quantize": quantize,
            "np": np_val,
            "task_type": task_type,
            "sub_type": sub_type,
        }

    def _build_logic_plan(self, scene_pattern: str, tags: list, description: str) -> dict:
        """根据场景模式构建逻辑计划"""

        # 获取setup actions
        setup_actions = self._build_setup_actions(tags, description)

        # 获取execution actions
        execution_actions = self._build_execution_actions(scene_pattern, tags, description)

        # 获取assertion actions
        assertion_actions = self._build_assertion_actions(scene_pattern, tags)

        # 获取teardown actions
        teardown_actions = [{"action": "stop_vllm_server", "params": {}, "is_mandatory": True}]

        return {
            "setup": setup_actions,
            "execution": execution_actions,
            "assertion": assertion_actions,
            "teardown": teardown_actions,
        }

    def _build_setup_actions(self, tags: list, description: str) -> list:
        actions = []
        if "vllm" in tags or "vllm" not in tags:
            actions.append(
                {
                    "action": "set_vllm_server_prepare",
                    "params": {
                        "_note": "具体参数需根据模型规格填写，此处为占位",
                        "max_model_len": 16384,
                        "max_num_seqs": 192,
                        "gpu_memory_utilization": 0.9,
                        "tensor_parallel_size": 8,
                    },
                    "is_mandatory": True,
                }
            )
        return actions

    def _build_execution_actions(self, scene_pattern: str, tags: list, description: str) -> list:
        actions = []

        if "vllm" in scene_pattern:
            actions.append(
                {
                    "action": "start_vllm_server",
                    "params": {
                        "_note": "具体启动命令需根据模型和框架参数生成",
                        "model_path": "{model_path_placeholder}",
                        "serve_command": "vllm-mindspore serve {model_path} --trust-remote-code ...",
                        "trust_remote_code": True,
                    },
                    "is_mandatory": True,
                }
            )
            actions.append({"action": "get_vllm_log_ip_port", "params": {}, "is_mandatory": True})

        if scene_pattern == "vllm_det":
            actions.append(
                {
                    "action": "aisbench_test",
                    "params": {"test_type": "ceval", "run_count": 2, "log_suffix": ["_run1", "_run2"]},
                    "is_mandatory": True,
                }
            )
        elif scene_pattern == "vllm_perf":
            actions.append(
                {
                    "action": "vllm_benchmark_perf_test",
                    "params": {"_note": "需指定batch_size列表"},
                    "is_mandatory": True,
                }
            )
        elif scene_pattern == "vllm_acc":
            actions.append(
                {"action": "aisbench_test", "params": {"_note": "需指定test_type和dataset"}, "is_mandatory": True}
            )
        elif scene_pattern == "vllm_perf_acc":
            actions.append(
                {"action": "vllm_benchmark_perf_test", "params": {"_note": "性能测试"}, "is_mandatory": True}
            )
            actions.append({"action": "aisbench_test", "params": {"_note": "精度测试"}, "is_mandatory": True})
        elif scene_pattern == "mindie_acc":
            actions.append({"action": "mindie_server_warm_up", "params": {}, "is_mandatory": True})
            actions.append({"action": "run_infer_mindie_cluster_shell", "params": {}, "is_mandatory": True})

        return actions

    def _build_assertion_actions(self, scene_pattern: str, tags: list) -> list:
        actions = []
        if scene_pattern == "vllm_det":
            actions.append(
                {
                    "action": "check_ceval_consistency",
                    "params": {"threshold": 1, "metric": "ceval_score", "run_count": 2},
                    "is_mandatory": True,
                }
            )
        elif scene_pattern in ("vllm_acc", "vllm_perf_acc"):
            actions.append(
                {
                    "action": "check_benchmark_acc",
                    "params": {"_note": "需指定acc_stand和acc_error"},
                    "is_mandatory": True,
                }
            )
        if scene_pattern in ("vllm_perf", "vllm_perf_acc"):
            actions.append(
                {
                    "action": "vllm_benchmark_perf_check",
                    "params": {"_note": "需指定perf_stand和perf_error"},
                    "is_mandatory": True,
                }
            )
        return actions

    def _generate_comments(self, scene_pattern: str, tags: list) -> str:
        pattern_desc = {
            "vllm_perf": "VLLM性能测试",
            "vllm_acc": "VLLM精度测试",
            "vllm_det": "VLLM一致性测试",
            "vllm_perf_acc": "VLLM性能+精度测试",
            "mindie_acc": "MindIE精度测试",
        }
        return f"{pattern_desc.get(scene_pattern, '未知模式')}，标签: {', '.join(tags)}"
