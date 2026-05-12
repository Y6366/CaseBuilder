#!/usr/bin/env python3
"""
多层上下文构建工具
封装 RecursiveRetriever，用于从测试工程源码构建多维上下文视图

使用方法:
  python3 tools/build_context.py /path/to/test_project --output context_output
  python3 tools/build_context.py /path/to/test_project --filter "cases/deepseek" "cases/qwen"
"""

import ast
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("CaseBuilder.BuildContext")


@dataclass
class FunctionInfo:
    name: str
    args: list[dict[str, str]]
    returns: Optional[str]
    calls: list[str]
    docstring: Optional[str]
    line_start: int
    line_end: int
    in_class: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class ClassInfo:
    name: str
    bases: list[str]
    base_info: str
    docstring: Optional[str]
    line_start: int
    line_end: int
    file_path: Optional[str] = None


@dataclass
class FileInfo:
    path: str
    relative_path: str
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[dict] = field(default_factory=list)
    global_vars: list[str] = field(default_factory=list)
    line_count: int = 0


class CallOrderVisitor(ast.NodeVisitor):
    """按顺序提取函数内调用，带过滤降噪"""

    IGNORE_PREFIXES = [
        "ms_log",
        "logger",
        "print",
        "pytest.",
        "time.sleep",
        "os.",
        "sys.",
        "self.execute",
        "self.dst_obj",
        "str",
        "int",
        "list",
        "dict",
        "range",
        "Path",
        "super",
        "len",
        "max",
        "min",
        "sum",
        "abs",
        "round",
        "sorted",
        "open",
        "type",
        "isinstance",
        "hasattr",
        "getattr",
        "setattr",
    ]
    IGNORE_SUFFIXES = [
        ".items",
        ".get",
        ".append",
        ".extend",
        ".keys",
        ".values",
        ".format",
        ".strip",
        ".split",
        ".join",
        ".replace",
        ".lower",
        ".upper",
        ".encode",
        ".decode",
        ".update",
        ".pop",
        ".sort",
    ]

    def __init__(self, unparser):
        self.calls = []
        self.unparse = unparser

    def visit_Call(self, node):
        call_name = None
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_name = self.unparse(node.func)

        if call_name:
            # 过滤噪声
            if (
                "'" in call_name
                or '"' in call_name
                or any(call_name.startswith(p) for p in self.IGNORE_PREFIXES)
                or any(call_name.endswith(s) for s in self.IGNORE_SUFFIXES)
            ):
                pass
            else:
                self.calls.append(call_name)

        self.generic_visit(node)


class RecursiveRetriever:
    """
    递归检索器 - AST解析测试工程源码，构建多维知识图谱
    """

    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.files: dict[str, FileInfo] = {}
        self.call_graph: dict[str, list[str]] = defaultdict(list)
        self.class_hierarchy: dict[str, list[str]] = defaultdict(list)
        self.import_map: dict[str, list[str]] = defaultdict(list)
        self.method_source: dict[str, str] = {}

    def scan_directory(self, directory: Path, pattern: str = "*.py", max_depth: int = 10) -> list[Path]:
        """递归扫描目录"""
        matched_files = []
        try:
            for item in directory.iterdir():
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue
                if item.is_file() and item.match(pattern):
                    matched_files.append(item)
                elif item.is_dir() and max_depth > 0:
                    matched_files.extend(self.scan_directory(item, pattern, max_depth - 1))
        except PermissionError:
            logger.warning(f"无法访问目录 {directory}")
        return matched_files

    def analyze_file(self, file_path: Path) -> Optional[FileInfo]:
        """解析单个Python文件"""
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            tree = ast.parse(content)

            file_info = FileInfo(
                path=str(file_path),
                relative_path=file_path.relative_to(self.root_path).as_posix(),
                line_count=len(content.splitlines()),
            )

            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        file_info.imports.append({"type": "import", "module": alias.name, "alias": alias.asname})

                elif isinstance(node, ast.ImportFrom):
                    module_name = node.module if node.module else ""
                    if node.level > 0:
                        module_name = "." * node.level + module_name
                    file_info.imports.append(
                        {
                            "type": "from_import",
                            "module": module_name,
                            "names": [(alias.name, alias.asname) for alias in node.names],
                        }
                    )

                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            file_info.global_vars.append(target.id)

                elif isinstance(node, ast.ClassDef):
                    bases = [self._unparse(b) for b in node.bases]
                    base_info = " -> 继承自: " + ", ".join(bases) if bases else ""
                    docstring = ast.get_docstring(node)

                    class_info = ClassInfo(
                        name=node.name,
                        bases=bases,
                        base_info=base_info,
                        docstring=docstring,
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        file_path=str(file_path),
                    )
                    file_info.classes.append(class_info)
                    self.class_hierarchy[node.name] = bases

                    for child in node.body:
                        if isinstance(child, ast.FunctionDef):
                            func_info = self._analyze_function(child, node.name, str(file_path))
                            file_info.functions.append(func_info)
                            self.call_graph[f"{node.name}.{func_info.name}"] = func_info.calls

                elif isinstance(node, ast.FunctionDef):
                    func_info = self._analyze_function(node, None, str(file_path))
                    file_info.functions.append(func_info)
                    self.call_graph[func_info.name] = func_info.calls

            return file_info

        except Exception as e:
            logger.error(f"分析文件 {file_path} 失败: {e}")
            return None

    def _analyze_function(self, node, current_class, file_path):
        """解析函数节点"""
        args_info = []
        defaults_offset = len(node.args.args) - len(node.args.defaults)

        for i, arg in enumerate(node.args.args):
            arg_info = {"name": arg.arg}
            if hasattr(arg, "annotation") and arg.annotation:
                arg_info["annotation"] = self._unparse(arg.annotation)
            if i >= defaults_offset:
                default_node = node.args.defaults[i - defaults_offset]
                arg_info["default"] = self._unparse(default_node)
            args_info.append(arg_info)

        returns_info = self._unparse(node.returns) if node.returns else None

        visitor = CallOrderVisitor(self._unparse)
        visitor.visit(node)

        docstring = ast.get_docstring(node)

        func_info = FunctionInfo(
            name=node.name,
            args=args_info,
            returns=returns_info,
            calls=visitor.calls,
            docstring=docstring,
            line_start=node.lineno,
            line_end=getattr(node, "end_lineno", node.lineno),
            in_class=current_class,
            file_path=file_path,
        )

        if current_class:
            self.method_source[f"{current_class}.{node.name}"] = file_path
        else:
            self.method_source[node.name] = file_path

        return func_info

    def _unparse(self, node) -> str:
        """安全的AST反解析"""
        if node is None:
            return ""
        if hasattr(ast, "unparse"):
            try:
                return ast.unparse(node).replace("\n", " ")
            except Exception:
                pass
        # 回退方案
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Attribute):
            return self._unparse(node.value) + "." + node.attr
        else:
            return type(node).__name__

    def analyze_project(self, directories=None, case_filter=None):
        """分析整个项目"""
        if directories is None:
            directories = ["cases", "common", "common/ms_aw/network"]

        for directory in directories:
            dir_path = self.root_path / directory
            if not dir_path.exists():
                logger.warning(f"目录不存在: {dir_path}")
                continue

            files = self.scan_directory(dir_path)

            if "cases" in directory and case_filter:
                normalized_filters = [c.replace("\\", "/") for c in case_filter]
                files = [f for f in files if any(cf in f.as_posix() for cf in normalized_filters)]

            for file_path in files:
                file_info = self.analyze_file(file_path)
                if file_info:
                    self.files[file_info.path] = file_info

        return {
            "project_root": str(self.root_path),
            "total_files": len(self.files),
            "total_functions": len(self.call_graph),
            "total_classes": len(self.class_hierarchy),
        }


def generate_layered_context_maps(retriever, output_dir="context_output"):
    """生成多维视图文件"""
    output_path = Path(output_dir).resolve()
    output_path.mkdir(exist_ok=True)
    logger.info(f"生成上下文映射文件到: {output_path}")

    # ───── V1_REPO_SKELETON ─────
    v1_parts = ["# View 1.1: 仓库骨架 (Repo Skeleton)\n", f"**项目根目录**: `{retriever.root_path}`\n"]
    dir_tree = defaultdict(list)
    for _, fi in retriever.files.items():
        rel_dir = str(Path(fi.relative_path).parent)
        dir_tree[rel_dir].append(Path(fi.relative_path).name)

    for rd in sorted(dir_tree):
        v1_parts.append(f"\n#### `/{rd}`")
        for fn in sorted(dir_tree[rd]):
            v1_parts.append(f"- {fn}")

    (output_path / "V1_REPO_SKELETON.md").write_text("\n".join(v1_parts), encoding="utf-8")
    logger.info("  ✓ V1_REPO_SKELETON.md")

    # ───── V1_MODULE_SIGNATURES ─────
    v1_sig = ["# View 1.2: 模块签名 (Module Signatures)\n"]
    for _, fi in sorted(retriever.files.items(), key=lambda x: x[1].relative_path):
        v1_sig.extend(
            [
                f"\n## 文件: `{fi.relative_path}`",
                f"- 概况: {fi.line_count} 行 | {len(fi.classes)} 类 | {len(fi.functions)} 函数",
            ]
        )

        if fi.global_vars:
            v1_sig.append("\n### 导出的全局配置 (Global Configs)")
            for gv in fi.global_vars:
                v1_sig.append(f"- `{gv}`")

        if fi.classes:
            v1_sig.append("\n### 暴露的类 (Classes)")
            for cls in fi.classes:
                v1_sig.append(f"- **{cls.name}** `{cls.base_info}`")
                if cls.docstring:
                    v1_sig.append(f"  > {cls.docstring.split(chr(10))[0]}")

        if fi.functions:
            v1_sig.append("\n### 暴露的工具方法 (Utility Methods)")
            for func in fi.functions:
                scope = f" [{func.in_class}]" if func.in_class else ""
                sig_args = ", ".join(a["name"] for a in func.args[:3])
                v1_sig.append(f"- `{func.name}({sig_args}...)`{scope}")
                if func.docstring:
                    v1_sig.append(f"  > {func.docstring.split(chr(10))[0]}")

    (output_path / "V1_MODULE_SIGNATURES.md").write_text("\n".join(v1_sig), encoding="utf-8")
    logger.info("  ✓ V1_MODULE_SIGNATURES.md")

    # ───── V2_DEPENDENCY_GRAPH ─────
    v2_dep = ["# View 2.1: 代码依赖图谱 (Dependency Graph)\n"]
    v2_dep.append("\n## 1. 核心导入映射 (Imports)\n")

    for _, fi in sorted(retriever.files.items(), key=lambda x: x[1].relative_path):
        if fi.imports:
            v2_dep.append(f"\n### `{fi.relative_path}` 依赖于:")
            for imp in fi.imports[:10]:
                if imp["type"] == "from_import":
                    names = ", ".join([n for n, _ in imp["names"]])
                    v2_dep.append(f"- `from {imp['module']} import {names}`")
                else:
                    v2_dep.append(f"- `import {imp['module']}`")

    v2_dep.append("\n## 2. 类继承树\n")
    for cls, bases in sorted(retriever.class_hierarchy.items()):
        if bases:
            v2_dep.append(f"- `{cls}` -> " + ", ".join(bases))

    v2_dep.append("\n## 3. 方法溯源\n")
    for method, source in sorted(retriever.method_source.items()):
        rel = Path(source).relative_to(retriever.root_path).as_posix()
        v2_dep.append(f"- `{method}` 实现在 -> `{rel}`")

    (output_path / "V2_DEPENDENCY_GRAPH.md").write_text("\n".join(v2_dep), encoding="utf-8")
    logger.info("  ✓ V2_DEPENDENCY_GRAPH.md")

    # ───── V2_CALL_TRACE ─────
    v2_trace = ["# View 2.2: 测试执行调用链 (Execution Trace)\n"]
    target_phases = ["setup", "teardown"]

    for fp, fi in retriever.files.items():
        if "test_" not in fp:
            continue

        v2_trace.append(f"\n### 来源文件: `{fi.relative_path}`\n")

        for func in fi.functions:
            if func.name in target_phases or "test" in func.name.lower():
                v2_trace.append(f"- **用例入口**: `{func.name}`")
                v2_trace.append("  - **内部调用图**:")
                for call in func.calls:
                    src = retriever.method_source.get(call)
                    if src:
                        rel = Path(src).relative_to(retriever.root_path).as_posix()
                        v2_trace.append(f"    -> `self.{call}` ({rel})")
                    else:
                        v2_trace.append(f"    -> `self.{call}`")

    (output_path / "V2_CALL_TRACE.md").write_text("\n".join(v2_trace), encoding="utf-8")
    logger.info("  ✓ V2_CALL_TRACE.md")

    # ───── V3_TOOL_SPECS ─────
    v3 = """# View 3: 检索工具契约 (Tool & API Specs)

> 本文件用于向 Agent 暴露当前测试框架或解析工具自身的 API 调用规范。

## RecursiveRetriever (AST解析工具)
- **功能**: 用于在运行时动态读取工程上下文的沙盒工具。
- **暴露方法**:
  1. `analyze_file(file_path: str)` -> 返回指定文件的类与函数细节。
  2. `scan_directory(dir: str)` -> 返回指定目录内的结构。
  3. `get_call_chain(func_name: str)` -> 从 `call_graph` 提取目标函数的依赖。
"""
    (output_path / "V3_TOOL_SPECS.md").write_text(v3, encoding="utf-8")
    logger.info("  ✓ V3_TOOL_SPECS.md")

    # ───── SUMMARY ─────
    summary = {
        "project_root": str(retriever.root_path),
        "metrics": {
            "total_files_analyzed": len(retriever.files),
            "total_functions_traced": len(retriever.call_graph),
            "total_classes_found": len(retriever.class_hierarchy),
        },
    }
    (output_path / "SUMMARY.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("  ✓ SUMMARY.json")

    return output_path


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="构建多层上下文映射 - 从测试工程源码生成多维知识视图")
    parser.add_argument("project_root", help="测试工程根目录路径")
    parser.add_argument("--output", "-o", default="context_output", help="输出目录 (默认: context_output)")
    parser.add_argument("--filter", "-f", nargs="*", default=None, help="用例路径过滤器 (如: cases/deepseek)")
    parser.add_argument("--dirs", nargs="*", default=None, help="要扫描的目录列表 (默认: cases, common)")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    if not Path(args.project_root).exists():
        logger.error(f"目录不存在: {args.project_root}")
        sys.exit(1)

    logger.info(f"分析项目: {args.project_root}")
    retriever = RecursiveRetriever(args.project_root)

    dirs = args.dirs or ["cases", "common", "common/ms_aw/network"]
    case_filter = args.filter

    result = retriever.analyze_project(directories=dirs, case_filter=case_filter)
    logger.info(
        f"扫描结果: {result['total_files']} 文件 | {result['total_functions']} 函数 | {result['total_classes']} 类"
    )

    output = generate_layered_context_maps(retriever, args.output)
    logger.info(f"完成! 输出目录: {output}")


if __name__ == "__main__":
    main()
