"""
Prompt #1: 用例 → CFG 生成

基于论文 Figure 4 和 Algorithm 1 设计。
论文中的Prompt #1由五个组件组成:
1. Role Definition — 角色定义
2. Task Instructions — 任务指令
3. Algorithm 1 — CFG生成算法
4. Output Format — JSON输出格式
5. Input Use Case — 输入用例
"""

CFG_SYSTEM_PROMPT = """Act as a software engineer expert."""

CFG_USER_PROMPT_TEMPLATE = """Use the following algorithm to convert the below use case into a control flow graph, following below instructions:

### INSTRUCTION
1. Extract and generate nodes from the Main Flow, Alternative Flow, and Extension Flow of the use case.
2. Ensure all conditional branches and transitions are correctly represented, and avoid orphan nodes.
3. For every conditional statement (e.g., "if", "when", "provided that", "in case"), create separate edges for each outcome to preserve all logical paths.
4. Connect each alternative and extension step to its originating main flow step (e.g., "3a" to "S3") and ensure it rejoins the main flow if not otherwise stated.
5. Assign weights to all edges, starting from 1 and increasing sequentially, representing the control flow order.
6. Output the control flow graph in valid JSON format, strictly following the structure below.

### ALGORITHM (CFG Generation)
Input: Steps in main flow and other flows of use-case description
Output: CFG G = (S, E) with root R

1. Preprocess: Merge all steps into one ordered sequence
2. Let S = {S1, S2, ..., Sn} be the resulting ordered nodes
3. Set root R := S1; Initialize edge sequence E := ∅ and edge weight W := ∅
4. Add edge E1 := S1 → S2, set W(E1) := 1
5. for each step Si do
6.     if Si+1 contains a condition then
7.         add edge Ei := Si → Si+1         (for the true condition)
8.         add edge Ei+1 := Si → Si+2       (for the false condition)
9.         set W(Ei), W(Ei+1) := W(Ei-1) + 1
10.    else
11.        add edge Ei := Si → Si+1
12.        set W(Ei) := W(Ei-1) + 1
13.    end if
14. end for

### Output Format (JSON):
{
  "nodes": [
    {"id": "S1", "Statement": "Description of step 1"},
    {"id": "S2", "Statement": "Description of step 2"},
    {"id": "A1", "Statement": "Description of alternative step"},
    {"id": "E1", "Statement": "Description of exception step"}
  ],
  "edges": [
    {"from": "S1", "to": "S2", "weight": 1},
    {"from": "S2", "to": "S3", "condition": "optional condition text", "weight": 2},
    {"from": "S2", "to": "A1", "condition": "alternative condition", "weight": 2}
  ]
}

Now apply this to the following use case:

#### USE CASE
{use_case}"""

# Prompt #2: 测试路径 → 测试用例
TESTCASE_SYSTEM_PROMPT = """Act as a senior QA engineer expert in software testing."""

TESTCASE_USER_PROMPT_TEMPLATE = """Convert the following test execution path into a detailed, structured test case.

### INSTRUCTION
1. Generate a clear, descriptive test case title that summarizes what is being tested.
2. Identify appropriate preconditions based on the test path context.
3. Convert each step in the path into a test step with:
   - Step number
   - Input/Action description
   - Expected result
4. Ensure the test case is self-contained and readable.

### CONTEXT
Original Use Case:
{use_case}

### Test Execution Path:
{test_path}

### Output Format (JSON):
{{
  "id": "TC-XXX",
  "Description": "Clear description of what this test case verifies",
  "Precondition": "Required preconditions for this test",
  "Test": [
    {{"Step": "1", "Input": "Action to perform", "Result": "Expected outcome"}},
    {{"Step": "2", "Input": "Next action", "Result": "Expected outcome"}}
  ]
}}

Generate the test case in valid JSON format:"""
