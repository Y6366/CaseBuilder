# View 3: 检索工具契约 (Tool & API Specs)

  

> 本文件用于向 Agent 暴露当前测试框架或解析工具自身的 API 调用规范。

  

## RecursiveRetriever (AST解析工具)

- **功能**: 用于在运行时动态读取工程上下文的沙盒工具。

- **暴露方法**:

  1. `analyze_file(file_path: str)` -> 返回指定文件的类与函数细节。

  2. `scan_directory(dir: str)` -> 返回指定目录内的结构。

  3. `get_call_chain(func_name: str)` -> 从 `call_graph` 提取目标函数的依赖。