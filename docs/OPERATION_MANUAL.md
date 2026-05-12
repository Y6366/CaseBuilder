# CaseBuilder 操作手册

## 1. 环境准备

### 前置条件
- Python 3.9+
- 无额外第三方依赖（所有核心功能使用标准库实现）

### 安装步骤
```bash
cd /path/to/CaseBuilder

# 验证Python版本
python3 --version

# 目录结构确认
ls -la
# 应看到: agents/ config/ docs/ knowledge/ tools/ workflow/ demo/
```

## 2. 第一步：构建工程上下文

如果已有测试工程源码，首先构建多维上下文：

```bash
# 指向测试工程根目录
python3 tools/build_context.py /path/to/test_project --output context_output

# 可指定过滤条件
python3 tools/build_context.py /path/to/test_project \
  --output context_output \
  --filter "cases/02network/02nlp/deepseek" "cases/02network/02nlp/qwen"
```

构建完成会在 `context_output/` 下生成：
- **V1_REPO_SKELETON.md** — 仓库骨架
- **V1_MODULE_SIGNATURES.md** — 模块签名
- **V2_DEPENDENCY_GRAPH.md** — 依赖图谱
- **V2_CALL_TRACE.md** — 调用链
- **V3_TOOL_SPECS.md** — 工具规范
- **SUMMARY.json** — 统计摘要

## 3. 第二步：运行Demo

```bash
# 交互式Demo
python3 demo/run_demo.py

# 命令行直接运行
python3 workflow/orchestrator.py "deepseek r1 671b，vllm推理，bf16权重，32p，CEVAL一致性测试"

# 跳过检查点和校验（自动化模式）
python3 workflow/orchestrator.py "场景描述" --no-checkpoint --no-review
```

## 4. 第三步：生产使用

### 4.1 配置文件

编辑 `config/settings.yaml`：

```yaml
# 关闭人工检查点（自动化模式）
workflow:
  enable_human_checkpoint: false
  enable_review: true
  max_review_retries: 2

# 指定测试工程路径
paths:
  test_project_root: "/path/to/your/test_project"
```

### 4.2 Python API集成

```python
from workflow.orchestrator import Orchestrator

orchestrator = Orchestrator("config/settings.yaml")
result = orchestrator.run("用户描述的测试场景")

if result["status"] == "success":
    print(f"生成成功: {result['output_file']}")
elif result["status"] == "review_failed":
    print(f"已生成但校验未通过: {result['output_file']}")
    for issue in result["review_report"]["issues"]:
        print(f"  [{issue['severity']}] {issue['message']}")
```

### 4.3 单独使用Agent

```python
from agents.intent_agent import IntentAgent

agent = IntentAgent()
intent = agent.recognize("deepseek r1 671b vllm bf16 32p 一致性测试")
print(intent["identified_tags"])       # 提取的标签
print(intent["case_metadata"])         # 用例元数据
print(intent["logic_plan"])            # 逻辑执行计划
```

## 5. 知识库维护

### 5.1 更新方法词典

编辑 `knowledge/method_glossary.json`，添加新方法：

```json
{
  "methods": {
    "new_method_name": {
      "category": "server",
      "tag": "vllm",
      "desc": "方法描述",
      "signature": "new_method_name(self, param1, param2) -> bool",
      "params": {
        "param1": "参数1描述"
      }
    }
  }
}
```

### 5.2 添加场景模式

编辑 `knowledge/rules/scene_patterns.md`，添加新模式。

### 5.3 添加代码模板

在 `knowledge/templates/` 下添加新的模板文件。

## 6. 自定义扩展

### 6.1 新增Agent

1. 在 `agents/` 下创建新文件
2. 实现标准接口
3. 在 `workflow/orchestrator.py` 中注册

### 6.2 替换LLM

当前使用规则引擎（关键词匹配），如需接入LLM：
1. 在Agent的 `recognize`/`generate` 方法中替换为LLM API调用
2. 推荐在 `config/settings.yaml` 中配置模型参数

## 7. 常见问题

### Q: 没有测试工程源码怎么办？
A: Demo模式不依赖真实工程源码。只需方法词典和场景规则即可运行。

### Q: 如何提高生成质量？
A:
1. 完善方法词典
2. 增加更多场景模式
3. 提供更多模板
4. 构建完整的工程上下文

### Q: 生成的代码有占位符怎么办？
A: 带有 `_placeholder` 后缀的值需要手动填写。可在代码生成后人工补充。

### Q: 如何接入大模型？
A: 将 IntentAgent 和 CodeGenAgent 中的规则引擎替换为 LLM API 调用即可。建议先使用规则引擎验证流程，再替换为LLM。
