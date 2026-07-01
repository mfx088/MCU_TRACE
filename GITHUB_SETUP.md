# GitHub 推送指南

> 本仓库**已本地 git 初始化**（commit `1f6003a`），但因公司网络限制 + GitHub 账号 SSH key 未配置，
> **需你手动完成最后一步**。整个过程 5 分钟。

## ⚠️ 关键：公司网封了 github.com

实测：
- SSH 22 → `git@github.com`：`Permission denied (publickey)`（其实是 TCP 通的，但 key 没在你的 GitHub 账号下）
- HTTPS 443 → `api.github.com`：`基础连接已经关闭: 发送时发生错误`（公司网拦截）
- `127.0.0.1:8443` 内部代理：服务未启动

**参考同仓项目 [E:\Git_PJ\CAN_LOG\HANDOVER.md §12](E:\Git_PJ\CAN_LOG\HANDOVER.md)：**
> `# Git push   # 公司网封 github，需手机热点`

**→ 唯一可靠方案：切到手机热点再 push**

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

### ⭐ 方案 0（最可靠）：手机热点 + SSH

参考同仓项目经验，公司网封了 github.com 所有通道。**唯一可靠方案是切到手机热点**：

1. **手机开热点**，电脑连上（iPhone 个人热点 / 安卓 USB 共享网络都行）
2. **创建空仓库** https://github.com/new
   - Repository name: `MCU_TRACE`
   - Visibility: **Private**（公司内部工具）
   - ⚠️ **不要勾选** Add a README / .gitignore / license（避免和本地冲突）
3. **添加 SSH key** https://github.com/settings/keys
   - 把 `~/.ssh/id_rsa.pub` 内容粘贴进去（见下方完整公钥）
   - Title: `mafuxuan@hangsheng.com.cn` 或 `MFX-ThinkBook`
4. **跑推送脚本**：
   ```powershell
   cd e:\Git_PJ\MCU_TRACE
   .\push.bat
   ```
   或者手动：
   ```powershell
   ssh -T git@github.com       # 应看到 "Hi mafuxuan! ..."
   git push -u origin main
   ```
5. **完成后切回公司网**（手机热点耗电 + 限流量）

> 完整公钥（`~/.ssh/id_rsa.pub`）：
> ```
> ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQC1eAeOHQlwqftmpZmqyDIXs48T8zZJDfvibl+Dc7fiFoUdC2LrPe2OctQqyoyrulDgzzO15p0PFLCwb8o6VZhcH75H4FUEB5FmSRXHlZUiPhvqFKWFvesO1lIgI3/6W2HGeue1V92OhFuIUefP8DgW2bBg3hNpHfK1EFPq+sx1FAcR3qA21P75fnKfQlWSfv0vaEZlwYobvflaHDrwy0EXW8sdg7vd4gP+QyYHD5I63USMdJMnShkIj2Tqcz2QIJtmD5Xy+Ix6R6nT38NLSxt3OCUR5h9ED1CXScMkF5FEoVr/VluH5wTVOM4+/e1KRyiM/bDgaLWiuU9CLlcS153x9DCTZahqeLNV4+R46vSij+xlztTTHEt1UpatNv0vA95+S0E7nocXOlyrU29Qd/SL88JlWnQNgTbaI7jQsPbbt7DfRe8c557V80UU5LsHLamNoln1W4aPsVrms43EUDXSALH/ihOAvfdswB7MLXAmOinNgGBnit4htPrRn5+FLAScB3egwRW+mUXdMWgw5r1xggVwRpd/5IZZ811c/R/uni6exw4y6n0iaDkTdBKYS1DzTE9BSKyV3vrHJFH9ydPzI/Y6FTurRvYgWVzcihvpRQBYcQ1O0w5XIFLz/gyHIs+eTJCVIq3s3j3iYuhPDmdJNblaDoXVBAdL50GiWOVhuQ== mafuxuan@hangsheng.com.cn
> ```

### 方案 1：手机热点 + HTTPS + PAT（不依赖 SSH key）

如果不想加 SSH key，用 PAT：
```powershell
# 1. 切到手机热点
# 2. 浏览器开 https://github.com/settings/tokens/new 拿 PAT（勾 repo）
# 3. 创建空仓库
# 4. 跑：
cd e:\Git_PJ\MCU_TRACE
$env:GH_TOKEN = 'ghp_你的token'
git remote set-url origin https://mafuxuan:${GH_TOKEN}@github.com/mafuxuan/MCU_TRACE.git
git push -u origin main
git remote set-url origin https://github.com/mafuxuan/MCU_TRACE.git   # 去掉 token
```

### 方案 2：把 PAT 给我

把 PAT 飞书发我（`mafuxuan`），我可以在你切到手机热点时**一次性跑完创建 + push**。

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
