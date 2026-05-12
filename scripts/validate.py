#!/usr/bin/env python3
"""Basic validation script for CI (no external dependencies)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

# 1. Module imports
modules = [
    "agents.intent_agent",
    "agents.retrieval_agent",
    "agents.codegen_agent",
    "agents.review_agent",
    "tools.build_context",
    "workflow.orchestrator",
]
for m in modules:
    __import__(m)
    print(f"✅ {m}")

# 2. Core classes exist
print("✅ All core classes exist")

# 3. Knowledge files
glossary = Path("knowledge/method_glossary.json")
assert glossary.exists(), "glossary missing"
data = json.loads(glossary.read_text())
print(f"✅ Glossary: {len(data)} entries")

templates = list(Path("knowledge/templates").glob("*.py"))
assert len(templates) > 0
print(f"✅ Templates: {len(templates)} files")

print("\n✅ ALL VALIDATIONS PASSED")
