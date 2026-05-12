# LLMCFG-TGen 适配方案 — 从需求文档到可执行测试用例

---

## 一、你的需求文档结构分析

根据你提供的真实需求样例，需求文档的结构已经高度结构化：

```
需求文档
├── 用例名: test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003
├── 模型名称/规格: deepseek r1 671B
├── 权重路径: self.ds_r1_model_path = "/home/workspace/..."
├── 模型所在代码仓: 不涉及
├── 服务拉起前环境变量(可选): export MS_ENABLE_LCCL=off; ...
├── 服务拉起命令: vllm-mindspore serve {self.ds_r1_model_path} ...
├── 执行测试类型: aisbench ceval测试
│   ├── 方法: aisbench_test
│   ├── 测试规格: max_out_en:4096, batch_size:256
│   ├── 数据集: cevaLchat_prompt
│   └── 要求: 执行两次ceval测试，执行日志需分别保存
└── 校验指标及基线来源: 两次ceval得分差不超过1
```

**关键洞察：** 你的需求文档不是非结构化的NL需求，而是**半结构化的参数配置表**。这比论文假设的场景简单得多——不需要CFG来做路径覆盖分析，需要的是**参数提取 + 模板填充 + 调用链编排**。

---

## 二、适配后的完整流水线设计

```
需求文档（半结构化参数配置表）
    │
    ▼
┌─────────────────────────────────────────────────┐
│ Phase 1: 需求解析（结构化提取）                    │
│                                                   │
│ 输入: 需求文档（自然语言+参数混合）                 │
│ 输出: 结构化需求JSON                               │
│                                                   │
│ {                                                 │
│   "case_name": "test_ms_deepseekr1_671b_...",     │
│   "network": "deepseek",                          │
│   "network_version": "r1",                        │
│   "model_size": "671b",                           │
│   "framework": "vllm",                            │
│   "test_subtype": "det_ceval",                    │
│   "version": "v1",                                │
│   "parallel_strategy": "tp32",                    │
│   "weight_type": "bf16",                          │
│   "hardware": "910b3",                            │
│   "cards": "32p",                                 │
│   "sequence": "0003",                             │
│   "weight_path_var": "ds_r1_model_path",          │
│   "weight_path_value": "/home/workspace/...",     │
│   "code_repo": null,                              │
│   "env_vars": "export MS_ENABLE_LCCL=off;...",    │
│   "serve_command": "vllm-mindspore serve ...",    │
│   "test_type": "accuracy",                        │
│   "test_tool": "aisbench_test",                   │
│   "test_dataset": "cevaLchat_prompt",             │
│   "test_params": {                                │
│     "max_out_len": 4096,                          │
│     "batch_size": 256                             │
│   },                                              │
│   "test_requirements": [                          │
│     "执行两次ceval测试，执行日志需分别保存"          │
│   ],                                              │
│   "validation": {                                 │
│     "method": "两次ceval得分差不超过1",            │
│     "type": "consistency_check"                   │
│   }                                               │
│ }                                                 │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│ Phase 2: 调用链匹配（查找最相似的历史用例）          │
│                                                   │
│ 匹配逻辑:                                         │
│   framework=vllm + test_subtype=det → 定位调用链   │
│                                                   │
│ 匹配到已有用例:                                    │
│   test_ms_deepseekr1_671b_vllm_infer_det_ceval_   │
│   v1_tp32_bf16_910b3_32p_0001                     │
│                                                   │
│ 其调用链为:                                        │
│   setup:                                          │
│     super().setup → deploy_cluster_env             │
│   test_run:                                       │
│     cluster_ip_process → vllm_server_check →       │
│     get_vllm_log_ip_port →                         │
│     aisbench_test → aisbench_test →                │
│     check_err_info_in_log →                        │
│     vllm_benchmark_perf_test                       │
│   teardown:                                       │
│     super().teardown                               │
│                                                   │
│ 输出: 调用链模板 + 差异分析                         │
│   新需求 vs 历史用例的差异:                         │
│   - 序号 0003 vs 0001 (无影响)                     │
│   - 执行两次ceval → test_run需循环2次               │
│   - 校验两次得分差 ≤ 1 → 新增自定义校验逻辑         │
│   - 日志分别保存 → 日志路径需区分                    │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│ Phase 3: 代码生成（LLM + 模板 + 上下文）            │
│                                                   │
│ 上下文注入:                                        │
│   1. 用例样例.md (完整代码模板)                     │
│   2. 相似历史用例的调用链 (V2.2)                    │
│   3. 基类方法说明 (6个核心方法)                     │
│   4. 依赖图谱 (import路径)                         │
│                                                   │
│ 输出:                                              │
│   - test_ms_deepseekr1_671b_vllm_infer_det_        │
│     ceval_v1_tp32_bf16_910b3_32p_0003.py          │
│   - net_config.py 补充项                           │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│ Phase 4: 人工审核 + 反馈                           │
│   - LLM标注置信度                                  │
│   - 差异对比视图                                    │
│   - 审核通过 → 入库                                │
│   - 审核修改 → 反馈学习                             │
└─────────────────────────────────────────────────┘
```

---

## 三、LLMCFG-TGen 具体改造点

### 原论文三步 → 适配后的三步

| 论文步骤 | 论文功能 | 适配后功能 | 改造程度 |
|----------|----------|-----------|----------|
| **Step 1: CFG Generation** | NL用例 → CFG（控制流图） | 需求文档 → 结构化需求JSON + 调用链匹配 | **重写Prompt** |
| **Step 2: Path Extraction** | DFS枚举CFG路径 | **保留但语义变化**: 从CFG路径变为setup/test_run/teardown的方法调用序列 | **中等改造** |
| **Step 3: Test Case Creation** | 路径 → NL测试用例 | 调用链 + 需求参数 → Python测试类代码 | **完全重写** |

### 不再需要CFG的原因

论文的CFG解决的是"NL需求中分支路径可能遗漏"的问题。但你的场景中：
- 用例的执行路径由**测试类型**（acc/perf/func/det）和**推理框架**（vllm/mindie）决定
- 这些路径已经固化在基类方法和历史用例中
- 新用例的路径可以通过**匹配最相似历史用例**直接获得

所以CFG可以替换为**调用链模板匹配**。

---

## 四、当前信息是否足够？评估

| 需要的信息 | 状态 | 影响 | 解决方案 |
|-----------|------|------|----------|
| net_config.py 变量内容 | ❌ 不便提供 | 低 | 需求文档已包含权重路径等关键变量，net_config只需生成变量声明模板 |
| 基类方法完整签名 | ❌ 仅有6个 | 中 | 用调用链反推参数：调用链中 `aisbench_test(self, self.ais_bench_path, "vllm_api_general_chat", ...)` 已暴露了实际调用参数 |
| 配置常量值 | ❌ 无 | 低 | 从需求文档和已有用例中提取 |
| 需求文档样例 | ✅ 有1个 | - | 足以验证流程 |
| 用例代码样例 | ✅ 有1个 | - | 足以作为模板 |
| 调用链图谱 | ✅ 有完整 | - | 核心输入 |
| 依赖图谱 | ✅ 有 | - | 确定import路径 |

**结论：当前信息基本足够实现Phase 1-3的MVP。**

核心原因：
1. 需求文档已经包含了生成代码所需的全部参数（权重路径、环境变量、服务拉起命令、测试参数、校验标准）
2. 调用链图谱暴露了完整的基类方法调用序列和参数传递方式
3. 用例样例提供了代码级的模板

**唯一的缺口**是 `aisbench_test` 方法的完整参数签名——但从已有用例的调用方式可以推断：

```python
# 从调用链样例反推的参数签名：
aisbench_test(
    ais_bench_path,          # 工具路径
    api_type,                # "vllm_api_general_chat"
    dataset,                 # "cevaLchat_prompt" / "gsm8k_gen_0_shot_cot_chat_prompt"
    path=ckpt_path,          # 模型权重路径
    model=ckpt_path,         # 模型名
    host_ip=vllm_ip,         # 服务IP
    host_port=vllm_port,     # 服务端口
    max_out_len=4096,        # 最大输出长度
    batch_size=256,          # 批次大小
    cycle_time=500           # 超时时间
)
```

---

## 五、基于你的真实需求，生成的目标代码

以下是你的需求文档应该生成的测试用例代码（手工推导，用于验证方案可行性）：

```python
import importlib
from common.config.config import CLUSTER_CONFIG_NEW, VLLM_BENCHMARK_TOOL_PATH
from common.ms_aw.network.net.deepseek import Deepseek


# net_config.py 补充项:
# ds_r1_model_path = "/home/workspace/large_model_ckpt_new/deepseek_r1_bf16_safetensor/"


class Test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003(Deepseek):
    """
    deepseek_r1网络，671b，910b3环境32p，bf16权重，vllm_mindspore服务化推理，ceval精度验证
    """

    def setup(self, case_name=None):
        case_name = "test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003"
        if not super(Test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003, self).setup(case_name):
            return False

        self.deploy_cluster_env()

        self.init_success_flg = True
        self.ms_log.info("The case setup success")
        return self.init_success_flg

    @pytest.mark.level1
    @pytest.mark.timeout(14400)
    @pytest.mark.env_Network_Ascend_Arm_32p
    @pytest.mark.env_Network_Ascend_X86_32p
    def test_run(self):
        """
        test_run: ceval精度验证，执行两次ceval测试
        """
        assert self.init_success_flg
        self.ms_log.info("The case test is running")
        self.perf_acc_flag = True

        # 1. 集群IP处理
        self.cluster_ip_process()

        # 2. 检查vllm服务状态
        self.vllm_server_check()

        # 3. 获取vllm服务IP和端口
        vllm_ip, vllm_port = self.get_vllm_log_ip_port(f"{self.model_path}/vllm_server.log")

        # 4. 第一次ceval测试
        self.ms_log.step("4. 执行第一次ceval测试")
        acc_first = self.aisbench_test(
            self.ais_bench_path, "vllm_api_general_chat", "cevaLchat_prompt",
            path=self.ds_r1_model_path, model=self.ds_r1_model_path,
            host_ip=vllm_ip, host_port=vllm_port,
            max_out_len=4096, batch_size=256, cycle_time=500
        )

        # 5. 第二次ceval测试
        self.ms_log.step("5. 执行第二次ceval测试")
        acc_second = self.aisbench_test(
            self.ais_bench_path, "vllm_api_general_chat", "cevaLchat_prompt",
            path=self.ds_r1_model_path, model=self.ds_r1_model_path,
            host_ip=vllm_ip, host_port=vllm_port,
            max_out_len=4096, batch_size=256, cycle_time=500
        )

        # 6. 校验两次ceval得分差不超过1
        self.ms_log.step("6. 校验两次ceval测试一致性")
        if acc_first is not None and acc_second is not None:
            score_diff = abs(float(acc_first) - float(acc_second))
            self.ms_log.info(f"第一次ceval得分: {acc_first}, 第二次ceval得分: {acc_second}, 差值: {score_diff}")
            if score_diff > 1:
                self.ms_log.error(f"两次ceval得分差 {score_diff} 超过阈值 1")
                self.perf_acc_flag = False
        else:
            self.ms_log.error("ceval测试结果获取失败")
            self.perf_acc_flag = False

        # 7. 验证日志文件是否有error日志
        if not self.check_err_info_in_log(
            [f"{self.model_path}/vllm_server.log"],
            "ERROR|CRITICAL|Traceback|RuntimeError|WARNING",
            ignore_cw="Failed to connect to the meta server|"
                      "Failed to register and try to reconnect to the meta server|"
                      "Failed to connect to the tcp server", log_card_type=32
        ):
            self.perf_acc_flag = False

        if not self.perf_acc_flag:
            self.ms_log.error("Something wrong with infer, pls check error log.")
            assert False

        self.ms_log.info("The case test is success")

    def teardown(self):
        self.ms_log.info("The case teardown is running")
        super(Test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003, self).teardown()
        return True
```

**生成要点说明：**

| 生成逻辑 | 来源 |
|----------|------|
| 类名 | 直接从需求文档的"用例名"字段 |
| 继承 `Deepseek` | network=deepseek → 匹配依赖图谱中的 `common.ms_aw.network.net.deepseek` |
| import路径 | 从V2依赖图谱匹配 `det_ceval` 类型用例的import模式 |
| setup方法 | 调用链匹配 `det_ceval` → `super().setup + deploy_cluster_env` |
| test_run的调用链 | V2.2中 `_0001` 用例的 `cluster_ip_process → vllm_server_check → get_vllm_log_ip_port → aisbench_test × 2` |
| 执行两次aisbench | 需求文档明确要求"执行两次ceval测试" |
| 自定义校验逻辑 | 需求文档要求"两次等分相差不能超过1" → 生成差值比较代码 |
| 环境变量/服务命令 | 从需求文档直接提取（但此用例是det类型，服务已预部署） |
| pytest装饰器 | 卡数32p → `@pytest.mark.env_Network_Ascend_Arm_32p` |

---

## 六、关键技术决策

### 1. 不需要CFG，改为"调用链模板匹配"

你的测试类型是有限的组合空间：

```
测试类型 × 推理框架 = 调用链模板
─────────────────────────────────
acc × vllm     → 模板A (start_server → get_benchmark_acc → check_benchmark_acc)
acc × mindie   → 模板B (set_mindieserver_prepare → run_infer_mindie → check_benchmark_acc)
perf × vllm    → 模板C (start_server → vllm_benchmark_perf_test → vllm_benchmark_perf_check)
perf × mindie  → 模板D (set_mindieserver → run_infer_mindie → check_infer_performence)
func × vllm    → 模板E (start_server → vllm_server_warm_up → ds_func_perf_test)
det × vllm     → 模板F (vllm_server_check → aisbench_test → check_err_info_in_log)
```

这些模板可以从V2.2调用链中自动提取。新用例只需匹配到正确的模板，然后填充参数。

### 2. 代码生成策略：LLM + 模板 + RAG

不是让LLM从零生成代码，而是：
- **模板层**：调用链模板定义了setup/test_run/teardown的方法调用骨架
- **参数层**：需求文档提供具体参数（路径、命令、规格）
- **RAG层**：相似历史用例提供代码风格和细节参考
- **LLM层**：处理需求文档中的自然语言描述（如"执行两次ceval测试" → 循环逻辑）

### 3. net_config.py处理

需求文档中已包含路径信息（`self.ds_r1_model_path = "/home/workspace/..."`），生成时只需要：
- 提取需求中的变量声明
- 输出为net_config.py的补充项
- 用例文件中通过import引用

---

## 七、下一步行动

**立即可做：**

1. **验证Phase 3代码生成** — 用你提供的真实需求文档 + 已有用例样例作为few-shot，直接调用LLM生成目标测试代码，你人工审核看效果

2. **提取调用链模板库** — 从V2.2中自动提取所有 (测试类型 × 框架) 的调用链模式，建立模板映射表

3. **设计需求解析Prompt** — 编写将你的半结构化需求文档转为结构化JSON的Prompt

需要你决定：先推哪个？
