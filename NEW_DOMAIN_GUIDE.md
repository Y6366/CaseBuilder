# 新增领域指南

## 前提条件

新增领域前，需要准备该领域的"三大视图"上下文：

1. **VIEW1 模块签名** — 基类的方法/类签名列表
2. **VIEW2 依赖图谱** — import路径和跨模块依赖关系
3. **VIEW3 工具规范** — 可调用的工具API说明

另外需要：
- 2-3个该领域的完整测试用例样例（作为few-shot）
- 调用链模板（可从现有用例的执行链中提取）

## 步骤

### 1. 创建领域目录

```bash
mkdir -p context_store/{domain_name}/sample_cases
```

### 2. 放入上下文文件

```
context_store/{domain_name}/
├── VIEW1_module_signatures.md    # 模块签名
├── VIEW2_dependency_graph.md     # 依赖图谱
├── VIEW3_tool_specs.md           # 工具规范
└── sample_cases/                 # 2-3个样例用例
    ├── sample_001.py
    └── sample_002.py
```

### 3. 创建领域配置

复制模板：
```bash
cp config/domains/_TEMPLATE.yaml config/domains/{domain_name}.yaml
```

编辑配置文件，填入：
- `domain` 和 `description`
- `requirement_parsing` 中的字段映射和用例名规则
- `class_hierarchy` 中的继承体系和import路径
- `call_chain_templates` 中的调用链模板（**最重要**）
- `pytest_markers` 中的装饰器映射
- `method_specs` 中的基类方法说明

### 4. 提取调用链模板

调用链模板是核心——定义了每种测试类型的 setup/test_run/teardown 方法调用序列。

提取方法：
1. 收集该领域已有的5-10个用例
2. 按测试类型分组（acc/perf/func等）
3. 从代码中提取每个类型的标准调用序列
4. 参数化可变部分（如路径、规格值等用 `{PLACEHOLDER}` 标记）

### 5. 验证

```bash
python -m src.pipeline_v2 --domain {domain_name} --file data/examples/req_{domain_name}.json --output data/output/result.json
```

## 示例

参考 `config/domains/deepseek_infer.yaml` 作为完整示例。
