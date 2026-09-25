# PVE + ROS CHR Patch + ImmortalWrt 双软路由方案（2026-08-16）

**创建日期**：2026-08-16
**作者**：龙爪（Hermes Agent）
**决策背景**：见 `pve-ros-patch-decision-20260816.md`
**对象机器**：CncTion J4125-4L @ 192.168.31.50（现 ImmortalWrt 24.10.4）

---

## 0. 装机方案（已定）

| 项 | 内容 |
|---|---|
| **宿主** | PVE 9.2-1（基于 Debian 12 + Linux 6.8 内核）|
| **VM 100 主路由** | **patched ROS CHR 7.23.3**（elseif/MikroTikPatch）|
| **VM 101 旁路由** | **ImmortalWrt 25.12.1**（最新稳定版，2026-07-06）+ **Nikki v1.26.1**（已支持 OpenWrt 25.12）|
| **小米硬路由** | 改纯 AP（WAN 空置）|
| **光猫** | 原样保留（不改桥接）|

## 1. 现状（改造前）

```
[光猫 路由模式 DHCP 192.168.1.x]
   ↓
[小米硬路由 192.168.31.1 (PPPoE拨号+NAT+DHCP+WiFi)]
   ↓
[旁路由 J4125 192.168.31.50 (Nikki透明代理)]
   ↓
[141/156/NAS]
```

## 2. 改造后架构

```
[光猫 路由模式 原样]
   ↓
[PVE 主机 J4125 192.168.31.50 管理口]
   ├─ VM 100 ROS CHR (192.168.31.1) — PPPoE + DHCP + DNS + NAT + 防火墙
   └─ VM 101 ImmortalWrt (192.168.31.51) — Nikki/mihomo 透明代理
   ↓ vmbr0 (LAN)
[小米硬路由 改纯 AP]
   ↓
[141/156/NAS]
```

## 3. 网口分配（关键修正）

| 物理口 | 接什么 | 用法 |
|---|---|---|
| **eth0** | 小米硬路由 LAN1 | **vmbr0**（LAN，所有 VM 共享）|
| **eth1** | 光猫 LAN1 | **vmbr1**（WAN，**直通给 ROS VM**）|
| **eth2** | 备用 | 后续 VM |
| **eth3** | 备用 | 后续 VM |

⚠️ **eth1 必须直通给 ROS VM**（PPPoE 拨号需要独占物理口，桥接不稳）。

## 4. VM 资源分配

| 资源 | ROS CHR VM (100) | ImmortalWrt VM (101) | PVE 宿主 | 剩余 |
|---|---|---|---|---|
| CPU | 2 核 | 2 核 | 系统自留 | 0 |
| RAM | 1 GB | 3 GB（mihomo 吃） | 0.5 GB | 7.5 GB 后续 VM |
| 磁盘 | 2 GB（CHR 128MB 已够） | 8 GB | 16 GB | 16 GB 数据 |

## 5. 物理接线（**老大手动 · 改接顺序**）

⚠️ **必须先改网关再改接线，避免断网盲区**

### 步骤

1. **141 网关改 192.168.31.1**（直连小米，绕过旁路由 Nikki，同网段仍能 SSH 进50）
2. 拔小米 WAN 口网线 → 网线 A 改插 J4125 eth1
3. 小米 WAN 口永远空置
4. J4125 物理装机（U 盘启动 PVE 装机）
5. PVE 装好后从 141 Web `https://192.168.31.50:8006` 远程操作

**断网窗口**：从步骤 2 开始到 ROS VM PPPoE 拨号成功（预计 1-2 小时）

## 6. 完整执行步骤

### Stage 0：备份（已完成 ✅）

| 文件 | 路径 |
|---|---|
| 原 PVE 方案文档 | `/home/yu/.hermes/memories/details/pve-dual-router-plan.md` |
| 实操方案 | `/home/yu/.hermes/skills/网管/references/pve-dual-router-actual-plan-20260802.md` |
| 旧备份 | `/home/yu/pve-backup-20260802.tar.gz`（29 MB）|
| **新备份（2026-08-16）** | `50:/mnt/sda3/pve-backup-20260816/`（nikki.tar.gz 13MB + uci 配置）|

### Stage 1：远程准备（**不断网，✅ 已完成**）

| 资源 | 路径 | 状态 |
|---|---|---|
| PVE 9.2-1 ISO | `/home/yu/pve-install/proxmox-ve_9.2-1.iso` | ✅ |
| patched ROS CHR 7.23.3 IMG | `50:/mnt/sda3/chr-7.23.3-patched-legacy-bios.img`（128 MB）| ✅ 已传 |
| patched ROS NPK | `50:/mnt/sda3/routeros-7.23.3.npk` | ✅ 已传 |
| ImmortalWrt 24.10.4 IMG | `50:/mnt/sda3/immortalwrt-25.12.1-x86-64-generic-ext4-combined.img`（解压 348MB）| ✅（从 `/home/yu/pve-install/` 解压）|
| Nikki 25.12 离线包 | `50:/mnt/sda3/nikki_x86_64-openwrt-25.12.tar.gz`（35 MB）| ✅ 已下载 |
| Ventoy 1.1.05 | `/tmp/ventoy-1.1.05/`（141 上）| ✅ 已下载 |
| Nikki 新备份 | `50:/mnt/sda3/pve-backup-20260816/` | ✅ |

### Stage 2：烧 Ventoy U盘（**老大动手 5 分钟**）

#### 2.1 准备 U盘

需要一个**至少 4GB** 的 U盘（建议 8GB+），**插到 141 的 USB 口**。

#### 2.2 烧 Ventoy（141 上执行）

```bash
# 1. 确认 U盘设备名
lsblk -d -o NAME,SIZE,MODEL,TRAN | grep usb

# 2. 假设是 /dev/sdb（**确认后**替换）
sudo bash /tmp/ventoy-1.1.05/Ventoy2Disk.sh -i -g /dev/sdb
# -g 表示 GPT（和50 的 Legacy BIOS+GPT 一致）
# Ventoy 会自动分区和格式化

# 3. 拷 ISO/IMG 到 U盘 Ventoy 分区
# Ventoy 会自动列出 U盘 mount 点（一般是 /mnt 或 /media/$USER/Ventoy）
VENTOY=$(ls /media/$USER/Ventoy 2>/dev/null || ls /run/media/$USER/Ventoy 2>/dev/null)
echo "Ventoy mount: $VENTOY"

cp /home/yu/pve-install/proxmox-ve_9.2-1.iso "$VENTOY/"
cp /home/yu/pve-install/immortalwrt-24.10.4-x86-64-generic-ext4-combined.img "$VENTOY/"
```

⚠️ Ventoy **不识别 .img 文件的 MBR 引导**——ROS CHR IMG 需要**直接 dd 到第二个分区**（或者用 Ventoy 的"无持久化"模式启动 IMG）。详见 Stage 4 修正。

### Stage 3：物理装机（**老大手动 10 分钟**）

1. U盘从 141 拔下 → 插到 50
2. 接 HDMI 显示器 + USB 键盘到 50
3. **拔掉 J4125 所有网线**（避免装机时误触发 PPPoE）
4. 重启 50 → 按 DEL/F2 进 BIOS
5. BIOS 设置：
   - **关闭 Secure Boot**（如果开了）
   - 启动顺序：U 盘第一
6. 保存重启 → 进 PVE 装机界面
7. 装机向导：

| 字段 | 值 |
|---|---|
| Target Harddisk | /dev/sda（64GB SSD）|
| Location + Time Zone | China / Asia/Shanghai |
| Password（root）| 老大自己定，记下来 |
| Email | 老大邮箱 |
| Management Interface | **eth0** |
| Hostname | `pve-router` |
| **IP Address（CIDR）** | **192.168.31.50/24** |
| **Gateway** | **192.168.31.1**（临时指向小米旧 IP）|
| **DNS Server** | **192.168.31.1** |

8. 拔 U 盘 + 重启
9. PVE 启动后，从 141 浏览器访问 `https://192.168.31.50:8006`

### Stage 4：远程建 VM（**141 上跑**）

#### 4.1 上传 patched ROS IMG 到 PVE local-lvm

```bash
# 把 50 上的 patched IMG 拉一份到 PVE 存储
sshpass -p '123456' ssh -o StrictHostKeyChecking=no root@192.168.31.50 \
  "dd if=/mnt/sda3/chr-7.23.3-patched-legacy-bios.img of=/dev/null"  # 触发缓存
# 或者直接 PVE 上传（推荐）：
# Web UI → local(pve) → ISO Images → Upload
# 上传 /home/yu/pve-install/ros/chr-7.23.3-patched-legacy-bios.img
```

#### 4.2 创建 VM 100（ROS CHR 主路由）

```bash
# PVE Web 操作（推荐）：
# 1. Create VM → ID 100 → Name: ros-main
# 2. System: BIOS = Default, Machine = i440fx (ROS 兼容性最好)
# 3. Disks: SCSI Controller = VirtIO Block（不要用 virtio-scsi-pci，ROS 不认）
#    Disk: 2GB（CHR 实际只占 128MB，2GB 留余量）
# 4. CPU: 2 cores
# 5. Memory: 1024 MB
# 6. Network:
#    - net0: VirtIO (paravirtualized) → vmbr0
#    - net1: VirtIO → vmbr1
# 7. 不需要 CD/DVD
# 8. Confirm
```

```bash
# 命令行版本（如果你想）
qm create 100 --name ros-main --memory 1024 --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --net1 virtio,bridge=vmbr1 \
  --scsihw virtio-scsi-single --scsi0 local-lvm:2 \
  --boot order=scsi0
```

#### 4.3 把 patched IMG 导入 VM 100

```bash
# 方法 A: 把 patched IMG 转成 VM 磁盘（推荐）
qm importdisk 100 chr-7.23.3-patched-legacy-bios.img local-lvm -format qcow2

# 方法 B: 用 dd 流式写入 VM 磁盘
# 在 PVE Web → VM 100 → Hardware → Unused Disk 0 → Edit → 设为 SCSI0
```

#### 4.4 创建 VM 101（ImmortalWrt 旁路由）

```bash
qm create 101 --name immortal-bypass --memory 3072 --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci --scsi0 local-lvm:8 \
  --ide2 local:iso/immortalwrt-25.12.1-x86-64-generic-ext4-combined.img,media=cdrom \
  --boot order=ide2
```

### Stage 5：ROS CHR VM 首次启动 + 配置

#### 5.1 启动 VM 100 → 控制台

```bash
# 141 上 VNC 进 VM 100 看到 ROS 启动界面
# 默认账号: admin / （空密码）
```

#### 5.2 初始 ROS 配置（CLI 脚本）

```routeros
# === 基本设置 ===
/system identity set name=ros-main
/user set [find name=admin] password=YOUR_PASSWORD_HERE

# === PPPoE 拨号（接 vmbr1）===
/interface pppoe-client
add name=pppoe-wan1 interface=ether2 user=051005333376 password=506900 \
    add-default-route=yes disabled=no use-peer-dns=no

# ether2 对应 vmbr1（WAN）
# ether1 对应 vmbr0（LAN）

# === LAN 接口 IP ===
/ip address
add address=192.168.31.1/24 interface=ether1 network=192.168.31.0

# === DHCP 服务 ===
/ip pool add name=lan-pool ranges=192.168.31.100-192.168.31.200
/ip dhcp-server
add name=lan-dhcp interface=ether1 address-pool=lan-pool disabled=no
/ip dhcp-server network
add address=192.168.31.0/24 gateway=192.168.31.1 dns-server=192.168.31.51

# === NAT（masquerade）===
/ip firewall nat
add chain=srcnat out-interface=pppoe-wan1 action=masquerade

# === 防火墙 ===
/ip firewall filter
add chain=input connection-state=established,related action=accept
add chain=input connection-state=invalid action=drop
add chain=input src-address=192.168.31.0/24 action=accept
add chain=input action=drop

# === DNS 转发给旁路由 Nikki ===
/ip dns
set servers=192.168.31.51 allow-remote-requests=yes cache-size=4096KiB

# === 保存 ===
/system backup save name=ros-initial
```

#### 5.3 验证 patched license

```routeros
/system license print
# 应该看到: software-id: 任意值; level: p-unlimited（如果打补丁成功）
# 如果还是 "free"，需要重做 patch
```

### Stage 6：ImmortalWrt VM 启动 + Nikki 恢复

#### 6.1 启动 VM 101 → ImmortalWrt 控制台

默认 IP: 192.168.31.1（LuCI 80 端口）—— 但这时和 ROS 主路由冲突。**先把 VM 101 LAN 临时设成其他 IP**：

```bash
# VNC/Console 进 VM 101
uci set network.lan.ipaddr='192.168.31.51'
uci set network.lan.netmask='255.255.255.0'
uci set network.lan.gateway='192.168.31.1'
uci set network.lan.dns='192.168.31.1'
uci commit network
/etc/init.d/network restart
```

#### 6.2 安装 Nikki（从离线包，**OpenWrt 25.12 用 apk**）

```bash
# 进 VM 101 控制台或 SSH
ssh root@192.168.31.51

# 方法 A: 从离线包安装（推荐，不依赖网络）
cd /tmp
wget -O nikki.tar.gz http://192.168.31.50/mnt/sda3/nikki_x86_64-openwrt-25.12.tar.gz
# 或 scp 传过来
tar -xzf nikki_x86_64-openwrt-25.12.tar.gz
apk add --allow-untrusted *.apk

# 方法 B: 从 GitHub release 直接装（需要外网）
wget -O - https://github.com/nikkinikki-org/OpenWrt-nikki/raw/refs/heads/main/install.sh | ash
```

#### 6.3 导入老的 Nikki 配置（从 50 备份）

```bash
# 从 50 拉备份
sshpass -p '123456' scp -o StrictHostKeyChecking=no \
  root@192.168.31.50:/mnt/sda3/pve-backup-20260816/nikki.tar.gz /tmp/

# 上传到 VM 101
scp -o StrictHostKeyChecking=no /tmp/nikki.tar.gz root@192.168.31.51:/tmp/

# 进 VM 101 恢复
ssh root@192.168.31.51
cd / && tar -xzf /tmp/nikki.tar.gz -C /
/etc/init.d/nikki restart
/etc/init.d/mihomo restart
```

#### 6.3 验证 Nikki 跑起来

```bash
# 浏览器访问 http://192.168.31.51:9090/ui/zashboard/
# 或者 curl 测试
curl -x http://192.168.31.51:7893 https://www.google.com -I
```

### Stage 7：小米硬路由改纯 AP

| 设置 | 现状 | 改为 |
|---|---|---|
| 接入方式 | WAN PPPoE 拨号 | **WAN 不插线** |
| DHCP | 启用 | **关闭** |
| NAT | 启用 | 关闭（路由模式改为桥接）|
| LAN IP | 192.168.31.1 | **改 192.168.31.2**（避 ROS 主路由冲突）|
| WiFi | 启用 | 启用（名字密码保留）|

### Stage 8：联调

1. **141 网关恢复**：`ip route replace default via 192.168.31.51`
2. **测试国内直连**：curl baidu.com
3. **测试代理**：curl -x http://192.168.31.51:7893 google.com
4. **speedtest**：https://www.speedtest.net/ 看实际带宽（应该跑满）
5. **ROS license 验证**：`/system license print` 应该 p-unlimited

## 7. 风险与缓解（修订版）

| 风险 | 概率 | 后果 | 缓解 |
|---|---|---|---|
| **patched CHR 启动后 license 检测失败** | 中 | 主路由跑不了 | 回退到 iKuaiOS 方案；或买 P1 license |
| **patched CHR 升级触发锁死** | 高（一旦官方升级）| 死锁 | **永远不升级 ROS**（除非必要）|
| **PPPoE 在 virtio 网卡上不稳** | 低 | 拨号掉线 | 改 eth1 直通（不用 virtio 桥接）|
| **i226 网卡在 PVE 6.8 内核下仍闪断** | 中 | eth0 link flap | 已知问题；可能需要强制 1G 协商 |
| **J4125 Legacy BIOS 兼容 PVE 9.2 GPT** | 低 | 装不上 | PVE 9.2 装机器已支持 GPT+Legacy |
| **Ventoy 不识别 patched IMG 的 MBR 引导** | 中 | IMG 起不来 | 用 `qm importdisk` 导入 PVE 虚拟磁盘，不需要 Ventoy |

## 8. 关键修正记录

1. **patched CHR IMG 已经集成补丁**——不需要额外打 option.npk
2. **Ventoy 只用来启动 PVE ISO + ImmortalWrt IMG**；patched CHR IMG 走 `qm importdisk` 直接导入
3. **eth1 必须直通给 ROS VM**（PPPoE 不能桥接）
4. **J4125 Legacy BIOS + GPT**——PVE 9.2 自动支持，不需要 Force MBR
5. **patched 版本号 7.23.3**（比官方 7.21.5 新一点，patched 跟得快）
6. **风险已记档** → `pve-ros-patch-decision-20260816.md`
7. **老大最少 10 分钟物理接触**（插 U 盘 + 进 BIOS + 装机向导）
8. **141 网关临时改 192.168.31.1**——绕开 Nikki 但保留 31 网段二层直连

## 9. 资源清单

| 资源 | 路径 | 校验 |
|---|---|---|
| PVE 9.2-1 ISO | `/home/yu/pve-install/proxmox-ve_9.2-1.iso` | ✅ SHA256 |
| patched CHR IMG（解压） | `50:/mnt/sda3/chr-7.23.3-patched-legacy-bios.img` | ✅ 已传 |
| patched ROS NPK | `50:/mnt/sda3/routeros-7.23.3.npk` | ✅ 已传 |
| ImmortalWrt 24.10.4 | `50:/mnt/sda3/immortalwrt-24.10.4-x86-64-generic-ext4-combined.img` | ✅ 已传 |
| 新备份（Nikki） | `50:/mnt/sda3/pve-backup-20260816/` | ✅ |
| Ventoy 1.1.05 | `/tmp/ventoy-1.1.05/`（141 上）| ✅ |

## 10. 触发恢复点

- 老大说"开始搞 PVE"
- 老大说"继续 PVE"
- 任何 PVE/网络/ROS 相关的提问

**恢复方式**：直接读本文 + Stage 命令即可执行。

---

**风险提醒**：老大你已明知 ROS patched 方案的法律/安全/稳定性风险（详见 decision 文档）。开始动手前请确认：
1. U盘已准备好（≥ 4GB）
2. 50 机器有 HDMI 显示器 + 键盘
3. 你有 10 分钟空闲时间 + 之后 1-2 小时可远程观察