# 04-dragon-host.md · 龙爪本机 141 操作约束
# 141 / 龙爪本机变更时改本文件

## 本机配置

- 主机名：`yu-K46CM`
- IP：192.168.31.141（USB 千兆网卡 `enx000ec67f1214`）
- OS：Linux（7.0.0-28-generic, Ubuntu 24.04 内核）
- 硬件：i5-3317U 2C/4T + 7GB RAM + USB 千兆（**PPS 上限 ~110-130Kpps**，141→任何 server 都有这瓶颈）
- Tailscale：100.74.59.8 已接入（UseExitNode=False，**不接管出网**）

## 关键约束

| 约束 | 原因 |
|---|---|
| **不许 SSH 连自己** | 老大问"在 X 上吗"先 `hostname && ip addr show` 验证 |
| **灵爪 SSH 链路 ≠ 龙爪 a-stock-data** | 灵爪走 SSH 进 NAS / PVE；龙爪走本地 a-stock-data 服务 |
| **SSH alias 在 home 受保护路径** | AI 写不动，需老大手动维护 `~/.ssh/config` |
| **141 sudo 密码不进 memory** | 走 `~/.hermes/netops/credentials.yaml`（chmod 600）|

## 操作陷阱

| 陷阱 | 后果 | 正确做法 |
|---|---|---|
| 老大说"我在 XX 跑" | 别远程 SSH 替他跑 | 只给脚本，让他自己执行 |
| 老大说"我自己装/配" | 别列步骤剧透 | 立刻停手只回风险 |
| 老大说"你帮我跑" | 可远程但要排查 | 全局副作用必须排查风险链 |
| 老大说"全部回滚" | 不要默认把文档修改也算 | 先列回滚清单确认边界 |

## 关键事实

- 任何"网络慢"结论前**先确认是不是卡在 141 USB 网卡**
- 默认网关通常走 50（透明代理），改网关到 31.1 = 走小来硬路由（绕过代理）

## 141 独立代理通道（2026-09-19 老大指示部署）

**目的**：软路由 50 nikki 挂时 141 仍能出国（老大原话："我就怕软路由挂了，你就不能出国访问了"）。

### 架构

```
[龙爪 hermes 命令] → ~/.hermes/hermes-proxy.sh (http_proxy=127.0.0.1:7893)
                            ↓
[141 本地 mihomo v1.19.31 v2 兼容] → systemd user unit (开机自启)
                            ↓
   proxy-providers → 192.168.31.10:3001 sub-store (机场+USVPS+JPVPS+SGVPS)
                            ↓
                       机场节点出口
```

**独立性**：141 自己有完整代理通道，**不依赖软路由 50**。即使 50 nikki 全挂，141 仍能上 YouTube/Google/HuggingFace 等。

### 关键文件/端口

| 项 | 值 |
|---|---|
| mihomo 二进制 | `~/.hermes/mihomo/mihomo` (v1.19.31 linux-amd64-v2-v1.19.31.gz) |
| config.yaml | `~/.hermes/mihomo/config.yaml` (从 50 scp Seven1_fallback_Geo融合.yaml, 转 LF) |
| systemd unit | `~/.config/systemd/user/mihomo.service` |
| 混合代理端口 | `127.0.0.1:7893` (mixed port, 走 HTTP/SOCKS) |
| 内置 DNS | `127.0.0.1:7874` (fake-ip) |
| 控制 API | `127.0.0.1:9090` |
| enable-linger | ✅ `State=lingering`（systemd user unit 能跨 session 跨开机） |
| hermes-proxy.sh | `~/.hermes/hermes-proxy.sh`（export http_proxy=127.0.0.1:7893） |

### 维护命令

```bash
# 状态/重启/日志
systemctl --user status mihomo
systemctl --user restart mihomo
tail -f ~/.hermes/mihomo/logs/mihomo.log

# 出口 IP 实测
curl -x http://127.0.0.1:7893 https://ifconfig.me   # 应返回代理 IP，不是 153.35.112.63

# 临时换节点（不动 yaml）
curl -X PUT http://127.0.0.1:9090/proxies/一键代理 -d '{"name":"香港故转"}'
```

### 已知坑

- **141 CPU 是 i5-3317U（Ivy Bridge 2013）**，同 J4125 一样只支持 x86-64-v2，**必须用 `mihomo-linux-amd64-v2-*` 二进制**，amd64 通用版 = v3 会秒退（跟 50 nikki 9/19 那次事故同根因）
- **TUN 模式不可用**（141 普通用户无 NET_ADMIN 权限），但**纯 HTTP 代理够用**——curl/wget/python 走 7893 完全 OK
- **yaml 默认 CRLF**（memory 9/18 那条）：scp 过来要 `sed -i 's/\r//g'`，否则 sed/awk 改字段静默不生效
- **proxy-providers 占位符 "机场名"** 报 `unsupported protocol scheme ""`，是 Seven1 yaml 模板里的占位 URL（不影响真订阅 机场/USVPS/JPVPS/SGVPS）
- **CPU 占用 ~3% / 内存 ~47MB**，轻量
- a-stock-data 部署在本机，CLI 走 `~/.hermes/skills/a-stock-data/scripts/fetch_data.py`

## 详细文档位置

| 主题 | 文档 |
|---|---|
| 操作自主权铁律 | `网管/SKILL.md` 必读坑段 |
| PVE 操作前的网关检查 | `网管/SKILL.md` §0.5 |
| 凭据存放 | `~/.hermes/netops/credentials.yaml` |
| a-stock-data 使用 | `a-stock-data` skill |