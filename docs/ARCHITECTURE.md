# CaseBuilder 架构文档

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                     用户输入层                                │
│              (自然语言测试场景描述)                             │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  Orchestrator 编排器                          │
│       (流程控制、检查点、日志、中间产物管理)                    │
└──────┬──────────┬──────────┬──────────┬─────────────────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Intent   │ │ Retrieval│ │ CodeGen  │ │ Review   │
│ Agent    │ │ Agent    │ │ Agent    │ │ Agent    │
│          │ │          │ │          │ │          │
│ 意图识别  │ │ 知识检索  │ │ 代码生成  │ │ 质量校验  │
│ 标签提取  │ │ 方法匹配  │ │ 模板填充  │ │ AST检查   │
│ 模式匹配  │ │ 调用链查询│ │ 代码组装  │ │ 规范检查  │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
┌──────────────────────────────────────────────────────────────┐
│                    知识层                                     │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐               │
│  │ 方法词典    │ │ 场景模式库  │ │ 代码模板库  │               │
│  │ glossary   │ │ patterns   │ │ templates  │               │
│  └────────────┘ └────────────┘ └────────────┘               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐               │
│  │ V1骨架/签名│ │ V2依赖/链路│ │ V3工具规范  │               │
│  └────────────┘ └────────────┘ └────────────┘               │
└──────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  工具层                                       │
│   build_context.py — 多层上下文构建工具                        │
│        (RecursiveRetriever AST解析器)                         │
└──────────────────────────────────────────────────────────────┘
```

## Agent职责

### IntentAgent (意图识别)
- **输入:** 用户自然语言描述
- **输出:** 结构化意图JSON
- **核心逻辑:** 关键词提取 → 场景模式匹配 → 元数据构建 → 逻辑计划生成
- **可替换:** 规则引擎 → LLM API

### RetrievalAgent (知识检索)
- **输入:** 意图JSON
- **输出:** 相关上下文（方法定义、相似用例、调用链、模板）
- **核心逻辑:** 基类信息查询 → 方法详情检索 → 相似用例匹配 → 模板选择

### CodeGenAgent (代码生成)
- **输入:** 意图JSON + 知识上下文
- **输出:** 完整Python测试用例代码
- **核心逻辑:** 模板选择 → 参数填充 → 代码组装 → 占位符标记

### ReviewAgent (质量校验)
- **输入:** 生成的代码 + 意图JSON
- **输出:** 校验报告 (pass/fail + 评分 + 问题列表)
- **核心逻辑:** AST语法检查 → 结构检查 → 方法调用校验 → 命名检查 → 意图对齐

## 数据流

```
用户描述
  │
  ├─→ IntentAgent.recognize()
  │     ├─ _extract_tags()        → ["deepseek_r1", "vllm", "det", "bf16", "32p"]
  │     ├─ _match_scene_pattern() → "vllm_det"
  │     ├─ _build_metadata()      → {case_name, base_class, imports, ...}
  │     └─ _build_logic_plan()    → {setup, execution, assertion, teardown}
  │
  ├─→ RetrievalAgent.retrieve()
  │     ├─ _get_base_class_info()     → 基类方法列表
  │     ├─ _get_method_details()      → 方法签名和参数
  │     ├─ _find_similar_cases()      → 相似用例参考
  │     ├─ _get_call_chain_examples() → 调用链示例
  │     └─ _get_template()            → 代码模板
  │
  ├─→ CodeGenAgent.generate()
  │     ├─ _generate_class_name()     → Test_ms_deepseekr1_671b_...
  │     ├─ _generate_imports()        → import pytest / from ... import ...
  │     ├─ _generate_setup_body()     → setup方法体
  │     ├─ _generate_test_run_body()  → test_run方法体
  │     └─ _assemble_code()           → 完整代码
  │
  └─→ ReviewAgent.review()
        ├─ _check_syntax()            → AST解析
        ├─ _check_structure()         → setup/test_run/teardown
        ├─ _check_method_calls()      → 方法合法性
        ├─ _check_imports()           → import完整性
        ├─ _check_naming()            → 命名规范
        ├─ _check_decorators()        → 装饰器
        └─ _check_logging()           → 日志规范
```

## 扩展点

1. **LLM接入:** 在IntentAgent和CodeGenAgent中替换规则引擎为LLM API
2. **新网络支持:** 在tag_patterns和base_class映射中添加新网络
3. **新场景模式:** 在scene_patterns.md中添加新模式
4. **新方法:** 在method_glossary.json中添加方法定义
5. **新模板:** 在templates/中添加模板文件

## 文件结构

```
CaseBuilder/
├── README.md                        # 项目总览
├── config/
│   └── settings.yaml                # 全局配置
├── agents/
│   ├── __init__.py
│   ├── intent_agent.py              # 意图识别Agent
│   ├── retrieval_agent.py           # 知识检索Agent
│   ├── codegen_agent.py             # 代码生成Agent
│   └── review_agent.py              # 质量校验Agent
├── workflow/
│   ├── __init__.py
│   └── orchestrator.py              # 工作流编排器
├── tools/
│   ├── __init__.py
│   └── build_context.py             # 多层上下文构建工具
├── knowledge/
│   ├── method_glossary.json         # 公共方法词典
│   ├── templates/
│   │   ├── vllm_perf_acc_template.py
│   │   └── vllm_det_template.py
│   └── rules/
│       ├── coding_rules.md          # 编码规范
│       └── scene_patterns.md        # 场景模式库
├── demo/
│   └── run_demo.py                  # 快速Demo
├── docs/
│   ├── OPERATION_MANUAL.md          # 操作手册
│   ├── DEBUG_GUIDE.md              # 调试指南
│   └── ARCHITECTURE.md             # 架构文档
├── context_output/                  # 上下文输出（运行后生成）
├── output/                          # 用例输出（运行后生成）
└── logs/                            # 日志（运行后生成）
```
