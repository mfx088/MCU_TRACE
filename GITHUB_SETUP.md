# GitHub 推送指南

> 本仓库**已本地 git 初始化**（commit `1f6003a`），但因公司网络限制 + GitHub 账号 SSH key 未配置，
> **需你手动完成最后一步**。整个过程 5 分钟。

## 现状

- **本地仓库**：✅ 已 `git init` + 首次 commit（`v0.2.2: 初始版本`，47 个文件，852KB）
- **分支**：`main`
- **远端**：`origin → git@github.com:mafuxuan/MCU_TRACE.git`（已设置）
- **本地 SSH key**（`~/.ssh/id_rsa.pub`）：
  ```
  ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQC1eAeOHQlwqftmpZmqyDIXs48T8zZJDfvi...
  mafuxuan@hangsheng.com.cn
  ```
  指纹：`SHA256:B/SR5cpqEQ4gS+XfDRpHoCUJKqHQL5bOlLPSsL1Ti0A`

## 推送步骤

### 方案 A：SSH（推荐，前提：GitHub 已加 SSH key）

1. 打开 https://github.com/settings/keys
2. 点 "New SSH key"，把上面那把 `id_rsa.pub` 内容粘贴进去，Title 填 `mafuxuan@hangsheng.com.cn` 或 `MFX-ThinkBook`
3. 创建空仓库：
   - 打开 https://github.com/new
   - Repository name: `MCU_TRACE`
   - Visibility: **Private**（公司内部工具）
   - ⚠️ **不要勾选** "Add a README file" / "Add .gitignore" / "Choose a license"（避免和本地冲突）
4. 在本仓库目录跑：
   ```bash
   cd e:\Git_PJ\MCU_TRACE
   git push -u origin main
   ```

### 方案 B：HTTPS + PAT（公司网拦截时备选）

1. 创建 PAT：https://github.com/settings/tokens/new
   - Note: `MCU_TRACE push`
   - Expiration: 90 days（或按公司策略）
   - Scopes: `repo`（完整仓库访问）
2. 创建空仓库：https://github.com/new（同上）
3. 改 remote 为 HTTPS + 推送：
   ```bash
   cd e:\Git_PJ\MCU_TRACE
   git remote set-url origin https://github.com/mafuxuan/MCU_TRACE.git
   # 推送时 PAT 作为密码（用户名用 mafuxuan）
   git push -u origin main
   # Windows 凭据管理器会记住，下次不用再输入
   ```

### 方案 C：让我帮你做（需提供 PAT）

把 PAT 通过安全渠道发给我（飞书/邮件都行），我可以一行 curl + push：
```powershell
$env:GH_TOKEN = 'ghp_xxxxxxxxxxxxxxxxxxxx'
# 创建仓库（私有）
Invoke-RestMethod -Uri "https://api.github.com/user/repos" -Method Post `
  -Headers @{Authorization = "token $env:GH_TOKEN"} `
  -ContentType "application/json" `
  -Body '{"name":"MCU_TRACE","private":true,"description":"MCU 日志自动解析 + 可视化分析工具（v0.2.2）","auto_init":false}'
# 推送
cd e:\Git_PJ\MCU_TRACE
git remote set-url origin https://mafuxuan:${GH_TOKEN}@github.com/mafuxuan/MCU_TRACE.git
git push -u origin main
git remote set-url origin https://github.com/mafuxuan/MCU_TRACE.git   # 去掉 token
```

## 推送成功后

`git remote -v` 应该显示：
```
origin  git@github.com:mafuxuan/MCU_TRACE.git (fetch)
origin  git@github.com:mafuxuan/MCU_TRACE.git (push)
```

`git log --oneline` 显示：
```
1f6003a v0.2.2: 初始版本
```

## 后续维护

```bash
# 修改文件后
git add .
git commit -m "describe change"
git push origin main

# 同步到 GitHub
git pull origin main
```

## 注意事项

- `dist/`、`work/_e2e/`、`work/log_20260629_140253/`、`work/test_enc*/` 已被 `.gitignore` 排除
  （这些是 build 产物和测试数据，太大不进仓）
- `work/report.html` 和 `work/report.json` 保留（v0.2.2 E2E 验证产物）
- 每次发版：打 tag 即可
  ```bash
  git tag v0.2.2 1f6003a
  git push origin v0.2.2
  ```
