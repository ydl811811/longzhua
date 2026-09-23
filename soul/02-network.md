# 02-network.md · 家庭网络拓扑 + 操作教训
# 拓扑变更或新教训时改本文件

## 拓扑总览（2026-09-05 后状态）

```
光猫 (路由模式, 192.168.1.x)
  ↓ RJ45
小米硬路由 192.168.31.1 (PPPoE 拨号 + NAT + DHCP + WiFi)
  ↓ LAN
PVE 宿主 192.168.31.20 (J4125, root=12345678)
  ├─ VM 101 = ImmortalWrt = 软路由 192.168.31.50 (root=123456, 代理=sing-box 透明代理)
  ├─ 电视盒子 192.168.31.133 (HK1 RBOX X4 / Android 11 / Amlogic S905X4)
  │    有线, 静态IP, 网关+DNS 都指向旁路由 31.50（老大设的, 目的走代理）
  │    ADB 无线调试 5555（adb root 可用）; MAC 02:ad:32:01:fd:f8（随机MAC）
  └─ 老大 Win 笔记本 192.168.31.156
├─ 龙爪 141 K46CM (Linux, 100.74.59.8 Tailscale)
└─ NAS YDL@192.168.31.10 (Debian 12, 4核/15GB)
```

## 凭据存放

**全部凭据 → `~/.hermes/netops/credentials.yaml`**（chmod 600）
- memory **永远不存**任何密码 / API key

## VM 101 当前配置（2026-09-05 优化后）

- 资源：4 核 / 3GB RAM / 14.3GB disk
- 网卡：**virtio queues=4**（多队列分散中断）
- UCI：`network.@globals[0].packet_steering=0` + `steering_flows=2048`
- 实测：小包 480→672 Mbps（+40%），softirq 88x→1.5x，大包 0% 衰减
- 备份：`/etc/pve/qemu-server/101.conf.bak-pre-multiqueue-20260905`

## 网络操作教训（3 条铁律）

| 日期 | 教训 | 简述 |
|---|---|---|
| 2026-08-23 | qm shutdown 101 → 50 代理挂 → 141 网关断 | 操作前先看 141 网关依赖 |
| 2026-09-02 | ps \| grep X 空 ≠ "挂了" | 先确认替代服务 |
| 2026-09-05 | 测小包用 NAS 当 client 是误判源 | 用 141 当 client（NAS enp2s0 单队列是 NAS 瓶颈不是 server）|
| 2026-09-13 | 电视盒子「YouTube/Google 打不开」= **系统时间错**（不是网络！）| HK1 盒子无可用 RTC（`/dev/rtc0` 不存在）+ NTP 不通 → 开机时钟停在 `2024-05-10` → TLS 证书被判「尚未生效」→ **所有 HTTPS 失败**。识别特征 logcat：`SSLHandshakeException: Unacceptable certificate` + `SntpClient: Poll timed out`。修：`adb root` → `adb shell date MMDDhhmmCCYY.ss` → `settings put global ntp_server ntp.aliyun.com`（默认 NTP 不通；换阿里云后 25ms 同步成功、自动校正 -160s）。验证看 sing-box `/connections` 里 www.youtube.com 有无下行字节 |
| 2026-09-13 | 验证「LAN 设备是否真走旁路由+代理」三招 | ① conntrack 里见该设备流（回包 src=31.50）② `nft list table inet sing-box` 的 **prerouting** redirect 计数在该设备发包时递增（output 链那条是路由器自己的，别混）③ 出口 IP 对照：国内站点见家宽 `153.35.112.63` / 境外站点见代理 `18.162.193.47`（香港AWS）。**Android 无 curl 时**用 `sh -c '{ cat req; sleep 4; } \| nc -w 12 IP 80'`——toybox nc 必须保持 stdin 打开才收得到响应 |
| 2026-09-13 | 下游设备「无法上网」先查旁路由代理节点 | 31.50 的 sing-box 节点故障 → 133 盒子境外站点全挂（国内直连仍通）。看 `logread \| grep sing-box`。另：Android 默认路由在 `eth0` 策略表、**不在 main 表**，`ip route show` 看不到 default 是正常的，别误判 |
| 2026-09-13 | 灵爪搬家：进程在 ≠ 服务通 | 软链接搬家后必须 `openclaw doctor --fix`，再 `openclaw gateway start`，最后**真发飞书消息端到端验证** |
| 2026-09-19 | **关 nikki 后只有 Wi-Fi 设备断网 = OpenWrt lan→wan 没勾 IP 动态伪装（masquerade）** | nikki 透明代理接管 NAT 时，Wi-Fi 走 50 出公网正常；关 nikki 后流量回到 OpenWrt 原生路径，**没 masquerade → LAN 包出去后回不来**。修：LuCI → Network → Firewall → lan→wan 规则勾 **IP 动态伪装**。"为啥只有 Wi-Fi 断、有线不断" = 网关是 50 的设备才走软路由出公网，网关 31.1 的有线设备走小米主路由 PPPoE 直出根本不经过 50。memory 教训：①排查"个别设备断网"先看它网关是不是软路由 ②关代理前先确认 lan→wan masquerade 勾好 ③记忆 mis：masquerade 不是优化项，是**没有就全断**的开关 |

## OpenClaw (灵爪) 操作纪律（2026-09-13 落地）

灵爪 = 飞牛 NAS (**192.168.31.10**) 上的另一个 agent（不是龙爪的附属物，**不归龙爪管**）。但老大让龙爪帮查/帮修时，按以下命令。

### 守护结构（3 层套娃，systemctl stop 没用）

```
飞牛 trim_main（飞牛 OS 核心）
  ↓ 监控
trim_open_gateway.service（system 级，PID 由 trim_open_gateway 持有）
  ↓ 拉
openclaw supervisor（PID 769906 类，trim 拉）
  ↓ 拉
gateway --port 18789（PID 771227 / 811959 类，真正跟飞书对话）
```

**systemctl --user stop openclaw-gateway** 灵爪会立刻被 supervisor 拉起。**必须用 OpenClaw 自带命令**（见下）。

### 关键命令（OpenClaw 2026.8.2 → 2026.9.4 都适用）

| 任务 | 命令 | 说明 |
|---|---|---|
| **停灵爪** | `openclaw gateway stop` | 自带命令，绕开 systemd 套娃，让 supervisor 不再拉 gateway |
| **启灵爪** | `openclaw gateway start` | 自带命令，supervisor 会拉 gateway |
| **查状态** | `openclaw status` | Gateway / Channels / Sessions 全表 |
| **升级** | `openclaw update` | 内部流程：stop → npm → doctor → 失败则要求 fix |
| **修复** | `openclaw doctor --fix` | 接受 workspace path alias 迁移等（搬家后必跑）|
| **强制修复** | `openclaw doctor --fix --force` | 跳过确认 |
| **非交互修复** | `openclaw doctor --fix --non-interactive` | safe migrations only |

### 搬家 / 路径变更流程（重要）

如果 `/home/YDL/.openclaw` 物理路径变了（搬数据、换盘、改挂载点）：

1. **rsync 数据到新位置**（不直接 mv，灵爪可能还在跑）
2. **用 `openclaw gateway stop` 优雅停**
3. **mv 旧目录 → .bak**（可逆，不是 rm）
4. **`ln -s 新路径 旧路径`** 创建软链接
5. **`openclaw gateway start` 启灵爪** —— **灵爪从软链接读老路径，无感**
6. **跑 `openclaw doctor --fix`** —— 接受 workspace path alias 迁移到新路径
7. **`openclaw gateway start` 再次启动**（如果第 5 步 gateway 启动失败，doctor 修好后重试）
8. **真发飞书消息验证端到端** ← **不可省**
9. 验证 OK 后 `rm -rf 旧 .bak`

### Update 失败模式（WorkspaceAliasRepointedError）

如果 update 报：
```
WorkspaceAliasRepointedError: workspace path alias points to a different current target:
~/.openclaw/workspace now resolves to <新路径>, but its saved setup records belong to <旧路径>
```

修法：跑 `openclaw doctor --fix` 接受迁移（会问"Confirm only if this is the same workspace after a folder move. Transfer its saved setup and file-verification history without changing workspace files? **Yes**"）。

**update 成功后 gateway 不自动启动**——"Managed gateway remains stopped because update recovery could not prove a runnable installation"。要手动 `openclaw gateway start`。

### 龙爪边界

- 老大授权时龙爪**可帮灵爪跑** `openclaw gateway stop/start`、`openclaw doctor --fix`、`openclaw status` 等**只读或 OpenClaw 自带命令**
- **不主动改**灵爪的配置、飞书 app 凭证、workspace 路径
- **不删**灵爪的数据（除非老大明确授权，且已 backup）

## Tailscale 状态（2026-09-05 实测纠正）

- 141 已接入 Tailscale（IP 100.74.59.8），但 **UseExitNode=False**
- **141 没被 exit node 接管出网**——DNS 走小米 31.1
- memory 旧条目"日本 VPS exit node 接管"是错的，已纠正

## 详细文档位置

| 主题 | 文档 |
|---|---|
| 网络架构 / 排障工作流 / 必读坑段 | `网管/SKILL.md` |
| PVE 安装 / 改 IP / 操作 | `网管/references/pve-*.md` |
| 软路由流量优化 | `网管/references/j4125-*.md` |
| FW4 flowtable / 单臂路由 | `网管/references/fw4-flowtable-and-ps-grep-pitfall-20260902.md` |
| OpenClaw (灵爪) 3 层套娃守护 + stop/start/doctor 命令 | `02-network.md` §OpenClaw 操作纪律 |
| 决策记录 | `~/.hermes/netops/decision_log.yaml` |