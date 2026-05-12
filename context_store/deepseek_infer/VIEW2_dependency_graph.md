# View 2.1: 代码依赖图谱 (Dependency Graph)

  

## 1. 核心导入映射 (Imports)

  

### `cases\02network\02nlp\deepseek\r1\infer\net_config.py` 依赖于:

- `from easydict import EasyDict`

  

### `cases\02network\02nlp\deepseek\r1\infer\test_ms_deepseekr1_671b_mindie_infer_acc_bf16_910b3_32p_0001.py` 依赖于:

- `import importlib`

- `from common.config.config import MINDFORMERS_ROOT, SHARE_CKPT_PATH`

- `from common.config.config import DATA_ROOT`

- `from common.ms_aw.network.net.deepseek import Deepseek`

- `from common.utils.ssh_cmd_helper import SSHHelper`

  

### `cases\02network\02nlp\deepseek\r1\infer\test_ms_deepseekr1_671b_mindie_infer_acc_int8_910b3_16p_0001.py` 依赖于:

- `import importlib`

- `from common.config.config import MINDFORMERS_ROOT, SHARE_CKPT_PATH`

- `from common.config.config import DATA_ROOT`

- `from common.ms_aw.network.net.deepseek import Deepseek`

- `from common.utils.ssh_cmd_helper import SSHHelper`

  

### `cases\02network\02nlp\deepseek\r1\infer\test_ms_deepseekr1_671b_mindie_infer_perf_int8_910b3_16p_0001.py` 依赖于:

- `import importlib`

- `from common.config.config import MINDFORMERS_ROOT, BENCHMARK_PERFORMANCE_TOOL_PATH`

- `from common.config.config import DATA_ROOT, SHARE_CKPT_PATH`

- `from common.ms_aw.network.net.deepseek import Deepseek`

- `from common.utils.ssh_cmd_helper import SSHHelper`

  

### `cases\02network\02nlp\deepseek\r1\infer\test_ms_deepseekr1_671b_vllm_infer_det_ceval_v1_tp32_bf16_910b3_32p_0001.py` 依赖于:

- `from common.config.config import CLUSTER_CONFIG_NEW, VLLM_BENCHMARK_TOOL_PATH`

- `from common.ms_aw.network.net.deepseek import Deepseek`

- `from common.ms_aw.network.net.qwen import Qwen`

  

### `cases\02network\02nlp\deepseek\r1\infer\test_ms_deepseekr1_671b_vllm_infer_det_v1_tp32_bf16_910b3_32p_0001.py` 依赖于:

- `from common.config.config import CLUSTER_CONFIG_NEW, VLLM_BENCHMARK_TOOL_PATH`

- `from common.ms_aw.network.net.deepseek import Deepseek`

- `from common.ms_aw.network.net.qwen import Qwen`

  

### `cases\02network\02nlp\deepseek\r1\infer\test_ms_deepseekr1_671b_vllm_infer_gptq_w4a16_910b3_8p_0001.py` 依赖于:

- `from common.config.config import GOLDEN_STICK_ROOT`

- `from common.ms_aw.network.net.deepseek import Deepseek`

  

### `cases\02network\02nlp\deepseek\r1\infer\test_ms_deepseekr1_671b_vllm_infer_osl_w8a8_910b3_16p_0001.py` 依赖于:

- `from common.config.config import CLUSTER_CONFIG_NEW`

- `from common.config.config import DATA_ROOT`

- `from common.config.config import GOLDEN_STICK_ROOT`

- `from common.ms_aw.network.net.deepseek import Deepseek`

  

### `cases\02network\02nlp\deepseek\r1\infer\test_ms_deepseekr1_671b_vllm_infer_quant_gptq_w4a16_910b3_8p_0001.py` 依赖于:

- `from common.config.config import GOLDEN_STICK_ROOT`

- `from common.ms_aw.network.net.deepseek import Deepseek`