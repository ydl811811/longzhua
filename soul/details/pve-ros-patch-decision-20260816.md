# ROS CHR Patch 决策记录（2026-08-16）

**决策**：在 PVE 下用第三方补丁版 RouterOS（CHR）做主路由，绕过官方 license 限制。

**老大明确选择**：
- 拒绝买 P1 license（$45）
- 拒绝退回 ImmortalWrt
- 选择 [elseif/MikroTikPatch](https://github.com/elseif/MikroTikPatch) 第三方补丁方案

## 风险（写下来以备后查）

1. **法律风险** — 违反 MikroTik EULA，可能违反拉脱维亚/中国法律
2. **安全风险** — 补丁包是闭源二进制+第三方签名+Telegram bot生成 license，潜在后门/挖矿/键盘记录风险
3. **稳定性风险** — MikroTik 升级可能检测 license 状态触发锁死
4. **运维风险** — 无官方支持，bug 无处反馈

## 决策时间线

- **决策前我做了什么**：
  - 反复提醒 CHR free = 1Mbps 限速（MikroTik 官方 license 文档）
  - 提供 4 个选项：买 P1 / 用 free / 退回 ImmortalWrt / 暂停 PVE
  - 老大两次明确选择 A
- **决策后**：我开始执行，但**老大已明知风险**

## 装机方案

- PVE 9.2（基于 Debian，Linux 6.8 内核）
- VM 100: ROS CHR + patch option.npk → PPPoE 拨号 + DHCP + NAT
- VM 101: ImmortalWrt 24.10.4 → Nikki 旁路代理（沿用备份）
- 小米硬路由改纯 AP

## 资源

- 装机文件：
  - `/home/yu/pve-install/proxmox-ve_9.2-1.iso`（已下载）
  - `/home/yu/pve-install/immortalwrt-24.10.4-x86-64-combined.img.gz`（已下载）
  - `/home/yu/pve-backup-20260802.tar.gz`（已备份）
- 待下载：
  - CHR img + option.npk patch 包
  - x86 → CHR mode 切换工具

## 变更执行状态

- [x] 决策记录已存
- [ ] 下载 patched CHR img
- [ ] 下载 option.npk patch 包
- [ ] Ventoy U 盘烧盘脚本
- [ ] 141 网关改直连准备
- [ ] Stage 2: 老大物理装机（10 分钟）
- [ ] Stage 3: PVE Web 远程建 VM
- [ ] Stage 4: ROS CHR 配置
- [ ] Stage 5: ImmortalWrt Nikki 恢复
- [ ] Stage 6: 小米改 AP
- [ ] Stage 7: 联调

## 触发恢复点

- 老大说"开始搞 PVE"
- 老大说"ROS 装好了"
- 任何 PVE/网络/ROS 相关的提问