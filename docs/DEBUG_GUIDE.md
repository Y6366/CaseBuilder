# CaseBuilder 调试指南

## 1. 日志系统

### 日志位置
- 运行日志: `logs/run_YYYYMMDD_HHMMSS.log`
- Demo日志: `logs/demo.log`

### 日志级别
```
INFO    — 正常流程（每个阶段的进入/退出）
WARNING — 非致命问题（未知方法、缺少上下文）
ERROR   — 致命问题（语法错误、文件读取失败）
```

### 查看日志
```bash
# 查看最近一次运行日志
ls -t logs/ | head -1 | xargs -I {} cat logs/{}

# 实时跟踪
tail -f logs/run_*.log

# 过滤错误
grep "ERROR" logs/run_*.log
```

## 2. 中间产物调试

每次运行会在 `output/.artifacts_YYYYMMDD_HHMMSS/` 下保存中间产物：

```
.artifacts_20260506_121600/
├── intent.json              # 意图识别结果
├── knowledge.json           # 知识检索结果
├── code_result.json         # 代码生成结果
├── review_report.json       # 质量校验报告
└── review_report_attempt_1.json  # 首次校验结果
```

### 检查意图识别
```bash
cat output/.artifacts_*/intent.json | python3 -m json.tool
```

### 检查知识检索
```bash
cat output/.artifacts_*/knowledge.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for m in data.get('method_details', []):
    print(f\"  {m['name']}: {m['definition'].get('desc', 'N/A')}\")"
```

### 检查校验报告
```bash
cat output/.artifacts_*/review_report.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Score: {data['score']}/100\")
for i in data.get('issues', []):
    print(f\"  [{i['severity']}] {i['message']}\")"
```

## 3. 分阶段调试

### 单独调试意图识别
```python
from agents.intent_agent import IntentAgent
agent = IntentAgent()
intent = agent.recognize("你的测试场景描述")
print(intent)
```

### 单独调试知识检索
```python
from agents.retrieval_agent import RetrievalAgent
agent = RetrievalAgent()
knowledge = agent.retrieve(intent)  # 传入intent
print(knowledge.keys())
```

### 单独调试代码生成
```python
from agents.codegen_agent import CodeGenAgent
agent = CodeGenAgent()
result = agent.generate(intent, knowledge)
print(result['code'])
```

### 单独调试质量校验
```python
from agents.review_agent import ReviewAgent
agent = ReviewAgent()
report = agent.review(code_string, intent)
print(report['summary'])
for issue in report['issues']:
    print(f"  [{issue['severity']}] {issue['message']}")
```

## 4. 常见问题排查

### 问题：意图识别标签不准确
**排查:**
```python
agent = IntentAgent()
tags = agent._extract_tags("你的描述")
print(tags)
```
**解决:** 在 `_extract_tags` 的 `tag_patterns` 中添加新的关键词映射。

### 问题：方法调用校验误报
**排查:** 检查 `method_glossary.json` 是否包含该方法。
**解决:** 在词典中添加缺失的方法定义。

### 问题：代码生成有语法错误
**排查:** 运行AST校验：
```python
import ast
ast.parse(generated_code)
```
**解决:** 检查 `CodeGenAgent._assemble_code` 的模板组装逻辑。

### 问题：上下文为空
**排查:**
1. 确认 `context_output/` 目录存在
2. 确认目录下有 V1/V2/V3 视图文件
3. 运行 `python3 tools/build_context.py /path/to/project`

**解决:** 先构建上下文再运行生成流程。

## 5. 性能分析

```bash
# 统计各阶段耗时
grep "耗时" logs/run_*.log

# 统计上下文分析量
cat context_output/SUMMARY.json | python3 -m json.tool
```
