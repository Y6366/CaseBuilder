"""
Web界面 — LLMCFG-TGen 可视化操作界面

基于论文中提到的"user-friendly web application"复现。
使用Flask实现，支持:
- 输入NL用例描述
- 可视化CFG
- 展示提取的测试路径
- 展示生成的测试用例
"""

from flask import Flask, render_template_string, request, jsonify
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.pipeline import LLMCFGTGenPipeline

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLMCFG-TGen: 用例→测试用例自动生成</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; padding: 20px; color: #2c3e50; }
        .card { background: white; border-radius: 8px; padding: 20px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        textarea { width: 100%; height: 200px; padding: 12px; border: 1px solid #ddd; border-radius: 6px; font-family: monospace; font-size: 14px; resize: vertical; }
        button { background: #3498db; color: white; border: none; padding: 12px 30px; border-radius: 6px; font-size: 16px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #2980b9; }
        button:disabled { background: #95a5a6; cursor: not-allowed; }
        .step { display: flex; align-items: center; margin: 10px 0; }
        .step-num { background: #3498db; color: white; width: 30px; height: 30px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 10px; font-weight: bold; flex-shrink: 0; }
        .step-num.done { background: #27ae60; }
        .step-num.active { background: #f39c12; animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .cfg-vis { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 6px; font-family: monospace; white-space: pre; overflow-x: auto; }
        .path { background: #ecf0f1; padding: 10px; margin: 5px 0; border-radius: 4px; border-left: 3px solid #3498db; }
        .tc-card { border: 1px solid #ddd; border-radius: 6px; margin: 10px 0; overflow: hidden; }
        .tc-header { background: #3498db; color: white; padding: 10px 15px; }
        .tc-body { padding: 15px; }
        .tc-body table { width: 100%; border-collapse: collapse; }
        .tc-body th, .tc-body td { padding: 8px; border: 1px solid #ddd; text-align: left; }
        .tc-body th { background: #f8f9fa; }
        .loading { display: none; text-align: center; padding: 20px; }
        .loading.active { display: block; }
        .example-btn { background: #e67e22; margin-left: 10px; }
        .example-btn:hover { background: #d35400; }
        #result { display: none; }
        .summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 15px 0; }
        .summary-item { text-align: center; padding: 15px; background: #ecf0f1; border-radius: 8px; }
        .summary-item .num { font-size: 2em; font-weight: bold; color: #2c3e50; }
        .summary-item .label { color: #7f8c8d; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔬 LLMCFG-TGen</h1>
        <p style="text-align:center; color:#7f8c8d; margin-bottom:20px;">
            从自然语言用例描述自动生成测试用例 — 基于LLM生成控制流图
        </p>

        <div class="card">
            <h3>📝 输入用例描述</h3>
            <p style="color:#7f8c8d; margin: 10px 0;">支持任意格式的自然语言用例描述（含主流程、备选流程、异常流程）</p>
            <button class="example-btn" onclick="loadExample('uc001')">📚 示例1: 图书借阅</button>
            <button class="example-btn" onclick="loadExample('uc002')">🏧 示例2: ATM取款</button>
            <button class="example-btn" onclick="loadExample('uc003')">🛒 示例3: 在线下单</button>
            <br><br>
            <textarea id="useCase" placeholder="在此输入用例描述...&#10;&#10;例如:&#10;Use Case Name: Login&#10;Main Flow:&#10;1. User enters username&#10;2. User enters password&#10;3. System validates credentials [E1]&#10;4. System displays dashboard&#10;&#10;Exception Flow:&#10;[E1] Invalid credentials: System shows error message"></textarea>
            <br>
            <button id="generateBtn" onclick="generate()">🚀 生成测试用例</button>
        </div>

        <div id="loading" class="loading">
            <div class="step"><div class="step-num active" id="step1">1</div><span>CFG Generation — 生成控制流图...</span></div>
            <div class="step"><div class="step-num" id="step2">2</div><span>Test-Path Extraction — 枚举测试路径...</span></div>
            <div class="step"><div class="step-num" id="step3">3</div><span>Test Case Creation — 创建测试用例...</span></div>
        </div>

        <div id="result">
            <div class="summary">
                <div class="summary-item"><div class="num" id="nodeCount">-</div><div class="label">CFG节点数</div></div>
                <div class="summary-item"><div class="num" id="pathCount">-</div><div class="label">测试路径数</div></div>
                <div class="summary-item"><div class="num" id="tcCount">-</div><div class="label">测试用例数</div></div>
            </div>

            <div class="card">
                <h3>📊 控制流图 (CFG)</h3>
                <div id="cfgDisplay" class="cfg-vis"></div>
            </div>

            <div class="card">
                <h3>🔀 测试路径</h3>
                <div id="pathsDisplay"></div>
            </div>

            <div class="card">
                <h3>✅ 生成的测试用例</h3>
                <div id="testCasesDisplay"></div>
            </div>
        </div>
    </div>

    <script>
    const examples = {};
    async function loadExample(id) {
        const resp = await fetch(`/example/${id}`);
        const data = await resp.json();
        document.getElementById('useCase').value = data.use_case;
    }

    async function generate() {
        const useCase = document.getElementById('useCase').value.trim();
        if (!useCase) { alert('请输入用例描述'); return; }

        document.getElementById('generateBtn').disabled = true;
        document.getElementById('loading').classList.add('active');
        document.getElementById('result').style.display = 'none';

        try {
            const resp = await fetch('/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({use_case: useCase})
            });
            const result = await resp.json();

            document.getElementById('step1').className = 'step-num done';
            document.getElementById('step2').className = 'step-num done';
            document.getElementById('step3').className = 'step-num done';

            // Summary
            document.getElementById('nodeCount').textContent = result.summary.cfg_nodes;
            document.getElementById('pathCount').textContent = result.summary.total_paths;
            document.getElementById('tcCount').textContent = result.summary.total_test_cases;

            // CFG
            document.getElementById('cfgDisplay').textContent = JSON.stringify(result.cfg, null, 2);

            // Paths
            let pathsHtml = '';
            result.test_paths.forEach((path, i) => {
                pathsHtml += `<div class="path"><strong>路径 ${i+1}:</strong> ${path.join(' → ')}</div>`;
            });
            document.getElementById('pathsDisplay').innerHTML = pathsHtml;

            // Test Cases
            let tcHtml = '';
            result.test_cases.forEach(tc => {
                let stepsHtml = '<table><tr><th>步骤</th><th>输入/操作</th><th>预期结果</th></tr>';
                tc.Test.forEach(step => {
                    stepsHtml += `<tr><td>${step.Step}</td><td>${step.Input}</td><td>${step.Result}</td></tr>`;
                });
                stepsHtml += '</table>';
                tcHtml += `<div class="tc-card">
                    <div class="tc-header"><strong>${tc.id}</strong>: ${tc.Description}</div>
                    <div class="tc-body">
                        <p><strong>前置条件:</strong> ${tc.Precondition}</p>
                        ${stepsHtml}
                    </div>
                </div>`;
            });
            document.getElementById('testCasesDisplay').innerHTML = tcHtml;

            document.getElementById('result').style.display = 'block';
        } catch (e) {
            alert('生成失败: ' + e.message);
        } finally {
            document.getElementById('loading').classList.remove('active');
            document.getElementById('generateBtn').disabled = false;
        }
    }
    </script>
</body>
</html>
"""

pipeline = None


def get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = LLMCFGTGenPipeline()
    return pipeline


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/example/<example_id>")
def example(example_id):
    example_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "examples"
    )
    filepath = os.path.join(example_dir, f"{example_id}_*.json")
    import glob
    files = glob.glob(filepath)
    if not files:
        return jsonify({"error": "Example not found"}), 404
    with open(files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    use_case = data.get("use_case", "")
    if not use_case:
        return jsonify({"error": "Empty use case"}), 400

    try:
        result = get_pipeline().run(use_case)
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)
