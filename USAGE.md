# TestForge 使用说明

> 基于LLM的测试用例自动生成引擎 — 从需求文档到可执行测试代码

---

## 目录

1. [项目概述](#1-项目概述)
2. [环境准备](#2-环境准备)
3. [快速开始](#3-快速开始)
4. [核心架构](#4-核心架构)
5. [命令行使用](#5-命令行使用)
6. [Python API使用](#6-python-api使用)
7. [Web界面使用](#7-web界面使用)
8. [需求文档格式](#8-需求文档格式)
9. [项目文件结构详解](#9-项目文件结构详解)
10. [新增领域操作指南](#10-新增领域操作指南)
11. [领域配置详解](#11-领域配置详解)
12. [调用链模板提取方法](#12-调用链模板提取方法)
13. [配置LLM](#13-配置llm)
14. [工作原理详解](#14-工作原理详解)
15. [已有领域：DeepSeek推理](#15-已有领域deepseek推理)
16. [扩展路线图](#16-扩展路线图)
17. [常见问题](#17-常见问题)

---

## 1. 项目概述

### 是什么

TestForge 将半结构化的测试需求文档自动转换为可执行的 Python 测试用例代码。它基于 LLM（大语言模型），结合领域知识（调用链模板、基类方法说明、样例用例）生成符合你测试框架规范的代码。

### 核心设计原则

**领域无关骨架 + 领域插件化上下文**

- 核心引擎（`src/pipeline_v2.py`）不包含任何业务逻辑
- 每个测试领域通过"上下文包"注入领域知识
- 新增领域只需准备上下文文件和配置，不改引擎代码
- 支持任意测试框架（pytest/unittest/自研框架）

### 适用场景

| 场景 | 示例 |
|------|------|
| 大模型推理测试 | DeepSeek/GLM/Llama/Qwen 推理精度/性能/功能验证 |
| 大模型训练测试 | 训练loss收敛、梯度检查、checkpoint验证 |
| 接口自动化测试 | API功能/性能/异常测试 |
| 任意参数化测试场景 | 用例间模式重复度高、参数不同但结构相同 |

### 与 LLMCFG-TGen 论文的关系

TestForge 从论文 "LLMCFG-TGen" 的复现工程演进而来。论文的三步流水线（CFG生成→路径枚举→测试用例）被重新设计为四步流水线（需求解析→调用链匹配→代码生成→校验），更适合工业落地：

| 论文设计 | TestForge 设计 | 变化原因 |
|----------|---------------|----------|
| NL用例 → CFG → 测试路径 → NL测试用例 | 需求文档 → 调用链模板 → Python测试代码 | 工业场景中调用链模式固定，不需要CFG路径分析 |
| 通用测试场景 | 领域插件化 | 不同测试领域的基类、import、调用链完全不同 |
| 输出NL文本描述 | 输出可执行Python代码 | 最终目标是直接可用的测试文件 |

论文原始代码保留在 `src/pipeline.py` 中，TestForge v2 在 `src/pipeline_v2.py`。

---

## 2. 环境准备

### 前提条件

- Python 3.10+
- 一个有效的 LLM API Key（OpenAI GPT-4o 或兼容 API）

### 安装

```bash
cd ~/Documents/My_rep/LLMCFG-TGen
pip install -r requirements.txt
```

依赖：`openai`, `python-dotenv`, `flask`, `graphviz`, `pyyaml`

### 配置 LLM API

```bash
# 方式一：环境变量
export OPENAI_API_KEY="sk-your-key"
export LLM_MODEL="gpt-4o"             # 可选，默认gpt-4o
export OPENAI_BASE_URL=""              # 可选，兼容API的base URL

# 方式二：.env文件
cp .env.example .env
# 编辑 .env 填入实际值
```

### 验证安装

```bash
# 验证领域上下文加载
python3 -c "
from src.pipeline_v2 import DomainContext
ctx = DomainContext('deepseek_infer')
print(f'OK: domain={ctx.domain}, views={[k for k,v in ctx.views.items() if v]}, samples={len(ctx.sample_cases)}')
"
```

---

## 3. 快速开始

### 从需求文档生成测试用例

```bash
# 使用预置的DeepSeek ceval需求文档
python -m src.pipeline_v2 \
  --domain deepseek_infer \
  --file data/examples/req_deepseek_ceval.json \
  --output data/output/result.json
```

输出：
- `data/output/result.json` — 完整结果（解析+模板+代码+校验）
- `data/output/result.py` — 生成的Python测试代码

### 直接查看生成的代码

```bash
python -m src.pipeline_v2 \
  --domain deepseek_infer \
  --file data/examples/req_deepseek_ceval.json
```

直接在终端打印生成的Python代码。

---

## 4. 核心架构

### 四步流水线

```
需求文档 + 领域标识(domain)
    │
    ├─→ 加载领域配置 (config/domains/{domain}.yaml)
    ├─→ 加载上下文包 (context_store/{domain}/)
    │
    ▼
┌──────────────────────────────────────┐
│ Step 1: 需求解析                      │
│ 需求文档 → LLM → 结构化需求JSON        │
│ 从用例名自动提取: 网络/框架/卡数/量化等  │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ Step 2: 调用链匹配                    │
│ 结构化需求 → 评分匹配 → 最佳调用链模板  │
│ 匹配维度: framework + scenario + type │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ Step 3: 代码生成                      │
│ 需求JSON + 调用链 + few-shot样例       │
│ + 基类方法说明 + import路径            │
│ → LLM生成完整Python测试类             │
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ Step 4: 代码校验                      │
│ 编译检查 + AST结构验证 + 关键字检查     │
└──────────────────────────────────────┘
    │
    ▼
输出: 可执行的测试文件(.py) + 结果报告(.json)
```

### 领域插件化设计

```
引擎层（不改）                    领域层（每个领域一份）
─────────────                    ─────────────────────
                                 
pipeline_v2.py ─── 读取 ───→  config/domains/{domain}.yaml
                                 ├── 继承体系映射
                                 ├── import路径
                                 ├── 调用链模板
                                 └── pytest装饰器映射
                                 
DomainContext ─── 加载 ───→  context_store/{domain}/
                                 ├── VIEW1 模块签名
                                 ├── VIEW2 依赖图谱
                                 ├── VIEW3 工具规范
                                 └── sample_cases/ (few-shot)
```

---

## 5. 命令行使用

### 基本命令

```bash
python -m src.pipeline_v2 \
  --domain <领域名> \
  --file <需求文档路径> \
  --output <输出路径>
```

### 完整参数

| 参数 | 说明 | 必填 | 示例 |
|------|------|------|------|
| `--domain` | 领域标识 | 是 | `deepseek_infer` |
| `--file` | 需求文档文件路径 | 二选一 | `req.json` |
| `--requirement` | 需求文档文本 | 二选一 | `"用例名: test_..."` |
| `--output` | 输出文件路径 | 否 | `result.json` |
| `--model` | LLM模型名 | 否 | `gpt-4o` |
| `--verbose` | 详细日志 | 否 | — |

### 示例

```bash
# 从文件生成
python -m src.pipeline_v2 \
  --domain deepseek_infer \
  --file my_requirement.json \
  --output output/result.json

# 直接传入需求文本
python -m src.pipeline_v2 \
  --domain deepseek_infer \
  --requirement "用例名: test_ms_deepseekr1_671b_vllm_infer_v1_acc_bf16_910b3_32p_0001
模型名称: deepseek r1 671B
..."

# 指定模型
python -m src.pipeline_v2 \
  --domain deepseek_infer \
  --file req.json \
  --model gpt-4o

# 详细日志（调试用）
python -m src.pipeline_v2 \
  --domain deepseek_infer \
  --file req.json \
  --verbose
```

---

## 6. Python API使用

### 基本用法

```python
from src.pipeline_v2 import TestForgePipeline

# 创建流水线（指定领域）
pipeline = TestForgePipeline(domain="deepseek_infer")

# 执行
result = pipeline.run(requirement_text)

# 获取生成的代码
print(result["generated_code"])

# 查看校验结果
print(result["validation"])
```

### 自定义LLM

```python
pipeline = TestForgePipeline(
    domain="deepseek_infer",
    model="gpt-4o",
    api_key="sk-xxx",
    base_url="https://api.deepseek.com/v1",
)
```

### 分步执行

```python
from src.pipeline_v2 import DomainContext
from src.llm_client import LLMClient

ctx = DomainContext("deepseek_infer")

# 只看解析结果
parsed = pipeline._parse_requirement(requirement_text)
print(parsed)

# 只看匹配的调用链
matched = pipeline._match_call_chain(parsed)
print(matched["name"])

# 查看领域信息
print(ctx.get_imports("deepseek", "vllm"))
print(ctx.get_base_class("deepseek"))
print(ctx.get_pytest_markers("32p"))
print(list(ctx.get_call_chain_templates().keys()))
```

### 输出结构

```python
result = pipeline.run(requirement)

result["requirement_parsed"]   # 结构化需求JSON
result["matched_template"]     # 匹配的调用链模板
result["generated_code"]       # Python测试代码字符串
result["validation"]           # {"valid": True/False, "errors": [], "warnings": []}
result["metadata"]             # 运行元数据
```

---

## 7. Web界面使用

```bash
python web/app.py    # 访问 http://localhost:5001
```

> 注意：当前Web界面仍为LLMCFG-TGen论文版本。TestForge v2的Web界面待开发。

---

## 8. 需求文档格式

### 支持的格式

TestForge 接受半结构化的需求文档。可以是纯文本或JSON文件。

### 推荐格式（纯文本）

```
用例名：test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003

模型名称，规格：deepseek r1 671B

权重路径：self.ds_r1_model_path = "/home/workspace/..."

模型所在代码仓：不涉及

服务拉起前环境变量（可选）：
export MS_ENABLE_LCCL=off;export ...

服务拉起命令：
vllm-mindspore serve {self.ds_r1_model_path} --trust-remote-code ...

执行测试类型：
aisbench ceval测试，使用aisbench_test方法，测试规格：max_out_en:4096，batch_size:256，数据集：cevaLchat_prompt
要求：执行两次ceval测试，执行日志需分别保存

校验指标及基线来源：
校验两次ceval测试得分，两次等分相差不能超过1
```

### JSON格式

```json
{
  "requirement": "用例名：test_...\n模型名称：...\n..."
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| 用例名 | ✅ | 完整的测试用例类名，包含所有参数维度 |
| 模型名称/规格 | ✅ | 网络名和参数量 |
| 权重路径 | ✅ | Python变量赋值语句 |
| 模型所在代码仓 | ❌ | 代码仓库路径，可为"不涉及" |
| 服务拉起前环境变量 | ❌ | shell export语句 |
| 服务拉起命令 | ❌ | 完整的服务启动命令 |
| 执行测试类型 | ✅ | 测试方法、数据集、测试规格 |
| 校验指标及基线 | ✅ | 通过标准和判定逻辑 |

### 用例名中的参数维度

用例名本身是结构化信息，引擎会自动解析：

```
test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003
     │         │     │     │    │     │    │     │    │     │    └─ 序号
     │         │     │     │    │     │    │     │    └─ 硬件芯片
     │         │     │     │    │     │    │     └─ 权重类型(bf16/int8/w4a8)
     │         │     │     │    │     │    └─ 卡数(8p/16p/32p)
     │         │     │     │    │     └─ 版本(v0/v1)
     │         │     │     │    └─ 测试子类型(acc/perf/func/det_ceval)
     │         │     │     └─ 场景(infer/train)
     │         │     └─ 框架(vllm/mindie)
     │         └─ 模型规格
     └─ 网络+版本
```

---

## 9. 项目文件结构详解

```
LLMCFG-TGen/
│
├── src/                              # 核心引擎（领域无关）
│   ├── pipeline_v2.py                # ★ TestForge v2 主流水线
│   ├── pipeline.py                   # LLMCFG-TGen 论文原版（保留）
│   ├── llm_client.py                 # LLM API客户端
│   ├── cfg_generator.py              # CFG生成器（论文组件，保留）
│   ├── path_extractor.py             # 路径枚举器（论文组件，保留）
│   └── test_creator.py               # 测试创建器（论文组件，保留）
│
├── config/
│   └── domains/                      # ★ 领域配置（每个领域一个YAML）
│       ├── _TEMPLATE.yaml            # 新领域模板
│       └── deepseek_infer.yaml       # DeepSeek推理场景配置
│
├── context_store/                    # ★ 领域上下文包
│   ├── deepseek_infer/               # DeepSeek推理
│   │   ├── VIEW1_module_signatures.md  # 模块签名（类/方法列表）
│   │   ├── VIEW2_dependency_graph.md   # 依赖图谱（import路径）
│   │   ├── VIEW3_tool_specs.md         # 工具规范（API说明）
│   │   └── sample_cases/               # few-shot样例用例
│   │       └── sample_001_w4a8_acc_perf.py
│   ├── deepseek_train/               # （预留）训练场景
│   ├── glm_infer/                    # （预留）GLM推理
│   └── llama_infer/                  # （预留）Llama推理
│
├── data/
│   ├── examples/                     # 示例需求文档
│   │   ├── req_deepseek_ceval.json
│   │   └── ...
│   └── output/                       # 生成结果输出目录
│
├── prompts/                          # LLM提示词模板
│   └── prompt_templates.py
│
├── tests/                            # 单元测试
│   └── test_pipeline.py
│
├── web/                              # Web界面
│   └── app.py
│
├── README.md                         # 项目概述
├── USAGE.md                          # 本文件
├── ADAPTATION_ANALYSIS.md            # 适配分析文档
├── ADAPTATION_PLAN.md                # 适配方案文档
├── NEW_DOMAIN_GUIDE.md              # 新领域简要指南
├── requirements.txt                  # Python依赖
└── .env.example                      # 环境变量模板
```

---

## 10. 新增领域操作指南

### 概述

新增一个测试领域（如"GLM推理测试"或"DeepSeek训练测试"）需要准备**三样东西**：

1. **三大视图文件**（放入 `context_store/{领域}/`）
2. **样例用例**（放入 `context_store/{领域}/sample_cases/`）
3. **领域配置YAML**（放入 `config/domains/{领域}.yaml`）

**不改引擎代码。**

### 详细步骤

#### 步骤1：创建领域目录

```bash
# 以"GLM推理测试"为例
DOMAIN="glm_infer"
mkdir -p context_store/$DOMAIN/sample_cases
```

#### 步骤2：准备三大视图

三大视图是LLM生成代码的上下文知识，来自你的测试工程代码的静态分析。

**VIEW1 模块签名** (`context_store/{领域}/VIEW1_module_signatures.md`)

记录测试工程中所有相关模块的类和函数签名：

```markdown
## 文件: `common/ms_aw/network/net/glm3.py`
### 暴露的类
- **GLM** `-> 继承自: SolutionTestBase`
  > GLM网络通用方法类

### 暴露的方法
- `glm_server_start(self, ...)` [GLM]
  > 启动GLM推理服务
- `glm_benchmark_test(self, ...)` [GLM]
  > GLM基准测试
- ...

## 文件: `cases/02network/02nlp/glm/...`
### 测试场景定义
- **Test_glm4_9b_vllm_infer_acc_bf16_910b3_8p_0001** `-> 继承自: GLM`
  > GLM4 9b, bf16, 910b3 8卡, vllm推理, 精度验证
```

获取方式：
- 手动从代码中提取
- 使用AST解析工具自动生成（参考你工程中的 `RecursiveRetriever`）
- `scan_directory` → 提取类/函数签名

**VIEW2 依赖图谱** (`context_store/{领域}/VIEW2_dependency_graph.md`)

记录import路径和跨模块依赖：

```markdown
## 1. 核心导入映射

### `cases/02network/02nlp/glm/v1/infer/test_glm4_9b_vllm_infer_acc_bf16_910b3_8p_0001.py` 依赖于:
- `from common.ms_aw.network.net.glm3 import GLM`
- `from common.config.config import CLUSTER_CONFIG_NEW, VLLM_BENCHMARK_TOOL_PATH`
```

获取方式：
- 使用Python的 `ast` 模块解析import语句
- 或使用你工程中的 `get_call_chain` 工具

**VIEW3 工具规范** (`context_store/{领域}/VIEW3_tool_specs.md`)

记录可调用的工具API：

```markdown
## RecursiveRetriever
- `analyze_file(file_path)` → 文件详情
- `scan_directory(dir)` → 目录结构
- `get_call_chain(func_name)` → 调用链
```

#### 步骤3：放入样例用例

收集2-3个该领域的完整测试用例代码（脱敏后），放入 `sample_cases/`：

```bash
cp /path/to/test_glm4_acc.py context_store/glm_infer/sample_cases/sample_001_acc.py
cp /path/to/test_glm4_perf.py context_store/glm_infer/sample_cases/sample_002_perf.py
```

这些样例用作LLM的few-shot参考，帮助生成风格一致的代码。

#### 步骤4：创建领域配置

```bash
cp config/domains/_TEMPLATE.yaml config/domains/glm_infer.yaml
```

编辑配置文件，填入以下内容（详见下一节）：

```yaml
domain: glm_infer
description: "GLM大模型推理测试"

class_hierarchy:
  network_to_base:
    glm:
      base_class: "GLM"
      import: "from common.ms_aw.network.net.glm3 import GLM"
  framework_imports:
    vllm:
      - "from common.config.config import CLUSTER_CONFIG_NEW, VLLM_BENCHMARK_TOOL_PATH"

call_chain_templates:
  infer_vllm_acc:
    match_rule: "scenario=='infer' and framework=='vllm' and test_type=='accuracy'"
    setup: [...]
    test_run: [...]
    teardown: [...]

pytest_markers:
  cards_to_marker:
    "8p": ["@pytest.mark.env_Network_Ascend_Arm_8p", "@pytest.mark.env_Network_Ascend_X86_8p"]
    ...

method_specs:
  glm_server_start: {desc: "启动GLM推理服务"}
  ...
```

#### 步骤5：验证

```bash
# 先验证上下文加载
python3 -c "
from src.pipeline_v2 import DomainContext
ctx = DomainContext('glm_infer')
print(f'OK: views={[k for k,v in ctx.views.items() if v]}, samples={len(ctx.sample_cases)}')
"

# 再验证完整流水线
python -m src.pipeline_v2 --domain glm_infer --file test_req.json --output result.json
```

### 工作量估算

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| 收集2-3个样例用例 | 0.5h | 从已有用例中选取代表性用例 |
| 提取模块签名(VIEW1) | 1-2h | 可用AST工具半自动化 |
| 提取依赖图谱(VIEW2) | 0.5h | import解析 |
| 编写工具规范(VIEW3) | 0.5h | 通常可直接复用 |
| 提取调用链模板 | 2-3h | **最耗时**，需人工分析每种测试类型 |
| 编写领域配置YAML | 1h | 按模板填空 |
| **总计** | **5-7h** | 一次性投入，后续维护成本低 |

---

## 11. 领域配置详解

领域配置文件 `config/domains/{domain}.yaml` 的完整结构：

### domain 和 description

```yaml
domain: deepseek_infer          # 必须与context_store目录名一致
description: "DeepSeek大模型推理测试用例自动生成"
```

### requirement_parsing — 需求文档解析规则

```yaml
requirement_parsing:
  # 需求文档中的字段映射
  fields:
    case_name:
      source: "用例名"           # 对应需求文档中的标签
      required: true
    weight_path_var:
      source: "权重路径"
      required: true
      extract_var_name: true     # 自动提取 self.xxx 变量名
  # 用例名中自动提取的维度
  name_patterns:
    network: "deepseek"
    framework: "vllm"
    # ...
```

### class_hierarchy — 继承体系

```yaml
class_hierarchy:
  base_class: "Deepseek"                     # 默认基类
  base_import: "from common.ms_aw.network.net.deepseek import Deepseek"
  network_to_base:                           # 网络名→基类映射
    deepseek:
      base_class: "Deepseek"
      import: "from common.ms_aw.network.net.deepseek import Deepseek"
    glm:
      base_class: "GLM"
      import: "from common.ms_aw.network.net.glm3 import GLM"
    llama:
      base_class: "Llama"
      import: "from common.ms_aw.network.net.llama2 import Llama"
  common_imports:                             # 所有用例都需要的import
    - "import pytest"
    - "import importlib"
  framework_imports:                          # 框架特定import
    vllm:
      - "from common.config.config import CLUSTER_CONFIG_NEW, VLLM_BENCHMARK_TOOL_PATH"
    mindie:
      - "from common.config.config import MINDFORMERS_ROOT, SHARE_CKPT_PATH"
```

**扩展新网络时**，只需在 `network_to_base` 中添加一条映射。

### call_chain_templates — 调用链模板（核心）

```yaml
call_chain_templates:
  infer_vllm_acc:                              # 模板名（自定义）
    match_rule: "scenario=='infer' and framework=='vllm' and test_type=='accuracy'"
    setup:
      - "super().setup(case_name)"
      - "self.copy_model(self.model_path, {CODE_REPO})"
      - "SSHHelper(...)"
      - "self.parse_cluster_file()"
      - "self.set_vllm_server_prepare()"
    test_run:
      - "self.start_vllm_server(start_server_cmd)"
      - "vllm_ip, vllm_port = self.get_vllm_log_ip_port(log_path)"
      - "acc = self.aisbench_test(...)"
      - "self.check_benchmark_acc(accuracy=acc, ...)"
      - "self.check_err_info_in_log(...)"
    teardown:
      - "self.stop_vllm_server()"
      - "super().teardown()"
```

每条模板包含：
- `match_rule`: 匹配条件（用引擎评分选择最佳模板）
- `setup`/`test_run`/`teardown`: 方法调用序列（指导LLM生成代码）

### pytest_markers — 装饰器映射

```yaml
pytest_markers:
  cards_to_marker:
    "8p":
      - "@pytest.mark.env_Network_Ascend_Arm_8p"
      - "@pytest.mark.env_Network_Ascend_X86_8p"
    "16p": [...]
    "32p": [...]
  default_timeout: 14400
  default_level: "@pytest.mark.level1"
```

### method_specs — 基类方法说明

```yaml
method_specs:
  aisbench_test:
    category: metric
    tag: acc
    desc: "华为官方精度测试工具"
    inferred_signature: "aisbench_test(ais_bench_path, api_type, dataset, path, model, host_ip, host_port, max_out_len, batch_size, cycle_time)"
  vllm_benchmark_perf_test:
    category: metric
    tag: perf
    desc: "VLLM 性能基准测试"
    inferred_signature: "vllm_benchmark_perf_test(ckpt_path, parallel_num, input_tokens, output_tokens, host_ip, port)"
```

这些信息注入到LLM的Prompt中，帮助生成正确的API调用。

---

## 12. 调用链模板提取方法

调用链模板是整个系统最核心的知识。以下是提取方法：

### 方法一：从代码中手动提取

1. 收集同一测试类型的3-5个用例
2. 对每个用例，记录setup/test_run/teardown中的方法调用序列
3. 找出共同的调用模式，参数化可变部分

### 方法二：从Execution Trace中自动提取

如果你有类似V2.2的调用链数据：

```python
# 示例：从V2.2数据中提取模板
traces = {
    "test_acc_001": {
        "setup": ["super().setup", "copy_model", "set_vllm_server_prepare", "deploy_cluster_env"],
        "test_run": ["start_vllm_server", "get_vllm_log_ip_port", "aisbench_test", "check_benchmark_acc"],
        "teardown": ["stop_vllm_server", "super().teardown"]
    },
    "test_acc_002": {
        "setup": ["super().setup", "copy_model", "set_vllm_server_prepare", "deploy_cluster_env"],
        "test_run": ["start_vllm_server", "get_vllm_log_ip_port", "aisbench_test", "check_benchmark_acc"],
        "teardown": ["stop_vllm_server", "super().teardown"]
    }
}

# 找共同模式 → 即为模板
```

### 方法三：用你的三大视图工具

```python
# 使用工程中的RecursiveRetriever
retriever.analyze_file("cases/02network/02nlp/deepseek/r1/infer/test_xxx.py")
retriever.get_call_chain("test_run")
```

### 提取要点

| 要点 | 说明 |
|------|------|
| 按测试类型分组 | acc/perf/func/det等各有不同调用链 |
| 按框架分组 | vllm和mindie的setup/teardown完全不同 |
| 参数化可变部分 | 路径、规格值等用占位符 |
| 保留核心骨架 | super().setup/copy_model等是必选项 |
| 注意边缘情况 | det类型不拉起服务，quant类型有额外步骤 |

### 已有领域的调用链模板参考

DeepSeek推理领域当前包含5个模板：

| 模板名 | 匹配条件 | setup步骤数 | test_run步骤数 |
|--------|----------|-----------|-------------|
| infer_vllm_acc | vllm + accuracy | 7 | 5 |
| infer_vllm_perf | vllm + performance | 6 | 4 |
| infer_vllm_det | vllm + det_* | 2 | 6 |
| infer_vllm_func | vllm + function | 5 | 3 |
| infer_mindie_acc | mindie + accuracy | 11 | 5 |

---

## 13. 配置LLM

### 支持的模型

| 模型 | 推荐度 | 说明 |
|------|--------|------|
| GPT-4o | ⭐⭐⭐⭐⭐ | 代码生成质量最高 |
| GPT-4o-mini | ⭐⭐⭐⭐ | 性价比高，调试用 |
| Claude 3.5 Sonnet | ⭐⭐⭐⭐ | 需通过兼容API |
| DeepSeek-V3 | ⭐⭐⭐⭐ | 国内可用，成本低 |
| GLM-4 | ⭐⭐⭐ | 需测试代码生成质量 |

### 配置方式

```bash
# OpenAI官方
export OPENAI_API_KEY="sk-xxx"
export LLM_MODEL="gpt-4o"

# 兼容API（如DeepSeek）
export OPENAI_API_KEY="your-deepseek-key"
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
export LLM_MODEL="deepseek-chat"

# 或在.env文件中配置
```

### LLM调用次数

```
总调用 = 1次（需求解析）+ 1次（代码生成）
```

注意：调用链匹配和代码校验是纯本地计算，不调用LLM。

### Token估算

```
需求解析: ~500 input + ~300 output ≈ 800 tokens
代码生成: ~5000 input + ~1000 output ≈ 6000 tokens
总计: ~7000 tokens / 每个用例
```

以GPT-4o计价，每个用例约 $0.04-0.06。

---

## 14. 工作原理详解

### Step 1: 需求解析

LLM从半结构化需求文档中提取：
- 用例名维度（网络/框架/卡数/量化等）
- 具体参数（路径、命令、测试规格）
- 校验标准

输出为结构化JSON，供后续步骤使用。

### Step 2: 调用链匹配

纯本地计算，零LLM调用。评分逻辑：

```python
score = 0
if framework in match_rule: score += 3
if scenario in match_rule: score += 3
if test_type in match_rule: score += 2
if test_subtype in template_name: score += 3
```

选择得分最高的模板。匹配结果包含setup/test_run/teardown的完整方法调用序列。

### Step 3: 代码生成

将以下上下文打包为Prompt，一次性发给LLM：
1. 结构化需求JSON（Step 1输出）
2. 匹配的调用链模板（Step 2输出）
3. import语句 + 基类名 + pytest装饰器（从领域配置）
4. 基类方法签名说明（从method_specs）
5. 2-3个样例用例代码（从sample_cases，作为few-shot）

LLM根据这些上下文生成完整Python测试类。

### Step 4: 代码校验

纯本地计算：
1. **编译检查** — `compile()` 验证语法
2. **AST检查** — 确认包含class/setup/test_run/teardown
3. **关键字检查** — 确认包含 `super()` 等必要调用

---

## 15. 已有领域：DeepSeek推理

### 当前状态

| 项目 | 状态 |
|------|------|
| 三大视图 | ✅ 已加载（VIEW1/2/3） |
| 样例用例 | ✅ 1个（w4a8 acc+perf） |
| 调用链模板 | ✅ 5个（acc/perf/func/det/mindie_acc） |
| 基类方法说明 | ✅ 6个 |
| pytest映射 | ✅ 8p/16p/32p |
| 领域配置 | ✅ 完整 |

### 已有调用链模板

```
infer_vllm_acc       → vllm推理精度测试（最常用）
infer_vllm_perf      → vllm推理性能测试
infer_vllm_det       → vllm推理det类型测试（服务预部署）
infer_vllm_func      → vllm推理功能测试
infer_mindie_acc     → mindie推理精度测试
```

### 已验证的需求→代码生成

使用 `req_deepseek_ceval.json` 需求文档，生成了正确的测试用例代码（约85%准确率，需微调2处）。

---

## 16. 扩展路线图

### 短期（1-2周）

1. **补充DeepSeek推理样例** — 增加2-3个不同类型的样例用例（perf/func/mindie）
2. **补充调用链模板** — 从V2.2中提取更多模板（quant类型、mindie perf等）
3. **优化代码生成Prompt** — 减少"模板中有但需求没要求"的冗余代码
4. **Web界面适配** — 更新web/app.py支持TestForge v2

### 中期（1-2月）

5. **新增领域：DeepSeek训练** — 复用DeepSeek网络层，添加训练特有的调用链
6. **新增领域：GLM推理** — 只需基类映射 + 样例 + 调用链模板
7. **新增领域：Llama推理** — 同上
8. **RAG增强** — 将样例用例向量化，按相似度检索最相关的few-shot

### 长期（持续）

9. **反馈学习** — 人工审核结果作为RL反馈信号
10. **自动化模板提取** — 从现有用例代码自动提取调用链模板
11. **多文件生成** — 同时生成 test_xxx.py + net_config.py + __init__.py
12. **批量处理** — 一批需求文档 → 一批测试文件

---

## 17. 常见问题

### Q: 新增领域时，调用链模板不知道怎么写怎么办？

把3-5个该领域的已有用例代码发给我，我帮你提取调用链模板。

### Q: 生成的代码有冗余步骤（模板中有但需求没要求的）

这是已知问题。Step 2匹配到的调用链模板是"完整版"，但需求可能只要求其中一部分。解决方案：
1. 优化Prompt中强调"只生成需求中要求的步骤"
2. 在需求解析阶段标记"不需要的步骤"
3. 增加更多细粒度的模板（如把det_ceval和det_other分开）

### Q: 能否处理中文需求文档？

可以。LLM能理解中文输入。Prompt本身是中英混合的，生成代码中的注释和docstring可以是中文。

### Q: 如何处理需求文档中"自定义校验逻辑"（如"两次得分差不超过1"）

这正是TestForge的优势——LLM能理解自然语言描述的校验逻辑，并生成对应的Python代码。不需要预定义所有校验模式。

### Q: 领域配置中的match_rule是精确匹配还是模糊匹配？

当前是简单的关键词评分匹配。未来可以升级为基于embedding的语义匹配。

### Q: 一个用例的生成成本是多少？

约7000 tokens（GPT-4o约$0.05）。如果用DeepSeek-V3等低成本模型，约$0.001。

---

*TestForge v2 — 基于LLMCFG-TGen论文(arXiv:2512.06401)演进*
*领域无关的测试用例自动生成引擎*
