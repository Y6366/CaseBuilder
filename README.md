# TestForge — 基于LLM的测试用例自动生成引擎

> 从 LLMCFG-TGen 论文复现工程演进为通用的测试用例代码生成系统

## 设计理念

**领域无关骨架 + 领域插件化上下文**

- 核心Pipeline不包含任何业务逻辑（不知道DeepSeek、不知道推理、不知道训练）
- 每个测试领域（推理精度/推理性能/训练/其他网络）通过"上下文包"注入领域知识
- 新增领域只需准备上下文包，不改引擎代码

## 项目结构

```
TestForge/
├── README.md
├── USAGE.md
├── ADAPTATION_ANALYSIS.md
├── ADAPTATION_PLAN.md
│
├── src/                          # 核心引擎（领域无关）
│   ├── __init__.py
│   ├── llm_client.py             # LLM调用客户端
│   ├── pipeline.py               # 端到端流水线（核心编排）
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── base.py               # 生成器基类
│   │   └── code_generator.py     # 代码生成器（LLM + 模板 + RAG）
│   ├── matchers/
│   │   ├── __init__.py
│   │   ├── base.py               # 匹配器基类
│   │   └── chain_matcher.py      # 调用链匹配器
│   └── renderers/
│       ├── __init__.py
│       ├── base.py               # 渲染器基类
│       └── python_renderer.py    # Python代码渲染器
│
├── config/
│   ├── domains/                  # 领域配置（每个业务一个）
│   │   └── deepseek_infer.yaml   # DeepSeek推理测试领域配置
│   └── templates/                # 代码模板
│       └── python_test_template.py
│
├── context_store/                # 领域上下文包（即论文中的"三大视图"）
│   ├── deepseek_infer/           # DeepSeek推理场景
│   │   ├── VIEW1_module_signatures.md
│   │   ├── VIEW2_dependency_graph.md
│   │   ├── VIEW3_tool_specs.md
│   │   ├── sample_cases/         # few-shot用例样例
│   │   │   ├── sample_001_w4a8_acc_perf.py
│   │   │   └── sample_002_det_ceval.py
│   │   └── call_chain_templates.json  # 调用链模板库
│   ├── deepseek_train/           # DeepSeek训练场景（未来扩展）
│   ├── glm_infer/                # GLM推理场景（未来扩展）
│   └── llama_infer/              # Llama推理场景（未来扩展）
│
├── data/
│   ├── examples/                 # 示例需求文档
│   │   ├── req_deepseek_ceval.json
│   │   └── ...
│   └── output/                   # 生成的测试用例输出
│
├── tests/
│   └── ...
│
└── web/
    └── app.py                    # Web界面
```

## 核心流程

```
需求文档 + 领域标识(domain)
    │
    ├─→ 加载领域配置(config/domains/{domain}.yaml)
    ├─→ 加载上下文包(context_store/{domain}/)
    │
    ▼
┌──────────────────────────────────────┐
│ Step 1: 需求解析 (Requirement Parse)  │
│ 需求文档 → 结构化需求JSON             │
│ Prompt从领域配置中加载                 │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ Step 2: 调用链匹配 (Chain Match)      │
│ 结构化需求 → 匹配最相似的历史调用链    │
│ 从context_store的调用链模板库中匹配    │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ Step 3: 代码生成 (Code Generation)    │
│ 结构化需求 + 调用链模板 + few-shot     │
│ → LLM生成完整测试类代码               │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ Step 4: 代码校验 (Code Validation)    │
│ AST解析 + 规则检查 + 编译验证          │
└──────────────────────────────────────┘
    │
    ▼
输出: 可执行的测试文件 + net_config补充项
```

## 扩展新领域

以"添加GLM推理测试"为例：

1. 创建 `context_store/glm_infer/` 目录
2. 放入GLM的三大视图文件（模块签名、依赖图谱、工具规范）
3. 放入2-3个GLM测试用例样例到 `sample_cases/`
4. 提取调用链模板到 `call_chain_templates.json`
5. 创建 `config/domains/glm_infer.yaml`
6. 完成 — 无需修改引擎代码
