"""
TestForge 核心 Pipeline v2

领域无关的端到端流水线:
  Step 1: 需求解析 — 需求文档 → 结构化需求JSON
  Step 2: 调用链匹配 — 需求 → 最相似的历史调用链模板
  Step 3: 代码生成 — 需求 + 调用链 + few-shot → Python测试类代码
  Step 4: 代码校验 — AST解析 + 编译检查 + 规则校验
"""

import json
import logging
import os
import yaml
from datetime import datetime
from pathlib import Path

from .llm_client import LLMClient

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


class DomainContext:
    """领域上下文 — 加载某个测试领域的全部知识。"""

    def __init__(self, domain: str):
        self.domain = domain
        self.config = self._load_domain_config(domain)
        self.context_dir = PROJECT_ROOT / "context_store" / domain
        self.views = {}
        self.sample_cases = []
        self._load_context()

    def _load_domain_config(self, domain: str) -> dict:
        config_path = PROJECT_ROOT / "config" / "domains" / f"{domain}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Domain config not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _load_context(self):
        """加载三大视图和样本用例。"""
        ctx_cfg = self.config.get("context", {})

        # 加载三大视图
        for view_key in ["module_signatures", "dependency_graph", "tool_specs"]:
            path = ctx_cfg.get(view_key)
            if path:
                full_path = PROJECT_ROOT / path
                if full_path.exists():
                    self.views[view_key] = full_path.read_text(encoding="utf-8")
                    logger.info(f"Loaded {view_key}: {len(self.views[view_key])} chars")

        # 加载样本用例
        samples_dir = ctx_cfg.get("sample_cases_dir")
        if samples_dir:
            full_dir = PROJECT_ROOT / samples_dir
            if full_dir.exists():
                for f in sorted(full_dir.glob("*.py")):
                    self.sample_cases.append({
                        "filename": f.name,
                        "code": f.read_text(encoding="utf-8"),
                    })
                    logger.info(f"Loaded sample case: {f.name}")

    def get_call_chain_templates(self) -> dict:
        """获取调用链模板库。"""
        # 优先从config中的call_chain_templates读取
        return self.config.get("call_chain_templates", {})

    def get_imports(self, network: str = None, framework: str = None) -> list[str]:
        """根据网络和框架生成import列表。"""
        imports = list(self.config.get("class_hierarchy", {}).get("common_imports", []))

        # 网络特定import
        if network:
            net_map = self.config.get("class_hierarchy", {}).get("network_to_base", {})
            net_info = net_map.get(network, {})
            if "import" in net_info:
                imports.append(net_info["import"])

        # 框架特定import
        if framework:
            fw_imports = self.config.get("class_hierarchy", {}).get("framework_imports", {})
            imports.extend(fw_imports.get(framework, []))

        return imports

    def get_base_class(self, network: str) -> str:
        """根据网络获取基类名。"""
        net_map = self.config.get("class_hierarchy", {}).get("network_to_base", {})
        return net_map.get(network, {}).get("base_class", "object")

    def get_pytest_markers(self, cards: str) -> list[str]:
        """根据卡数获取pytest装饰器。"""
        markers_cfg = self.config.get("pytest_markers", {})
        cards_map = markers_cfg.get("cards_to_marker", {})
        return cards_map.get(cards, cards_map.get("8p", []))

    def get_method_specs(self) -> dict:
        """获取基类方法说明。"""
        return self.config.get("method_specs", {})

    def get_name_patterns(self) -> dict:
        """获取用例名解析规则。"""
        return self.config.get("requirement_parsing", {}).get("name_patterns", {})


class TestForgePipeline:
    """
    TestForge 端到端流水线。

    用法:
        pipeline = TestForgePipeline(domain="deepseek_infer")
        result = pipeline.run(requirement_text)
    """

    def __init__(
        self,
        domain: str,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
    ):
        self.domain_ctx = DomainContext(domain)
        self.llm = LLMClient(model=model, api_key=api_key, base_url=base_url)
        logger.info(f"TestForge initialized: domain={domain}")

    def run(self, requirement: str) -> dict:
        """
        执行完整的测试用例生成流水线。

        Args:
            requirement: 需求文档文本（半结构化）

        Returns:
            {
                "requirement_parsed": {...},    # 结构化需求
                "matched_template": {...},      # 匹配的调用链模板
                "generated_code": "...",        # 生成的Python代码
                "validation": {...},            # 校验结果
                "metadata": {...}               # 元数据
            }
        """
        start_time = datetime.now()
        result = {"metadata": {"domain": self.domain_ctx.domain, "start_time": start_time.isoformat()}}

        # Step 1: 需求解析
        logger.info("=" * 60)
        logger.info("Step 1: Requirement Parsing")
        logger.info("=" * 60)
        parsed_req = self._parse_requirement(requirement)
        result["requirement_parsed"] = parsed_req

        # Step 2: 调用链匹配
        logger.info("=" * 60)
        logger.info("Step 2: Call Chain Matching")
        logger.info("=" * 60)
        matched = self._match_call_chain(parsed_req)
        result["matched_template"] = matched

        # Step 3: 代码生成
        logger.info("=" * 60)
        logger.info("Step 3: Code Generation")
        logger.info("=" * 60)
        code = self._generate_code(parsed_req, matched)
        result["generated_code"] = code

        # Step 4: 代码校验
        logger.info("=" * 60)
        logger.info("Step 4: Code Validation")
        logger.info("=" * 60)
        validation = self._validate_code(code)
        result["validation"] = validation

        elapsed = (datetime.now() - start_time).total_seconds()
        result["metadata"]["elapsed_seconds"] = elapsed
        result["metadata"]["end_time"] = datetime.now().isoformat()
        logger.info(f"Pipeline complete in {elapsed:.1f}s")

        return result

    def _parse_requirement(self, requirement: str) -> dict:
        """Step 1: 用LLM解析需求文档为结构化JSON。"""
        domain_cfg = self.domain_ctx.config
        name_patterns = domain_cfg.get("requirement_parsing", {}).get("name_patterns", {})

        prompt = f"""你是一个需求文档解析专家。请将以下测试需求文档解析为结构化JSON。

### 需求文档:
{requirement}

### 用例名解析规则:
从用例名中自动提取以下维度: {json.dumps(name_patterns, ensure_ascii=False, indent=2)}

### 输出格式:
```json
{{
  "case_name": "完整用例名",
  "network": "网络名称(deepseek/glm/llama等)",
  "network_version": "版本(r1/v3等)",
  "model_size": "模型规格(671b等)",
  "framework": "推理框架(vllm/mindie等)",
  "scenario": "场景(infer/train)",
  "test_subtype": "测试子类型(acc/perf/func/det_ceval等)",
  "version": "用例版本(v0/v1)",
  "parallel_strategy": "并行策略(tp32等)",
  "weight_type": "权重类型(bf16/int8/w4a8等)",
  "hardware": "硬件(910b3)",
  "cards": "卡数(8p/16p/32p)",
  "cards_num": 8,
  "sequence": "序号",
  "weight_path_var": "变量名(如ds_r1_model_path)",
  "weight_path_value": "路径值",
  "code_repo": "代码仓(可为null)",
  "env_vars": "环境变量(可为null)",
  "serve_command": "服务拉起命令(可为null)",
  "test_type": "测试类型(accuracy/performance/function)",
  "test_tool": "测试工具方法名",
  "test_dataset": "数据集名",
  "test_params": {{}},
  "test_requirements": ["具体执行要求列表"],
  "validation": {{
    "method": "校验方法描述",
    "params": {{}}
  }}
}}
```

只输出JSON，不要其他内容。"""

        system_prompt = "你是需求文档解析专家，擅长从半结构化的测试需求文档中提取结构化信息。"

        parsed = self.llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
        )
        logger.info(f"Parsed requirement: {parsed.get('case_name', 'unknown')}")
        return parsed

    def _match_call_chain(self, parsed_req: dict) -> dict:
        """Step 2: 匹配最相似的调用链模板。"""
        templates = self.domain_ctx.get_call_chain_templates()
        framework = parsed_req.get("framework", "")
        scenario = parsed_req.get("scenario", "")
        test_type = parsed_req.get("test_type", "")
        test_subtype = parsed_req.get("test_subtype", "")

        best_match = None
        best_score = -1

        for tmpl_name, tmpl_data in templates.items():
            rule = tmpl_data.get("match_rule", "")
            score = 0

            # 简单关键词匹配评分
            if framework and framework in rule:
                score += 3
            if scenario and scenario in rule:
                score += 3
            if test_type and test_type in rule:
                score += 2
            if test_subtype and test_subtype in rule:
                score += 2

            # 精确子串匹配加分
            if test_subtype and test_subtype in tmpl_name:
                score += 3
            if framework and framework in tmpl_name:
                score += 1

            if score > best_score:
                best_score = score
                best_match = {"name": tmpl_name, "score": score, **tmpl_data}

        if best_match:
            logger.info(f"Matched template: {best_match['name']} (score={best_match['score']})")
        else:
            logger.warning("No matching call chain template found")
            best_match = {"name": "fallback", "score": 0, "setup": [], "test_run": [], "teardown": []}

        return best_match

    def _generate_code(self, parsed_req: dict, matched_template: dict) -> str:
        """Step 3: 用LLM生成完整测试类代码。"""
        network = parsed_req.get("network", "deepseek")
        framework = parsed_req.get("framework", "vllm")
        cards = parsed_req.get("cards", "8p")

        # 收集上下文
        imports = self.domain_ctx.get_imports(network, framework)
        base_class = self.domain_ctx.get_base_class(network)
        pytest_markers = self.domain_ctx.get_pytest_markers(cards)
        method_specs = self.domain_ctx.get_method_specs()
        sample_cases = self.domain_ctx.sample_cases

        # 构建few-shot
        few_shot_text = ""
        for i, sample in enumerate(sample_cases):
            few_shot_text += f"\n### 参考用例 {i+1}: {sample['filename']}\n```python\n{sample['code']}\n```\n"

        # 构建调用链模板
        chain_text = json.dumps(matched_template, ensure_ascii=False, indent=2)

        # 构建方法说明
        methods_text = json.dumps(method_specs, ensure_ascii=False, indent=2)

        # pytest装饰器
        markers_text = "\n".join(pytest_markers)
        timeout = self.domain_ctx.config.get("pytest_markers", {}).get("default_timeout", 14400)

        prompt = f"""你是一个专业的测试开发工程师。请根据以下需求文档和上下文信息，生成一个完整的、可直接执行的Python测试用例。

## 需求文档（结构化）
```json
{json.dumps(parsed_req, ensure_ascii=False, indent=2)}
```

## 代码模板参数
- import语句: {chr(10).join(imports)}
- 基类: {base_class}
- pytest装饰器:
{markers_text}
@pytest.mark.timeout({timeout})

## 匹配的调用链模板
```json
{chain_text}
```

## 基类方法说明
```json
{methods_text}
```

## 参考用例（few-shot）
{few_shot_text if few_shot_text else "无"}

## 生成规则
1. 类名必须与需求文档中的case_name一致
2. 继承正确的基类（{base_class}）
3. import必须包含: {', '.join(imports)}
4. setup/test_run/teardown严格遵循调用链模板
5. 但只生成需求文档中要求的测试步骤，不要额外添加模板中有但需求没要求的操作
6. pytest装饰器使用: {', '.join(pytest_markers)} + @pytest.mark.timeout({timeout})
7. check_err_info_in_log中log_card_type应为卡数（如32p → 32）
8. 代码风格与参考用例保持一致

只输出Python代码，不要解释，不要markdown代码块标记。"""

        system_prompt = "你是一个专业的Python测试开发工程师，擅长编写自动化测试框架代码。"

        code = self.llm.generate(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.0,
        )

        # 清理markdown代码块标记
        if code.strip().startswith("```"):
            code = code.strip()
            if code.startswith("```python"):
                code = code[len("```python"):]
            elif code.startswith("```"):
                code = code[len("```"):]
            if code.endswith("```"):
                code = code[:-len("```")]
            code = code.strip()

        logger.info(f"Generated code: {len(code)} chars")
        return code

    def _validate_code(self, code: str) -> dict:
        """Step 4: 代码校验。"""
        result = {"valid": True, "errors": [], "warnings": []}

        # 1. 编译检查
        try:
            compile(code, "<generated>", "exec")
        except SyntaxError as e:
            result["valid"] = False
            result["errors"].append(f"Syntax error: {e}")

        # 2. AST检查（包含必要元素）
        try:
            import ast
            tree = ast.parse(code)

            has_class = any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
            has_setup = False
            has_test_run = False
            has_teardown = False

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            if item.name == "setup":
                                has_setup = True
                            elif item.name == "test_run":
                                has_test_run = True
                            elif item.name == "teardown":
                                has_teardown = True

            if not has_class:
                result["valid"] = False
                result["errors"].append("No class definition found")
            if not has_setup:
                result["warnings"].append("No setup() method found")
            if not has_test_run:
                result["valid"] = False
                result["errors"].append("No test_run() method found")
            if not has_teardown:
                result["warnings"].append("No teardown() method found")

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"AST parse error: {e}")

        # 3. 关键字检查
        required_keywords = ["class ", "def setup", "def test_run", "def teardown", "super()"]
        for kw in required_keywords:
            if kw not in code:
                result["warnings"].append(f"Missing keyword: {kw}")

        logger.info(f"Validation: valid={result['valid']}, errors={len(result['errors'])}, warnings={len(result['warnings'])}")
        return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="TestForge: 测试用例自动生成引擎")
    parser.add_argument("--domain", type=str, default="deepseek_infer", help="领域标识")
    parser.add_argument("--requirement", type=str, help="需求文档文本")
    parser.add_argument("--file", type=str, help="需求文档文件路径")
    parser.add_argument("--output", type=str, default=None, help="输出文件路径")
    parser.add_argument("--model", type=str, default=None, help="LLM模型")
    parser.add_argument("--verbose", action="store_true", help="详细日志")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            requirement = f.read()
    elif args.requirement:
        requirement = args.requirement
    else:
        parser.error("请提供 --requirement 或 --file")

    pipeline = TestForgePipeline(domain=args.domain, model=args.model)
    result = pipeline.run(requirement)

    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        # 同时保存生成的代码
        code_path = args.output.replace(".json", ".py")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(result["generated_code"])
        print(f"结果已保存: {args.output}")
        print(f"代码已保存: {code_path}")
    else:
        print(result["generated_code"])


if __name__ == "__main__":
    main()
