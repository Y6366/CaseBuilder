import pytest
import importlib
from common.config.config import CLUSTER_CONFIG_NEW, VLLM_BENCHMARK_TOOL_PATH
from common.ms_aw.network.net.deepseek import Deepseek


class Test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003(Deepseek):
    """
    deepseek_r1网络，671b，bf16权重，910b3环境32p，vllm_mindspore服务化推理，
    det_ceval精度稳定性验证（两次ceval得分差值不超过1）
    """

    def setup(self, case_name=None):
        case_name = "test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003"
        if not super(Test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003, self).setup(case_name):
            return False

        self.ds_r1_model_path = "/home/workspace/large_model_ckpt_new/deepseek_r1_bf16_safetensor/"

        # 部署集群环境（det类型，服务由外部预部署）
        self.ms_log.step("部署集群环境")
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
        test_run
        """
        assert self.init_success_flg
        self.ms_log.info("The case test is running")
        self.perf_acc_flag = True

        # 1. 获取集群IP并检查服务状态
        self.ms_log.step("1. 获取集群IP并检查vllm服务状态")
        self.cluster_ip_process()
        self.vllm_server_check()

        vllm_ip, vllm_port = self.get_vllm_log_ip_port()

        # 2. 第一次ceval测试
        self.ms_log.step("2. 执行第一次ceval测试")
        acc_first = self.aisbench_test(
            self.ais_bench_path,
            "vllm_api_general_chat",
            "ceval_chat_prompt",
            path=self.ds_r1_model_path,
            model=self.ds_r1_model_path,
            host_ip=vllm_ip,
            host_port=vllm_port,
            max_out_len=4096,
            batch_size=256,
            cycle_time=500,
            log_suffix="_ceval_run1"
        )
        self.ms_log.info(f"第一次ceval测试得分: {acc_first}")

        # 3. 第二次ceval测试
        self.ms_log.step("3. 执行第二次ceval测试")
        acc_second = self.aisbench_test(
            self.ais_bench_path,
            "vllm_api_general_chat",
            "ceval_chat_prompt",
            path=self.ds_r1_model_path,
            model=self.ds_r1_model_path,
            host_ip=vllm_ip,
            host_port=vllm_port,
            max_out_len=4096,
            batch_size=256,
            cycle_time=500,
            log_suffix="_ceval_run2"
        )
        self.ms_log.info(f"第二次ceval测试得分: {acc_second}")

        # 4. 校验两次ceval得分差值不超过1
        self.ms_log.step("4. 校验两次ceval得分差值不超过1")
        if acc_first is not None and acc_second is not None:
            score_diff = abs(float(acc_first) - float(acc_second))
            self.ms_log.info(f"两次ceval得分差值: {score_diff}")
            if score_diff > 1:
                self.ms_log.error(
                    f"两次ceval得分差值({score_diff})超过阈值1, "
                    f"第一次得分: {acc_first}, 第二次得分: {acc_second}"
                )
                self.perf_acc_flag = False
        else:
            self.ms_log.error(
                f"ceval测试得分获取失败, 第一次: {acc_first}, 第二次: {acc_second}"
            )
            self.perf_acc_flag = False

        # 5. 验证日志文件是否有error日志
        self.ms_log.step("5. 验证日志文件是否有error日志")
        if not self.check_err_info_in_log(
            [f"{self.model_path}/vllm_server.log"],
            "ERROR|CRITICAL|Traceback|RuntimeError|WARNING",
            ignore_cw="Failed to connect to the meta server|"
                      "Failed to register and try to reconnect to the meta server|"
                      "Failed to connect to the tcp server",
            log_card_type=32
        ):
            self.perf_acc_flag = False

        # 6. 执行性能测试
        self.ms_log.step("6. 执行性能测试")
        self.vllm_benchmark_perf_test(
            ckpt_path=self.ds_r1_model_path,
            parallel_num=1,
            input_tokens=256,
            output_tokens=256,
            host_ip=vllm_ip,
            port=vllm_port
        )

        if not self.perf_acc_flag:
            self.ms_log.error("Something wrong with infer, pls check error log.")
            assert False

        self.ms_log.info("The case test is success")

    def teardown(self):
        self.ms_log.info("The case teardown is running")
        super(Test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0003, self).teardown()
        return True
