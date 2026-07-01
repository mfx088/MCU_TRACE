# GitHub 推送指南

> 本仓库**已本地 git 初始化**（commit `1f6003a`），但因公司网络限制 + GitHub 账号 SSH key 未配置，
> **需你手动完成最后 2 步**。整个过程 5 分钟。

## 关键：公司网封了 github.com（已有解法）

实测：
- SSH 22 → `git@github.com`：❌ TCP connect timeout
- HTTPS 443 → `api.github.com` 直连：❌ SNI 错配 403
- **新解法**：本地 TCP tunnel（参考 [CAN_LOG §17](E:\Git_PJ\CAN_LOG\HANDOVER.md)）
  - Tunnel 转发到 `20.205.243.{160,161,166,168}:443`（公司网可达的 GitHub 主 IP 段）
  - SSH 协议：tunnel 后正常工作
  - HTTPS API：用 `curl --resolve api.github.com:443:20.205.243.168` 绕过 SNI

## 当前状态（2026-07-01）

| 步骤 | 状态 |
|---|---|
| 本地 `git init` + main 分支 | ✅ |
| 6 个 commit（47 文件 + tools/github_tunnel.py） | ✅ |
| Remote `origin → git@github.com:mafuxuan/MCU_TRACE.git` | ✅ |
| `tools/github_tunnel.py`（移植自 CAN_LOG §17） | ✅ |
| `~/.ssh/config` 已加 tunnel 入口 | ✅ |
| `push.bat` 一键脚本（启 tunnel + ssh 测试 + push + 收 tunnel） | ✅ |
| GitHub 添加 `id_rsa.pub` SSH key | ❌ **待你完成** |
| GitHub 创建空仓库 `mafuxuan/MCU_TRACE` | ❌ **待你完成** |

## 推送步骤

### Step 1: 在 GitHub 浏览器上添加 SSH key（一次性）

打开 https://github.com/settings/keys

点 "New SSH key"，粘贴以下完整公钥：

```
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQC1eAeOHQlwqftmpZmqyDIXs48T8zZJDfvibl+Dc7fiFoUdC2LrPe2OctQqyoyrulDgzzO15p0PFLCwb8o6VZhcH75H4FUEB5FmSRXXlZUiPhvqFKWFvesO1lIgI3/6W2HGeue1V92OhFuIUefP8DgW2bBg3hNpHfK1EFPq+sx1FAcR3qA21P75fnKfQlWSfv0vaEZlwYobvflaHDrwy0EXW8sdg7vd4gP+QyYHD5I63USMdJMnShkIj2Tqcz2QIJtmD5Xy+Ix6R6nT38NLSxt3OCUR5h9ED1CXScMkF5FEoVr/VluH5wTVOM4+/e1KRyiM/bDgaLWiuU9CLlcS153x9DCTZahqeLNV4+R46vSij+xlztTTHEt1UpatNv0vA95+S0E7nocXOlyrU29Qd/SL88JlWnQNgTbaI7jQsPbbt7DfRe8c557V80UU5LsHLamNoln1W4aPsVrms43EUDXSALH/ihOAvfdswB7MLXAmOinNgGBnit4htPrRn5+FLAScB3egwRW+mUXdMWgw5r1xggVwRpd/5IZZ811c/R/uni6exw4y6n0iaDkTdBKYS1DzTE9BSKyV3vrHJFH9ydPzI/Y6FTurRvYgWVzcihvpRQBYcQ1O0w5XIFLz/gyHIs+eTJCVIq3s3j3iYuhPDmdJNblaDoXVBAdL50GiWOVhuQ== mafuxuan@hangsheng.com.cn
```

- Title: `mafuxuan@hangsheng.com.cn` 或 `MFX-ThinkBook`
- Key type: `Authentication Key`

### Step 2: 在 GitHub 浏览器上创建空仓库（一次性）

打开 https://github.com/new

- **Repository name**: `MCU_TRACE`
- **Visibility**: `Private`（公司内部工具）
- ⚠️ **不要勾选** Add a README / .gitignore / license
- 点 "Create repository"

### Step 3: 推送

```powershell
cd e:\Git_PJ\MCU_TRACE
.\push.bat
```

**脚本行为**：
1. 启动 `tools/github_tunnel.py`（监听 127.0.0.1:8443）
2. 测 SSH：`ssh -T git@github.com`（应看到 `Hi mafuxuan! ...`）
3. 跑 `git push -u origin main`
4. 推完自动关 tunnel

预期输出：
```
[1/4] 启动 GitHub tunnel...
[2/4] 测试 GitHub SSH 连接...
Hi mafuxuan! You've successfully authenticated...
[3/4] 推送到 origin/main...
...
To github.com:mafuxuan/MCU_TRACE.git
 * [new branch]      main -> main
Branch 'main' set up to track remote branch 'main' from 'origin'.

[4/4] 关闭 tunnel...
✓ 推送成功！
```

## 备选方案：把 PAT 给我（最快，30 秒搞定）

如果不想手动加 SSH key，把 GitHub PAT（[点这里创建](https://github.com/settings/tokens/new)，勾 `repo`，90 天有效）飞书发给我。

我可以**用 tunnel + PAT 通过 API 一次性完成**（不需要你开浏览器）：
```powershell
$env:GH_TOKEN = 'ghp_你的token'
$env:CURL = 'C:\Windows\System32\curl.exe'

# 创建仓库 (公司网内 --resolve 绕 SNI)
& $env:CURL -X POST -H "Authorization: token $env:GH_TOKEN" `
  --resolve api.github.com:443:20.205.243.168 `
  https://api.github.com/user/repos `
  -d '{"name":"MCU_TRACE","private":true,"description":"MCU 日志自动解析 + 可视化分析工具（v0.2.2）"}'

# 添加 SSH key
$pubkey = Get-Content $env:USERPROFILE\.ssh\id_rsa.pub
$body = @{title="mafuxuan-MFX-ThinkBook"; key=$pubkey} | ConvertTo-Json
& $env:CURL -X POST -H "Authorization: token $env:GH_TOKEN" `
  --resolve api.github.com:443:20.205.243.168 `
  -H "Content-Type: application/json" `
  https://api.github.com/user/keys -d $body

# 推送
cd e:\Git_PJ\MCU_TRACE
.\push.bat
```

## 故障排查

### `Permission denied (publickey)` 但 key 已加
- 等 30 秒（GitHub key cache）
- 确认公钥完整（`ssh-rsa` 前缀 + `mafuxuan@hangsheng.com.cn` 后缀）

### `Connection reset by 127.0.0.1 port 8443`
- GitHub 主 IP 段变了
- 改 `tools/github_tunnel.py` 的 `TARGETS` 环境变量
- 备用 IP：`140.82.114.4` `140.82.114.5` `140.82.112.3` `140.82.112.4`

### `fatal: repository not found`
- GitHub 上没创建仓库，回到 Step 2

## 推送成功后

```powershell
git remote -v
# origin  git@github.com:mafuxuan/MCU_TRACE.git (fetch)
# origin  git@github.com:mafuxuan/MCU_TRACE.git (push)

git log --oneline
# 8761b1a feat: 公司网绕封 push 方案...
# e99a357 chore: improve push.bat with network troubleshooting
# ...
```

## 后续维护

```powershell
# 修改后
git add . ; git commit -m "..." ; .\push.bat

# 同步
git pull origin main
```

## 参考

- [E:\Git_PJ\CAN_LOG\HANDOVER.md §17 公司网绕封 GitHub push 方案](E:\Git_PJ\CAN_LOG\HANDOVER.md)
- [tools/github_tunnel.py](tools/github_tunnel.py) — 70 行 raw TCP forward
- [push.bat](push.bat) — 一键推送脚本
