# PVE 双软路由改造方案（小米硬路由废止版）

**创建日期**：2026-08-02  
**作者**：龙爪（Hermes Agent）  
**对象机器**：CncTion J4125-4L（@ 192.168.31.50，现跑 ImmortalWrt 24.10.4）  
**目标**：J4125 装 PVE 9 + 跑 2 个 OpenWrt VM（主路由 + 旁路由），小米硬路由废止改纯 AP

---

**2026-08-02 决策**：
- 老大选**方案 A：主路由 iKuaiOS + 旁路由 ImmortalWrt**
- 理由：主路由专款专用（iKuaiOS 商用稳定 + 拨号重拨 + 流控）+ 旁路由专款专用（ImmortalWrt + Nikki 生态无缝迁移）

## 0. 系统选型（**已定方案 A**）

| VM | 系统 | 角色 |
|---|---|---|
| **VM 100 主路由** | **iKuaiOS 3.7.23 stable** | PPPoE 拨号 + DHCP + DNS + 防火墙 + NAT + 流控 |
| **VM 101 旁路由** | **ImmortalWrt 24.10.4** | Nikki/mihomo 透明代理 + fakeip DNS |

**iKuaiOS 选型理由**：
- ✅ 专做主路由（PPPoE + DHCP + NAT + 流控商用级稳定）
- ✅ 中文 WebUI（老大不用学命令）
- ✅ PPPoE 智能重拨（OpenWrt 拨号挂了自己写 watchdog）
- ✅ 资源占用低（2GB RAM 足够，剩 4-5GB 给 PVE 后续 VM）
- ⚠️ 闭源 / 国内公司 / 高级功能需授权码（**免费版够家庭使用**）

**ImmortalWrt 选型理由**：
- ✅ Nikki 是 OpenWrt 原生 LuCI app，一键安装
- ✅ 备份文件无缝迁移（profile / run / zashboard）
- ✅ 老大已熟生态，恢复快

**架构**（2 层 NAT）：
```
[光猫 路由模式 + DHCP 192.168.1.x] → [小米硬路由 192.168.31.1 (PPPoE拨号+NAT+DHCP+WiFi)] → [旁路由 J4125 192.168.31.50 (Nikki透明代理)] → [141/NAS/...]
```

**硬件**：
- J4125-4L：Celeron J4125（4C/4T，VT-x + VT-d）/ 12GB DDR4 / 48GB SSD / 4 网口（eth0/1/2/3）
- 网口现状：eth0 接小米 LAN1 / eth1 未插（DOWN）/ eth2/3 备用
- 当前 OS：ImmortalWrt 24.10.4（Legacy BIOS + MBR 分区）

**关键事实**：
- 老大手上有 PPPoE 账号（051005333376 / 506900）
- 小米硬路由在 PPPoE 拨号，光猫是路由模式 DHCP
- Nikki/mihomo 在跑（web panel: http://192.168.31.50:9090/ui/zashboard/）

**已完成备份**：`/home/yu/pve-backup-20260802.tar.gz`（29.2 MB / 833 文件，含 Nikki + OpenWrt 全配置）

---

## 2. 改造后架构

**架构**（同样 2 层 NAT，但 PVE 接管）：
```
[光猫 路由模式 原样] → [PVE 主机 J4125（192.168.31.50 管理口）] 
                       ├─ VM 100 主路由 OpenWrt-A (192.168.31.1) — PPPoE 拨号 + DHCP + DNS + NAT + 防火墙
                       └─ VM 101 旁路由 OpenWrt-B (192.168.31.51) — Nikki/mihomo 透明代理
                       
                       ↓ vmbr0 (LAN)
                       [小米硬路由 改纯 AP (WAN口空置，只用 LAN+WiFi)] → 141/NAS/...
```

**关键 IP 调整**：
| 项 | 现状 | 改造后 |
|---|---|---|
| J4125 PVE 管理 | 192.168.31.50（旁路由 OS）| 192.168.31.50（PVE Web）|
| 小米硬路由 | 192.168.31.1（PPPoE 拨号）| **废止**（改纯 AP，IP 不再被设备用）|
| 主路由 VM | 不存在 | **192.168.31.1**（接管小米的 IP）|
| 旁路由 VM | 192.168.31.50（现在跑 Nikki）| **192.168.31.51**（新建，原 50 给 PVE）|
| 141 / 156 / NAS | DHCP 自动 | 不变 |

---

## 3. VM 资源分配

| 资源 | 主路由 VM (100) | 旁路由 VM (101) | PVE 宿主 | 剩余 |
|---|---|---|---|---|
| CPU | 2 核 | 2 核 | 系统自留 | 0（4 核刚好）|
| RAM | 2 GB | 3 GB（mihomo 吃内存）| 0.5 GB | 6.5 GB 给后续 VM/LXC |
| 磁盘 | 8 GB | 8 GB | 16 GB（PVE 系统 + ISO）| 16 GB 给数据/LXC |

**vmbr 规划**：
- **vmbr0**（LAN）：eth0 上接，所有 VM 共享（NAT/DHCP/DNS/Nikki 流量走这）
- **vmbr1**（WAN）：eth1 接光猫，**只给主路由 VM 直通**（PPPoE 必须直通，桥接模式拨号不稳）

---

## 4. 物理接线（老大动手，方案 A）

### 改造后接法
```
[光猫 LAN1] ──网线A(原小米WAN线)──> [J4125 eth1]    ← 移到这
[J4125 eth0] ──网线B(原)──> [小米硬路由 LAN1]
                            (小米 WAN口 空置不插)
[小米 LAN2/3/4] → [141/NAS/...]
[小米 WiFi] → [老大手机/平板]
```

### 接线步骤（**先改网关再改接线，避免断网盲区**）

1. **141 网关改 192.168.31.1**（直连小米，绕过旁路由 Nikki，但同网段仍能 SSH 进 50）
2. 拔小米 WAN 口网线 → 网线 A 改插 J4125 eth1
3. 小米 WAN 口永远空置
4. J4125 物理装机（插 U 盘 + 进 BIOS + U 盘启动）
5. PVE 装好后从 141 Web `https://192.168.31.50:8006` 远程操作

**断网窗口**：从步骤 2 开始到主路由 VM PPPoE 拨号成功（**预计 1-2 小时**）

---

## 5. 完整执行步骤（**老大手动操作在 Stage 2**）
### Stage 0：备份（已完成 ✅）
- `/home/yu/pve-backup-20260802.tar.gz`（29.2 MB / 833 文件）

### Stage 1：远程准备（**不断网**，我来做）
- ✅ PVE 9.2-1 ISO 下载完成（`/home/yu/pve-install/proxmox-ve_9.2-1.iso`）
- 下载 iKuaiOS 9 ISO（后台跑）
- 烧 Ventoy U 盘（**双 ISO 启动菜单**）

### Stage 2：物理装机（**老大操作 10 分钟**）
1. U 盘插 J4125
2. 接显示器 + 键盘
3. 重启 → DEL 进 BIOS
4. **J4125 是 Legacy BIOS**——PVE 9 装机时选 "Advanced → Force MBR" 模式
5. 选 U 盘启动 → Install Proxmox VE
6. 装机向导关键设置：
   - Management Interface: **eth0**
   - Hostname: `pve-router`
   - IP: **192.168.31.50/24**（保持原 IP）
   - Gateway: **192.168.31.1**（临时指向小米旧 IP，后续改主路由 VM IP）
   - DNS: **192.168.31.1**（同上）

### Stage 3：远程建 VM（**我来做，从 141 浏览器**）

```bash
# 主路由 VM (ID 100) — iKuaiOS
qm create 100 --name ikuai-main --memory 2048 --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --net1 virtio,bridge=vmbr1 \
  --scsihw virtio-scsi-pci --scsi0 local-lvm:8 \
  --ide2 local:iso/ikuaios-9-x86.iso,media=cdrom \
  --boot order=ide2

# 旁路由 VM (ID 101) — ImmortalWrt
qm create 101 --name immortal-bypass --memory 3072 --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci --scsi0 local-lvm:8 \
  --ide2 local:iso/immortalwrt-24.10.4-x86-64-generic-ext4-combined.img,media=cdrom \
  --boot order=ide2
```

### Stage 4：主路由 VM 配置（iKuaiOS）
- 装好后进 iKuaiOS Web UI（默认 `https://192.168.31.1`）
- WAN1 接 vmbr1（光猫侧）→ **PPPoE 拨号**（老大提供的账号 051005333376 / 506900）
- LAN1 接 vmbr0（家庭网侧）→ 192.168.31.1/24
- 启用 DHCP（默认就启用）
- 启用 DNS 转发
- 启用 IPv6（如需要）

### Stage 5：旁路由 VM 配置（ImmortalWrt）
- 装好后从备份文件 `/home/yu/pve-backup-20260802.tar.gz` 解压出 nikki-data/
- 拷贝到 `/etc/nikki/` + `/mnt/sda3/upper/etc/nikki/`（overlay 视图）
- IP 设 192.168.31.51
- 启动 mihomo，验证 web panel: `http://192.168.31.51:9090/ui/zashboard/`

### Stage 6：小米硬路由改纯 AP
- 关闭 DHCP / NAT（小米 WebUI）
- WAN 口保持空置
- LAN1 接 J4125 eth0 不变
- WiFi 名字密码保留

### Stage 7：联调
- 全设备上网测试（141/156/NAS）
- Nikki 代理测试
- IPv6 测试（如果有）

---

## 6. 风险与缓解

| 风险 | 概率 | 后果 | 缓解 |
|---|---|---|---|
| PVE 装机失败 | 低 | 起不来 | U 盘重装 2-3 次 |
| OpenWrt VM 网络配错 | 中 | 老大断网 | 主路由 VM 没起前回退小米拨号 |
| Nikki 迁移配置丢失 | 中 | 没代理 | 备份里有订阅链接 + mihomo dump |
| 小米 AP 模式配错 | 低 | Wi-Fi 断 | 小米恢复出厂设置即可 |
| J4125 Legacy BIOS 兼容 PVE 9 | 中 | 装不上 | 装机时选 Force MBR |

---

## 7. 关键修正记录（不要忘）

1. **光猫不要改桥接**——原样保留，光猫只做光电转换+ DHCP 192.168.1.x
2. **PPPoE 账号从小米搬到 PVE 主路由 VM**——光猫不动
3. **J4125 eth1 必须直通给主路由 VM**（vmbr1 不要桥接 WAN）
4. **J4125 是 Legacy BIOS**——PVE 9 装机选 Force MBR
5. **备份位置**：`/home/yu/pve-backup-20260802.tar.gz`（含 Nikki profiles + OpenWrt config）

---

## 8. 触发恢复点（什么时候想起这个方案）

- 老大说"开始搞 PVE"
- 老大说"重新规划网络"
- 灵爪 / 网管 / 任何场景提到"网络架构"

**恢复方式**：直接读这个文件（绝对路径在 § 7 备份位置附近）。
