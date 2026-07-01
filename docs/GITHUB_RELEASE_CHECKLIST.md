# GitHub 发布检查清单

发布 `AI 量化交易` 到 GitHub 前，建议按本清单逐项确认。

## 1. 敏感信息

- [ ] `.env` 没有被加入 git。
- [ ] 没有提交真实模型 API Key。
- [ ] 没有提交交易所 API Key、Secret、Passphrase、私钥或钱包助记词。
- [ ] 日志、截图、文档中没有泄露账号、邮箱、Token、代理地址等敏感信息。
- [ ] 交易所 API Key 未开启提现权限，并建议配置 IP 白名单。

## 2. 不应提交的大文件/本地文件

- [ ] `frontend/node_modules/` 未提交。
- [ ] `.venv/`、`python/.venv/` 未提交。
- [ ] `logs/`、`python/logs/` 未提交。
- [ ] SQLite 数据库、LanceDB、知识库目录未提交。
- [ ] IDE 本地目录 `.idea/` 未提交。
- [ ] 个人本地启动脚本 `Start-ValueCell-Local.ps1` 未提交。

## 3. 文档

- [ ] `README.md` 中的项目定位、技术栈、启动命令和访问地址准确。
- [ ] `.env.example` 只包含占位符和示例，不包含真实密钥。
- [ ] 风险提示清楚说明：项目不构成投资建议，真实交易可能亏损。
- [ ] 如仓库是二次开发版本，README 中已说明来源和 License。

## 4. 本地验证

建议至少执行一次：

```powershell
# Windows
.\start.ps1 -Help
```

```bash
# macOS / Linux
bash start.sh --help
```

如果依赖已安装，也建议执行：

```bash
make lint
make test
```

前端检查：

```bash
cd frontend
bun run typecheck
bun run lint
```

## 5. 初始化并推送 GitHub

如果当前目录还不是 git 仓库：

```bash
git init
git add .
git commit -m "Initial open-source release"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<你的仓库名>.git
git push -u origin main
```

如果已经是 git 仓库：

```bash
git status --short
git add README.md .env.example .gitignore docs/GITHUB_RELEASE_CHECKLIST.md Start-ValueCell-Local.example.ps1
git commit -m "Prepare project for GitHub release"
git push
```
