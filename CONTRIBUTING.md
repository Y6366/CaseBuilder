# CONTRIBUTING.md - 贡献指南

## 开发流程

### 分支策略

```
main        ← 稳定分支，受保护
  └── dev   ← 开发主分支
       └── feature/xxx  ← 功能分支
       └── fix/xxx      ← 修复分支
```

### 工作流程

1. 从 `dev` 创建功能分支
```bash
git checkout dev
git pull
git checkout -b feature/your-feature
```

2. 开发 + 本地测试
```bash
# 运行本地检查（等同于CI门禁）
ruff check .
ruff format --check .
python3 -m py_compile agents/*.py workflow/*.py tools/*.py
```

3. 提交并推送
```bash
git add -A
git commit -m "feat: 简短描述"
git push origin feature/your-feature
```

4. 创建 Pull Request → `dev`

### Commit 规范

| 前缀 | 说明 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | 修复bug |
| `docs:` | 文档更新 |
| `refactor:` | 重构 |
| `test:` | 测试相关 |
| `chore:` | 构建/配置 |

## CI/CD 流水线

### CI Pipeline（每次push/PR自动触发）

| 阶段 | 检查内容 | 失败后果 |
|------|----------|----------|
| 🔒 Gate | 语法检查 + 模块导入验证 | 阻断 |
| 🔍 Lint | Ruff代码风格检查 | 阻断 |
| 🧪 Test | 单元测试 / 基础验证 | 阻断 |
| 🛡️ Security | Bandit安全扫描 + 密钥检测 | 警告 |

### Release Pipeline（打tag时触发）

```bash
git tag v1.0.1
git push origin v1.0.1
```

自动创建GitHub Release + Release Notes。

### 分支保护（需在GitHub上配置）

在 GitHub → Settings → Branches → Branch protection rules 中为 `main` 分支添加：

- ✅ Require a pull request before merging
- ✅ Require approvals (1人)
- ✅ Require status checks to pass (选择: gate, lint, test)
- ✅ Require linear history
- ✅ Do not allow force pushes
