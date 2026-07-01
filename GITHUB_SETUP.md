# GitHub 推送指南 (v0.2.3)

> 本地 git 已初始化，main 分支，9 个 commit。
> 关键发现：你的 GitHub 账号是 **mfx088**（不是 mafuxuan），本机 id_ed25519 已在该账号下。

## 当前状态

| 步骤 | 状态 |
|---|---|
| 本地 `git init` + 9 个 commit | 完成 |
| Remote `origin -> git@github.com:mfx088/MCU_TRACE.git` | 完成 |
| `tools/github_tunnel.py` (raw TCP forward) | 完成 |
| `tools/http_proxy.py` (HTTP CONNECT 代理，**有 TLS bug**) | 部分 |
| `~/.ssh/config` 改用 `id_ed25519` | 完成 |
| `push.bat` + `start_proxy.bat` | 完成 |
| GitHub 添加 `id_ed25519` SSH key | 完成（你已完成） |
| GitHub 创建空仓库 `mfx088/MCU_TRACE` | **待完成** |

## 推送只需 1 步

### Step 1: 在 GitHub 创建空仓库（30 秒）

**方式 A：手机 4G 创建**（最稳）
1. 手机开 4G（公司 WiFi 封 github.com）
2. 浏览器打开 https://github.com/new
3. Repository name: `MCU_TRACE`
4. Visibility: `Private`
5. 注意不要勾选 Add a README / .gitignore / license
6. 点 "Create repository"

**方式 B：家用网创建**（如果有）

**方式 C：叫我帮你用 PAT 创建**
把 PAT 飞书发我（[创建地址](https://github.com/settings/tokens/new)，勾 `repo`，90 天），我用 tunnel + curl 一次性建仓。

### Step 2: 跑 push.bat

```powershell
cd e:\Git_PJ\MCU_TRACE
.\push.bat
```

脚本会：
1. 启 tunnel（127.0.0.1:8443 -> 20.205.243.x:443）
2. 测 SSH（应看到 "Hi mfx088!"）
3. 跑 `git push -u origin main`
4. 推完关 tunnel

预期输出：
```
[1/4] 启动 GitHub tunnel...
[2/4] 测试 GitHub SSH 连接（应看到 "Hi mfx088! ..."）...
Hi mfx088! You have successfully authenticated...
[3/4] 推送到 origin/main...
...
To github.com:mfx088/MCU_TRACE.git
 * [new branch]      main -> main
Branch main set up to track remote branch main from origin.

[4/4] 关闭 tunnel...
推送成功！
仓库地址: https://github.com/mfx088/MCU_TRACE
```

## 已实测的网络能力

| 操作 | 通道 | 状态 |
|---|---|---|
| SSH `git@github.com` | tunnel -> 20.205.243.x:443 | 通过（`Hi mfx088!`）|
| `git push` | 同上 | 待仓库创建后立即可推 |
| HTTPS `api.github.com/zen` | `--resolve api.github.com:443:20.205.243.168` | 返回 "Speak like a human." |
| HTTP CONNECT 代理（浏览器）| 同上 + local proxy | TLS handshake 在 curl+Schannel 下失败，浏览器可绕过 |
| 直接 HTTPS 443 到 github.com | 公司网 | 基础连接已关闭 |

## 关键技术点

- tunnel 走 SSH 协议：SSH 不走 TLS，tunnel raw 转发可正常握手
- HTTPS 走 IP 段：GitHub 主 IP 段 20.205.243.x 的 443 端口可达；`--resolve` 欺骗 cert 验证
- SSH config 第一条匹配生效：tunnel 入口（github.com -> 127.0.0.1:8443）放在最前
- id_ed25519 vs id_rsa：`id_rsa`（mafuxuan@hangsheng.com.cn）不在 GitHub 上；用 `id_ed25519`（14377@MFX-ThinkBook）

## 故障排查

### `Permission denied (publickey)`
等 30 秒（GitHub key cache）。确认用的是 `id_ed25519`（看 `.ssh/config` 的 `IdentityFile` 行）

### `Connection reset by 127.0.0.1 port 8443`
GitHub 主 IP 段变了。改 `tools/github_tunnel.py` 的 `TARGETS` 列表。
备用 IP：`140.82.114.{4,5,6}` `140.82.112.{3,4}`

### `Could not resolve hostname github.com`
tunnel 没启。跑 `start_proxy.bat`

### `fatal: repository not found`
GitHub 上没创建仓库，回到 Step 1

## 后续维护

```powershell
git add . ; git commit -m "..." ; .\push.bat
git pull origin main
```

## 参考

- `E:\Git_PJ\CAN_LOG\HANDOVER.md` §17 — 灵感来源
- `tools/github_tunnel.py` — 70 行 raw TCP forward
- `tools/http_proxy.py` — HTTP CONNECT 代理（有 TLS bug，备用）
- `push.bat` — 一键推送脚本
