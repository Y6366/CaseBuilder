# 测试场景模式库

## 模式1: VLLM性能测试 (vllm_perf)
**触发关键词:** 性能、perf、吞吐量、throughput、tokens/s
**流程:**
1. setup: set_vllm_server_prepare + 可选环境变量
2. test_run:
   - 启动vllm服务 (vllm_server_start)
   - 获取IP端口 (get_vllm_log_ip_port)
   - 循环不同batch_size执行性能测试 (vllm_benchmark_perf_test)
   - 校验性能达标 (vllm_benchmark_perf_check)
   - 日志错误检查 (check_err_info_in_log)
3. teardown: stop_vllm_server

## 模式2: VLLM精度测试 (vllm_acc)
**触发关键词:** 精度、accuracy、acc、gsm8k、ceval
**流程:**
1. setup: set_vllm_server_prepare + 可选copy_model
2. test_run:
   - 启动vllm服务
   - 获取IP端口
   - 执行精度测试 (aisbench_test)
   - 校验精度达标 (check_benchmark_acc)
   - 日志错误检查
3. teardown: stop_vllm_server

## 模式3: VLLM一致性测试 (vllm_det)
**触发关键词:** 一致性、det、deterministic、重复性
**流程:**
1. setup: set_vllm_server_prepare + 环境变量
2. test_run:
   - 启动vllm服务
   - 获取IP端口
   - 执行N次aisbench_test (run_count=N, log_suffix=[_run1, _run2, ...])
   - 校验一致性 (check_ceval_consistency)
3. teardown: stop_vllm_server

## 模式4: VLLM性能+精度测试 (vllm_perf_acc)
**触发关键词:** 性能精度、perf+acc、完整验证
**流程:**
1. setup: set_vllm_server_prepare
2. test_run:
   - 启动vllm服务
   - 获取IP端口
   - 执行性能测试（多个batch_size）
   - 校验性能
   - 执行精度测试
   - 校验精度
   - 日志错误检查
3. teardown: stop_vllm_server

## 模式5: MindIE精度测试 (mindie_acc)
**触发关键词:** mindie、mindie精度
**流程:**
1. setup: 基础setup + copy_model
2. test_run:
   - get_status_cmd
   - mindie_server_warm_up
   - process_check
   - get_benchmark_acc_or_speed
   - run_infer_mindie_cluster_shell
   - check_benchmark_acc
3. teardown: 基础teardown

## 模式6: 量化推理测试 (quantize_infer)
**触发关键词:** 量化、quantize、w4a8、w8a8、int8、gptq
**说明:** 量化测试在vllm启动命令中需要添加 --quantization 参数
**流程:** 基于上述模式，在启动命令中增加量化相关参数
