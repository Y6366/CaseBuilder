# 用例编码规范

## 1. 文件命名规范
- 格式：`test_ms_{network}_{size}_{framework}_{task}_{version}_{quantize}_{chip}_{np}_{seq}.py`
- 示例：`test_ms_deepseekr1_671b_vllm_infer_v1_w4a8_910b3_8p_0001.py`
- 各字段含义：
  - network: 网络名称（deepseekr1/deepseekv3/qwen等）
  - size: 模型规格（671b/72b等）
  - framework: 推理框架（vllm/mindie）
  - task: 任务类型（infer/train）
  - version: 版本号（v0/v1）
  - quantize: 量化方式（bf16/int8/w4a8/w8a8/gptq_w4a16）
  - chip: 芯片型号（910b3）
  - np: 卡数（8p/16p/32p）
  - seq: 序号（0001起）

## 2. 类命名规范
- 格式：与文件名相同，使用PascalCase：`Test_ms_deepseekr1_671b_vllm_infer_v1_w4a8_910b3_8p_0001`
- 类继承：必须继承对应的网络基类（如 `Deepseek`）
- 类docstring：一行描述，包含网络名称、模型规格、环境、权重格式、推理框架、验证类型

## 3. import规范
- 标准库在前，第三方库在中，项目内模块在后
- 必须import对应的网络基类
- 常用import：
  ```python
  import pytest
  from common.ms_aw.network.net.deepseek import Deepseek
  from common.config.config import XXX_ROOT, XXX_PATH
  ```

## 4. 结构规范
- 每个用例类必须包含三个方法：`setup`, `test_run`, `teardown`
- setup: 调用父类setup + 初始化case_name + 环境准备
- test_run: 核心测试逻辑，包含步骤编号注释
- teardown: 调用父类teardown，清理资源

## 5. setup方法模板
```python
def setup(self, case_name=None):
    case_name = "{完整类名}"
    if not super({类名}, self).setup(case_name):
        return False
    # 环境准备逻辑
    self.init_success_flg = True
    self.ms_log.info("The case setup success")
    return self.init_success_flg
```

## 6. test_run方法模板
```python
@pytest.mark.level1
@pytest.mark.timeout(14400)
@pytest.mark.env_Network_Ascend_Arm_{np}
def test_run(self):
    """test_run"""
    assert self.init_success_flg
    self.ms_log.info("The case test is running")
    self.perf_acc_flag = True
    # 步骤带编号：self.ms_log.step("1.描述")
    # 最终断言
    if not self.perf_acc_flag:
        self.ms_log.error("Something wrong, pls check error log.")
        assert False
    self.ms_log.info("The case test is success")
```

## 7. teardown方法模板
```python
def teardown(self):
    self.ms_log.info("The case teardown is running")
    super({类名}, self).teardown()
    return True
```

## 8. 日志规范
- 使用 `self.ms_log.step("1.描述")` 标记步骤
- 使用 `self.ms_log.info()` 记录正常流程
- 使用 `self.ms_log.error()` 记录错误
- 失败时设置 `self.perf_acc_flag = False`

## 9. 断言规范
- 性能测试：`vllm_benchmark_perf_check(perf_stand=X, perf_error=0.95)`
- 精度测试：`check_benchmark_acc(accuracy=X, acc_stand=Y, acc_error=0.99)`
- 一致性测试：`check_ceval_consistency(threshold=1, metric="ceval_score", run_count=2)`
- 日志检查：`check_err_info_in_log(log_paths, error_pattern, ignore_cw=...)`

## 10. pytest装饰器规范
- `@pytest.mark.level1` — 用例级别
- `@pytest.mark.timeout(N)` — 超时时间（秒）
- `@pytest.mark.env_Network_Ascend_Arm_{np}` — ARM环境标记
- `@pytest.mark.env_Network_Ascend_X86_{np}` — X86环境标记
- np根据卡数填写：8p/16p/32p等
