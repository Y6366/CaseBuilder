#!/usr/bin/env python3
"""
代码生成Agent - Code Generation Agent
负责将意图JSON + 检索知识合成为完整的测试用例Python代码
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger("CaseBuilder.CodeGenAgent")


class CodeGenAgent:
    """
    代码生成Agent

    输入:
    - intent: 意图识别结果
    - knowledge: 检索到的知识上下文

    输出: 完整的测试用例Python代码（字符串）

    职责:
    1. 根据意图填充代码模板
    2. 生成正确的import语句
    3. 生成setup/test_run/teardown方法
    4. 保证代码风格与现有工程一致
    """

    def __init__(self, templates_dir: str = "knowledge/templates", rules_path: str = "knowledge/rules/coding_rules.md"):
        self.templates_dir = Path(templates_dir)
        self.coding_rules = self._load_md(rules_path)
        logger.info("CodeGenAgent 初始化完成")

    def _load_md(self, path: str) -> str:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    def generate(self, intent: dict, knowledge: dict) -> dict:
        """
        生成测试用例代码

        Args:
            intent: 意图识别结果
            knowledge: 检索到的知识

        Returns:
            {
                "code": "完整Python代码字符串",
                "file_name": "建议的文件名",
                "class_name": "类名",
                "warnings": ["警告信息列表"],
                "placeholders": ["需要用户填写的占位符列表"]
            }
        """
        logger.info("开始代码生成...")

        metadata = intent["case_metadata"]
        logic_plan = intent["logic_plan"]
        tags = intent.get("identified_tags", [])

        # 1. 生成文件名和类名
        class_name = self._generate_class_name(metadata, tags)
        file_name = self._generate_file_name(class_name)
        logger.info(f"生成类名: {class_name}")
        logger.info(f"生成文件名: {file_name}")

        # 2. 生成imports
        imports = self._generate_imports(metadata, knowledge)
        logger.info(f"生成imports: {len(imports.split(chr(10)))} 条")

        # 3. 生成setup方法体
        setup_body = self._generate_setup_body(metadata, logic_plan, knowledge)

        # 4. 生成test_run方法体
        test_run_body = self._generate_test_run_body(metadata, logic_plan, knowledge, tags)

        # 5. 组装完整代码
        code = self._assemble_code(
            class_name=class_name,
            base_class=metadata["base_class"],
            imports=imports,
            class_docstring=self._generate_docstring(metadata, tags),
            setup_body=setup_body,
            test_run_body=test_run_body,
            timeout=self._calculate_timeout(tags),
            np_val=metadata.get("np", "8p"),
            metadata=metadata,
        )

        # 6. 检查占位符
        placeholders = re.findall(r"\{(\w+)_placeholder\}", code)

        # 7. 生成警告
        warnings = []
        if placeholders:
            warnings.append(f"代码中包含 {len(placeholders)} 个需要手动填写的占位符: {', '.join(placeholders)}")

        result = {
            "code": code,
            "file_name": file_name,
            "class_name": class_name,
            "warnings": warnings,
            "placeholders": placeholders,
        }

        logger.info(f"代码生成完成: {len(code)} 字符, {code.count(chr(10))} 行")
        return result

    def _generate_class_name(self, metadata: dict, tags: list) -> str:
        """生成类名"""
        case_name = metadata.get("case_name", "")
        if case_name and "XXXX" not in case_name:
            return "Test_" + case_name.replace("test_", "", 1)

        parts = ["Test", "ms"]
        network = metadata.get("network", "deepseekr1")
        parts.append(network)
        parts.append(metadata.get("model_size", "671b"))
        parts.append(metadata.get("framework", "vllm"))
        parts.append(metadata.get("task_type", "infer"))
        parts.append("v1")
        parts.append(metadata.get("sub_type", "perf"))
        parts.append(metadata.get("quantize", "bf16"))
        parts.append("910b3")
        parts.append(metadata.get("np", "8p"))
        parts.append("0001")
        return "_".join(parts)

    def _generate_file_name(self, class_name: str) -> str:
        """生成文件名"""
        return class_name.lower() + ".py"

    def _generate_imports(self, metadata: dict, knowledge: dict) -> str:
        """生成import语句"""
        imports = ["import pytest"]

        base_imports = metadata.get("imports", [])
        imports.extend(base_imports)

        config_imports = knowledge.get("import_references", [])
        for ref in config_imports:
            if ref.startswith("from ") and ref not in imports:
                clean_ref = ref.replace("参考: ", "").strip()
                if clean_ref.startswith("from "):
                    imports.append(clean_ref.split("->")[0].strip())

        return "\n".join(imports)

    def _generate_docstring(self, metadata: dict, tags: list) -> str:
        """生成类docstring"""
        network_map = {"r1": "deepseek_r1", "v3": "deepseek_v3"}
        network = network_map.get(metadata.get("network", ""), metadata.get("network", ""))
        size = metadata.get("model_size", "671b")
        framework = metadata.get("framework", "vllm")
        quantize = metadata.get("quantize", "bf16")
        np_val = metadata.get("np", "8p")
        sub_type_map = {"perf": "性能验证", "acc": "精度验证", "det": "一致性验证"}
        sub_type_desc = sub_type_map.get(metadata.get("sub_type", ""), "验证")

        return (
            f"{network}网络，{size}，910b3环境{np_val}，{quantize}权重，"
            f"{framework}_mindspore服务化推理，{sub_type_desc}"
        )

    def _generate_setup_body(self, metadata: dict, logic_plan: dict, knowledge: dict) -> str:
        """生成setup方法体"""
        lines = []

        for action in logic_plan.get("setup", []):
            action_name = action["action"]
            params = action.get("params", {})

            if action_name == "set_vllm_server_prepare":
                param_lines = []
                for k, v in params.items():
                    if k.startswith("_"):
                        continue
                    param_lines.append(f"            {k}={v}")
                params_str = ",\n".join(param_lines)
                lines.append("# 准备VLLM服务环境")
                lines.append(f"self.set_vllm_server_prepare(\n{params_str}\n        )")

            elif action_name == "set_env_variables":
                lines.append("# 设置环境变量")
                env_lines = []
                for k, v in params.items():
                    if k.startswith("_"):
                        continue
                    env_lines.append(f'            "{k}": "{v}"')
                lines.append("self.set_env_variables(\n" + ",\n".join(env_lines) + "\n        )")

            elif action_name == "copy_model":
                lines.append("# 拷贝模型代码仓")
                lines.append('self.ms_log.step("拷贝模型代码仓")')
                lines.append("if not self.copy_model(self.model_path, GOLDEN_STICK_ROOT, rm_model=False):")
                lines.append('    self.ms_log.error("Copy model failed")')
                lines.append("    return False")

        return "\n        ".join(lines) if lines else "pass"

    def _generate_test_run_body(self, metadata: dict, logic_plan: dict, knowledge: dict, tags: list) -> str:
        """生成test_run方法体"""
        lines = []
        step_num = 1

        for action in logic_plan.get("execution", []):
            action_name = action["action"]
            params = action.get("params", {})

            if action_name == "start_vllm_server":
                serve_cmd = params.get("serve_command", "vllm-mindspore serve {model_path} --trust-remote-code ...")
                lines.append(f'self.ms_log.step("{step_num}. 拉起vllm服务")')
                lines.append(f'start_server = ("{serve_cmd}")')
                lines.append("self.vllm_server_start(start_server, cycle_time=200, wait_time=60)")
                lines.append("")
                step_num += 1

            elif action_name == "get_vllm_log_ip_port":
                lines.append('vllm_ip, vllm_port = self.get_vllm_log_ip_port(f"{self.model_path}/vllm_server.log")')
                lines.append("")

            elif action_name == "aisbench_test":
                test_type = params.get("test_type", "ceval")
                run_count = params.get("run_count")

                if run_count and run_count > 1:
                    for i in range(1, run_count + 1):
                        lines.append(f'self.ms_log.step("{step_num}. 执行第{i}次{test_type}测试")')
                        lines.append(f"acc_run{i} = self.aisbench_test(")
                        lines.append(f'    self.ais_bench_path, "vllm_api_general_chat", "{test_type}_chat_prompt",')
                        lines.append("    path={model_path_placeholder}, model={model_path_placeholder},")
                        lines.append("    host_ip=vllm_ip, host_port=vllm_port,")
                        lines.append("    max_out_len={max_out_len_placeholder}, batch_size={batch_size_placeholder}")
                        lines.append(")")
                    step_num += 1
                else:
                    dataset = params.get("dataset", f"{test_type}_chat_prompt")
                    lines.append(f'self.ms_log.step("{step_num}. 执行精度测试")')
                    lines.append("acc = self.aisbench_test(")
                    lines.append(f'    self.ais_bench_path, "vllm_api_general_chat", "{dataset}",')
                    lines.append("    path={model_path_placeholder}, model={model_path_placeholder},")
                    lines.append("    host_ip=vllm_ip, host_port=vllm_port,")
                    lines.append("    max_out_len={max_out_len_placeholder}, batch_size={batch_size_placeholder}")
                    lines.append(")")
                    step_num += 1

            elif action_name == "vllm_benchmark_perf_test":
                lines.append(f'self.ms_log.step("{step_num}. 执行性能测试")')
                lines.append("perf_std = {1: {perf_std_1_placeholder}, {bs_placeholder}: {perf_std_2_placeholder}}")
                lines.append("for bs, std in perf_std.items():")
                lines.append('    self.ms_log.step(f"  batch_size={bs}")')
                lines.append("    self.vllm_benchmark_perf_test(")
                lines.append("        ckpt_path={ckpt_path_placeholder}, parallel_num=bs,")
                lines.append("        input_tokens=256, output_tokens=256,")
                lines.append("        host_ip=vllm_ip, port=vllm_port")
                lines.append("    )")
                lines.append("    if not self.vllm_benchmark_perf_check(")
                lines.append("        perf_stand=std, perf_error=0.95")
                lines.append("    ):")
                lines.append('        self.ms_log.error("check_benchmark_perf fail")')
                lines.append("        self.perf_acc_flag = False")
                step_num += 1

            elif action_name == "mindie_server_warm_up":
                lines.append(f'self.ms_log.step("{step_num}. MindIE服务预热")')
                lines.append("self.mindie_server_warm_up()")
                step_num += 1

            elif action_name == "run_infer_mindie_cluster_shell":
                lines.append(f'self.ms_log.step("{step_num}. 运行MindIE集群推理")')
                lines.append("self.run_infer_mindie_cluster_shell()")
                step_num += 1

        # 添加断言步骤
        for action in logic_plan.get("assertion", []):
            action_name = action["action"]
            params = action.get("params", {})

            if action_name == "check_benchmark_acc":
                lines.append(f'self.ms_log.step("{step_num}. 校验精度是否达标")')
                lines.append("if not acc or not self.check_benchmark_acc(")
                lines.append("    accuracy=acc,")
                lines.append("    acc_stand={acc_stand_placeholder},")
                lines.append("    acc_error=0.99")
                lines.append("):")
                lines.append("    self.perf_acc_flag = False")
                step_num += 1

            elif action_name == "check_ceval_consistency":
                threshold = params.get("threshold", 1)
                lines.append(f'self.ms_log.step("{step_num}. 校验CEVAL一致性")')
                lines.append("if not self.check_ceval_consistency(")
                lines.append(f'    threshold={threshold}, metric="ceval_score", run_count=2')
                lines.append("):")
                lines.append("    self.perf_acc_flag = False")
                step_num += 1

        # 日志检查（通用步骤）
        if "vllm" in tags:
            lines.append(f'self.ms_log.step("{step_num}. 验证日志文件是否有error日志")')
            lines.append("if not self.check_err_info_in_log(")
            lines.append('    [f"{self.model_path}/vllm_server.log"],')
            lines.append('    "ERROR|CRITICAL|Traceback|RuntimeError|WARNING",')
            lines.append(
                '    ignore_cw="Failed to connect to the meta server|'
                "Failed to register and try to reconnect to the meta server|"
                'Failed to connect to the tcp server",'
            )
            lines.append("    log_card_type=8")
            lines.append("):")
            lines.append("    self.perf_acc_flag = False")

        return "\n        ".join(lines)

    def _calculate_timeout(self, tags: list) -> int:
        """根据场景计算超时时间"""
        base_timeout = 7200
        if "32p" in tags:
            base_timeout = 14400
        if "det" in tags:
            base_timeout = int(base_timeout * 1.5)
        return base_timeout

    def _assemble_code(
        self, class_name, base_class, imports, class_docstring, setup_body, test_run_body, timeout, np_val, metadata
    ) -> str:
        """组装完整代码"""
        code = f'''# -*- coding: utf-8 -*-
"""
{class_docstring}
"""
{imports}


module = "{class_name}"


class {class_name}({base_class}):
    """
    {class_docstring}
    """

    def setup(self, case_name=None):
        case_name = "{class_name}"
        if not super({class_name}, self).setup(case_name):
            return False

        {setup_body}

        self.init_success_flg = True
        self.ms_log.info("The case setup success")
        return self.init_success_flg

    @pytest.mark.level1
    @pytest.mark.timeout({timeout})
    @pytest.mark.env_Network_Ascend_Arm_{np_val}
    @pytest.mark.env_Network_Ascend_X86_{np_val}
    def test_run(self):
        """
        test_run
        """
        assert self.init_success_flg
        self.ms_log.info("The case test is running")
        self.perf_acc_flag = True

        {test_run_body}

        if not self.perf_acc_flag:
            self.ms_log.error("Something wrong with infer, pls check error log.")
            assert False

        self.ms_log.info("The case test is success")

    def teardown(self):
        self.ms_log.info("The case teardown is running")
        super({class_name}, self).teardown()
        return True
'''
        return code
