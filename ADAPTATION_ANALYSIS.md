# LLMCFG-TGen 适配你的测试工程 — 使用流程与适配分析

---

## 一、你的测试工程架构解析

通过分析 `业务流程` 文件夹中的架构文档和用例样例，你的测试工程核心结构如下：

### 多层基类继承体系

```
SolutionTestBase                    ← 顶层基类（基础设施层）
  └── Infer                         ← 推理公共方法层（common/ms_aw/network/infer.py）
        └── Deepseek                ← 网络特定层（common/ms_aw/network/net/deepseek.py）
              └── Test_xxx_具体用例   ← 具体测试场景（cases/02network/02nlp/deepseek/...）
```

每一层的职责：

| 层级 | 类 | 职责 | 提供的方法 |
|------|----|------|-----------|
| **顶层** | SolutionTestBase | 测试基础设施、日志、环境管理 | `ms_log`, 基本setup/teardown |
| **中间层** | Infer (3557行) | 推理通用能力 | `setup()`, `copy_model()`, `set_vllm_server_prepare()`, `vllm_benchmark_perf_test()`, `check_benchmark_acc()`, `get_vllm_log_ip_port()`, `check_err_info_in_log()` 等87个方法 |
| **网络层** | Deepseek | DeepSeek网络特有配置 | `set_deepseek_config_prepare()`, `set_deepseek_func_infer_config()`, `hybrid_parallel_vllm()` |
| **用例层** | Test_xxx | 具体测试场景编排 | 只需实现 `setup()`, `test_run()`, `teardown()` |

### 典型用例的三段式结构

每个用例严格遵循 `setup → test_run → teardown` 的三段式：

- **setup**: `super().setup()` → 环境准备（`copy_model`, `set_vllm_server_prepare`, `SSHHelper`, `parse_cluster_file`, `deploy_cluster_env`）
- **test_run**: 服务启动 → 基准测试执行 → 结果校验
- **teardown**: 清理 → `super().teardown()`

### 用例的参数化命名模式

用例类名本身就是"配置文档"：
```
test_ms_deepseekr1_671b_vllm_infer_v1_w4a8_910b3_8p_0001.py
     │      │        │    │     │    │    │     │    └─ 序号
     │      │        │    │     │    │    │    └─ 8卡
     │      │        │    │     │    │    └─ 910B3芯片
     │      │        │    │     │    └─ w4a8量化
     │      │        │    │     └─ 版本v1
     │      │        │    └─ 推理场景
     │      │        └─ vllm框架
     │      └─ 671B参数量
     └─ deepseek-r1网络
```

---

## 二、LLMCFG-TGen 与你的工程之间的映射鸿沟

### 论文设计 vs 你的实际需求

```
论文 LLMCFG-TGen 的假设：                 你的实际场景：
─────────────────────                    ──────────────
输入: 面向用户的业务用例描述               输入: 模型推理需求规格（网络/权重/环境/精度/性能）
  "用户在登录页输入密码..."                  "DeepSeek-R1 671B, w4a8量化, 910B3 8卡, vllm推理"

输出: 抽象测试用例（NL文本）               输出: 可执行的Python测试类（继承Deepseek基类）
  TC-001: 验证登录成功                      class Test_ms_deepseekr1_671b_vllm_infer_...
    Step 1: 输入用户名                         def setup(self): ...
    Step 2: 输入密码                           def test_run(self): ...
                                               def teardown(self): ...

中间表示: CFG（控制流图）                   中间表示: 需要推理调用链（Execution Trace）
  表示用户操作分支                           表示 setup→服务部署→测试执行→校验 的流水线
```

**核心差距：**
1. 论文的"用例"是用户故事，你的"用例"是模型推理测试场景
2. 论文输出NL描述的测试步骤，你需要的是可执行的Python代码
3. 论文的CFG表示操作分支，你需要的是基类方法调用链

---

## 三、适配方案：在LLMCFG-TGen基础上新增Step 4

### 推荐的完整流程

```
需求文档（模型推理规格）
    │
    ▼
┌──────────────────────────────────────────────────┐
│ Phase A: 需求解析（复用LLMCFG-TGen思路，改造Prompt）│
│                                                    │
│ 输入: "DeepSeek-R1 671B, int8量化, 910B3 16卡,     │
│        vllm推理, 精度验证"                          │
│                                                    │
│ 输出: 结构化测试需求                                │
│   {                                                │
│     network: "deepseek-r1",                        │
│     size: "671b",                                  │
│     quantization: "int8",                          │
│     hardware: "910b3",                             │
│     cards: 16,                                     │
│     framework: "vllm",                             │
│     test_type: "accuracy",                         │
│     version: "v0"                                  │
│   }                                                │
└──────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────┐
│ Phase B: 测试流程图生成（改造LLMCFG-TGen Step 1+2） │
│                                                    │
│ 基于需求 → 生成测试执行流图（类似CFG）               │
│                                                    │
│ setup分支:                                         │
│   super().setup → copy_model → SSHHelper →         │
│   parse_cluster_file → set_vllm_server_prepare →   │
│   deploy_cluster_env → ssh_pass                    │
│                                                    │
│ test_run分支:                                      │
│   start_vllm_server → get_vllm_log_ip_port →       │
│   [accuracy路径]                                   │
│     get_benchmark_acc → check_benchmark_acc →       │
│     check_err_info_in_log                          │
│   [performance路径]                                │
│     vllm_benchmark_perf_test →                     │
│     vllm_benchmark_perf_check                      │
│                                                    │
│ teardown分支:                                      │
│   stop_vllm_server → super().teardown              │
└──────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────┐
│ Phase C: 代码生成（新增Step 4 — 核心适配层）         │
│                                                    │
│ 输入:                                               │
│   1. 结构化测试需求                                 │
│   2. 测试执行流图                                   │
│   3. 你的三大视图上下文（关键！）                     │
│     - V1.2 模块签名（基类方法列表）                  │
│     - V2.2 调用链（相似用例的setup/test/teardown）   │
│     - V3 工具规范（RecursiveRetriever API）          │
│   4. 2-3个最相似的历史用例（RAG检索）                 │
│                                                    │
│ 输出: 可执行的测试类Python代码                       │
│   - 正确的继承链                                    │
│   - 正确的import                                    │
│   - 正确的setup/test_run/teardown实现               │
│   - 正确的配置参数                                  │
│   - pytest装饰器                                    │
│   - net_config.py配置                              │
└──────────────────────────────────────────────────┘
```

---

## 四、适配需要的额外信息

基于现有文件，以下信息**已有**和**需要补充**的：

### ✅ 已有的信息（足够起步）

| 信息 | 来源文件 | 用途 |
|------|----------|------|
| 仓库目录结构 | V1.1 仓库骨架 | 文件放置路径、import路径 |
| 模块签名（类/方法） | V1.2 模块签名 | 可调用的基类方法列表 |
| 典型调用链 | V2.2 执行调用链 | setup/test_run/teardown的标准编排模式 |
| 依赖关系 | V2 依赖图谱 | import路径、跨模块引用 |
| 工具规范 | V3 工具规范 | RecursiveRetriever API |
| 用例代码样例 | 用例样例.md | 具体测试代码模板 |
| 三大视图架构 | 架构说明.md | 整体认知框架 |

### ⚠️ 需要补充的信息

**1. net_config.py 完整模板**
- 你的用例样例中引用了 `self.model_path`, `self.deepseekr1_gptq_w4a8_safetensors`, `self.server_port` 等配置变量
- 这些变量来自 `net_config.py`，但我只看到了文件名，没有看到内容
- **需要：** 一个完整的 `net_config.py` 样例（含所有配置字段的定义和取值规则）

**2. 基类方法的参数签名详情**
- V1.2中只有方法名，缺少参数详情
- 例如 `vllm_benchmark_perf_test(self, ...)` 的完整参数列表是什么？
- `check_benchmark_acc(self, accuracy, acc_stand, acc_error)` 的参数含义和典型值？
- **需要：** 关键基类方法的完整签名和参数说明（至少 `Infer` 和 `Deepseek` 中被频繁调用的20-30个方法）

**3. 配置常量的取值范围**
- `GOLDEN_STICK_ROOT`, `DATA_ROOT`, `SHARE_CKPT_PATH` 等路径常量
- 精度标准值（`acc_stand`, `perf_stand`）的确定规则
- 芯片型号（910b3）、卡数（8p/16p/32p）与部署策略的映射关系
- **需要：** `common/config/config.py` 的脱敏版本或配置项列表

**4. 需求文档的实际格式**
- 你说的"需求文档"在实际中长什么样？
- 是一份Word/PDF的功能需求？还是一个类似"DeepSeek-R1 671B int8 910B3 16p"的参数组合？
- 还是Jira/禅道中的任务描述？
- **需要：** 1-2个真实需求文档样例（脱敏）

**5. 校验标准的确定逻辑**
- 精度校验（`acc_stand=95.98, acc_error=0.99`）这些标准值从哪来？
- 性能校验（`perf_std = {1: 28, 192: 949}`）的确定规则？
- **需要：** 校验标准的来源说明（历史数据？规格书？经验值？）

**6. 测试类型与调用链的映射规则**
- 从调用链来看，不同测试类型有明显不同的编排：
  - **精度测试(acc):** `start_server → get_benchmark_acc → check_benchmark_acc`
  - **性能测试(perf):** `start_server → vllm_benchmark_perf_test → vllm_benchmark_perf_check`
  - **功能测试(func):** `start_server → vllm_server_warm_up → ds_func_perf_test`
  - **推理框架差异:** `vllm` vs `mindie` 的setup/teardown调用链完全不同
- **需要：** 测试类型（acc/perf/func）× 推理框架（vllm/mindie）的完整调用链映射表

---

## 五、推荐的分阶段适配计划

### Phase 1: 先跑通核心流程（1-2周）

**目标：** 对"DeepSeek + vllm + 精度测试"这一最常见场景，实现从需求到代码的自动生成。

**需要的输入：**
1. 3-5个DeepSeek vllm精度测试用例的完整代码（作为few-shot示例）
2. 对应的 `net_config.py` 模板
3. Infer/Deepseek基类中20个核心方法的签名
4. 一个真实的需求文档样例

**实现路径：**
- 暂不改造LLMCFG-TGen的CFG部分
- 直接用LLM + RAG（以现有用例为知识库）生成代码
- 人工审核 + 反馈循环

### Phase 2: 标准化CFG适配（2-3周）

**目标：** 用LLMCFG-TGen的思路构建"测试流程图"，使生成过程可解释、可验证。

**改造点：**
- Prompt #1：从"用户用例→CFG"改为"测试需求→测试执行流图"
- 流图节点不再是用户操作，而是基类方法调用
- 流图边代表方法调用顺序和条件分支

### Phase 3: 全场景覆盖（持续）

**目标：** 扩展到所有网络（GLM、Llama、Qwen等）、所有框架（vllm/mindie/mindformers）、所有测试类型。

---

## 六、立即可做的事情

如果你现在就想尝试，我可以：

1. **用你现有的用例样例作为few-shot**，直接用LLM生成一个新的测试用例（比如"DeepSeek-R1 671B, bf16, 910B3 32卡, vllm推理, 性能验证"），你看效果如何

2. **帮你设计一份"信息采集模板"**，你填完后我就能做完整的适配层开发

3. **改造LLMCFG-TGen的Prompt #1和#2**，适配你的基类体系，使输出直接是可执行的Python测试类

你倾向哪个方向先推进？
