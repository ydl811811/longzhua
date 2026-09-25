# 家庭网络

## 设备 IP 速查（不要再搞反，2026-07-18 教训）

| IP | 设备 | 备注 |
|---|---|---|
| 192.168.31.50 | 软路由 ImmortalWRT（旁路） | 跑 Nikki (mihomo) 代理，SSH root/123456，LuCI web/123456 |
| 192.168.31.10 | NAS 飞牛 (YDL) | 灵爪/OpenClaw 18789，SSH YDL/YDL32021976w |
| 192.168.31.141 | **本机 yu-K46CM** | 老大主笔记本，sudo YDL32021976 |

## 关键身份澄清：K46CM 是主笔记本，不是"网关"

**K46CM = 192.168.31.141 = 老大主笔记本（我所在的本机）** 这台机器在不同语境被叫过多个名字：

| 老大可能说的名字 | 实际指向 |
|---|---|
| "K46CM" / "我的笔记本" / "yu的本机" | 192.168.31.141 |
| "旁路网关" / "代理主机" / "Nikki 机器" / "ImmortalWRT" | 192.168.31.50（**软路由**，跑 Nikki/mihomo） |
| "主路由" / "硬路由" / "TP/小米主路由" | 192.168.31.1（只 Ping 通，SSH 关闭） |
| "NAS" / "飞牛" | 192.168.31.10 |

**判断快查**：`hostname && ip -4 addr show | grep "inet "` 
- `yu-K46CM` + `192.168.31.141` = 老大主笔记本
- `ImmortalWRT` + `192.168.31.50` = 软路由（旁路/Nikki）
- `YDL-NAS` + `192.168.31.10` = NAS
- 192.168.31.1 = 硬路由（主路由网关）

## 历史归档：旁路网关角色下线（2026-07-18）

- K46CM 原"旁路网关"角色整体下线
- systemd-resolved.conf 中 DNSStubListenerExtra=192.168.31.141 已删（曾指向本机自身）
- nikki/mihomo/openclash/sing-box 在 K46CM 上**从未部署**（代理能力统一在软路由 ImmortalWRT 192.168.31.50 跑 Nikki）  ← **2026-09-19 已过时**，见下
- **2026-09-19 起 141 部署独立代理**（老大指示"软路由挂了你不能出国" → 141 自己跑 mihomo）。详见 `04-dragon-host.md` §"141 独立代理通道"
- 本机 DNS 上游 = 192.168.31.1（主路由 dnsmasq，无 fakeip）
- **措辞铁律**："旁路网关角色下线" ≠ "K46CM 关机"。K46CM 机器还在跑，是老大主笔记本。

| ❌ 措辞过头 | ✅ 准确措辞 |
|---|---|
| "K46CM 整体停用" | "K46CM 上原旁路网关角色下线" |
| "192.168.31.141 机器停用" | "192.168.31.141 上的旁路网关功能下线" |

## web_extract SSRF 陷阱（2026-07-18 教训）

- 工具层 `tools/url_safety.py:async_is_safe_url()` 自带 SSRF pre-flight
- 命中 198.18.0.0/15（Nikki FakeIP）或 100.64.0.0/10（Tailscale）就 Block
- 修复（K46CM 一次配置）：`hermes config set security.allow_private_urls true`
- 后端（Firecrawl/Tavily）真实出网是公网，安全无害
- 169.254.169.254 / metadata.google.internal 永久 Block（与本开关无关）

## NAS SSH 公钥（FNOS 升级后追加恢复 key 登录）

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEtoOp/yemaVcmnE27F0UaAa1VozhaOFOIWTeqUqFjKo yu@yu-K46CM-new
```
加到 `/home/YDL/.ssh/authorized_keys` 即可。

## 📋 Memory 维护原则（来自 discipline.md，本文件遵循）

- **单一事实源**：同一网络事实（如"NAS IP=192.168.31.10"）只在 home-network.md 写一次，nas.md 不重复
- **本文件索引**：MEMORY.md（每次 session 注入）→ home-network.md → 命中 IP/网络问题查这里
- 详见 `details/discipline.md`「📂 Memory 归档铁律」段

---

## 🛠 旁路由 overlay 扩容方案（2026-07-31 实测成功）

**适用范围**：旁路由（192.168.31.50）磁盘空间不足，需要把 /overlay 从默认 loop0 切到大容量分区。

### 现状（扩容后）

| 项 | 状态 |
|---|---|
| `/overlay` 设备 | **`/dev/sda4` (48.2G)** ✅ |
| 已用 | 564.2M |
| 剩余 | 45.2G |
| fstab | 含 `target=/overlay, device=/dev/sda4, enabled=1` |
| Nikki | 正常跑 |
| fstab 备份 | `/etc/config/fstab.bak.20260731_222224` |

### 扩容脚本（已实测可跑）

**位置**：`/home/yu/.hermes/scripts/旁路由-overlay-扩容-sda4.sh`

**6 步流程**：
1. `mkdir -p /mnt/new_overlay`
2. `mount /dev/sda4 /mnt/new_overlay`
3. `cp -rp /overlay/. /mnt/new_overlay/`（BusyBox 不支持 -a，用 -rp）
4. 重写 fstab（详见脚本）
5. 验证 fstab（cat + grep target /overlay）
6. `umount /mnt/new_overlay`
7. **手动 `reboot`**（agent 不能自动跑，被系统黑名单）

### 关键教训（不要忘）

- ⚠️ **分析源码不一定准确** — 7/31 上午读源码判断"block 会拒绝 target=/overlay"，实际**用块设备路径就能切成功**（文件路径才不行）
- ⚠️ **agent 不能跑 reboot** — 脚本里去掉最后一步，老大手动
- ⚠️ **BusyBox cp 不支持 -a** — 用 `-rp`（recursive + preserve）
- ⚠️ **执行前必须备份 fstab** — 救命稻草
- ⚠️ **fstab device 必须是块设备路径**（如 `/dev/sda4`），不能是文件路径（`/mnt/sda4/overlay.img` 会被 block 跳过）

### ❌ 已废止的旧方案

| 旧方案 | 为什么废止 |
|---|---|
| 3GB overlay.img + fstab 切 overlay | device 是文件路径，block 跳过，不生效 |
| 换 `rootfs_data` 卷标 | 不必要 — 上面新方案更简单，不用换卷标 |
| sysupgrade 重刷固件 | 风险中 — 新方案 6 步搞定，不用重刷 |

### 备份/回滚

- **当前 fstab 备份**：`/etc/config/fstab.bak.20260731_222224`
- **完整方案文档**：`/tmp/旁路由overlay扩容方案_20260726.md`（已重写为新版本）

### 后续清理（可选，等系统稳定后做）

- 删 `/mnt/sda4/overlay_backup_20260731_222224/`（4KB 空目录，失败残留）
- 删 `/mnt/sda4/overlay_backup_20260731_222236/`（162M 备份，扩容稳定后无需）
- 删 `/mnt/sda4/overlay.img`（3G 文件，已废弃）+ 卸 loop1