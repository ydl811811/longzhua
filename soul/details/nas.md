# NAS（飞牛 FNOS / OpenClaw 灵爪）

## 基本信息

- IP: 192.168.31.10
- 用户: **YDL（大写）** / 密码: YDL32021976w
- SSH key: `~/.ssh/id_ed25519_new`（指纹 SHA256:pafPLXWBgqGllTrFdp+Rt8R4hWacuYPvJnF0OT5sZKs）
- FNOS: 1.1.3102 / Kernel: 6.18.18-trim
- 挂载点: **/vol1**（btrfs）⚠️ **不是** /volume1（群晖风格！）
- 用户家目录: /vol1/1000/
- 下载目录: /vol1/1000/下载/
- 已存在子目录: 影视/、程序/、VPS&OPENCLAW/、vps信息/
- **新文件默认推到 /vol1/1000/下载/程序/**

## SSH 快速诊断命令

```bash
# 基础连通性
sshpass -p 'YDL32021976w' ssh -o StrictHostKeyChecking=no YDL@192.168.31.10 "echo ok"

# sudo 自动化（NAS 的 sudo 无 TTY 限制，OK）
sshpass -p 'YDL32021976w' ssh YDL@192.168.31.10 \
  'echo "YDL32021976w" | sudo -S <命令>'

# **第一动作：先验证 IP** — ping + arp 确认 MAC 正确
ping 192.168.31.10
arp -n 192.168.31.10
```

## ⚠️ 关键陷阱

- **永远不要暴力枚举 NAS 凭据**（FNOS 3-5 次错误后封禁）
- **用户名大小写是根因**：`YDL` 大写，不是 `ydl`
- PAM 日志关键信号：`sudo tail -30 /var/log/auth.log | grep -i ssh`
- **winbind 陷阱**：NAS 把本地用户 ydl 误认为域用户，密码认证必失败；用 key 登录
- **authorized_keys 路径陷阱**：sudo 跑 echo 会写到 `/root/.ssh/`；必须用 `/home/YDL/.ssh/authorized_keys` 或 `sudo -u ydl`

## ⚠️ 挂载点陷阱

错误路径 → 正确路径：
| 错误 | 正确 |
|---|---|
| /volume1/我的文件/下载/ | /vol1/1000/下载/ |
| /volume1/homes/admin/ | /vol1/1000/ |

## Docker 项目

- compose 根目录：`/home/YDL/docker-compose/`（不是 `/etc/docker/compose`）
- 现有容器：xunlei（迅雷）、tvbox-repo、sub-store、g-box、iptv、librespeed
- 端口约定：g-box=4567, tvbox-repo=19999, librespeed=8989

## TV-box 服务

- 老大订阅：`http://NAS:19999/merged_32in1.json`
- 服务文件：`~/.config/systemd/user/tvbox-http.service`（**用户级 systemd**，不要 root）
- 工作目录：`/home/YDL/tvbox-repo/`

## 灵爪 (OpenClaw) 信息 → 见 details/lingzhua.md

> nas.md 只记 NAS 物理信息（IP/挂载/Docker/TV-box），灵爪/OpenClaw 详细配置全部去 lingzhua.md（含 Gateway/进程/SSH 暗号/协作分工铁律）。

## 向 NAS 推文件的标准流程

```bash
# 推文件
sshpass -p 'YDL32021976w' scp <本地文件> YDL@192.168.31.10:/vol1/1000/下载/程序/<file>

# 验证（双向 sha256）
sshpass -p 'YDL32021976w' ssh YDL@192.168.31.10 \
  "ls -lh /vol1/1000/下载/程序/<file>; sha256sum /vol1/1000/下载/程序/<file>"
```

辅助脚本：`scripts/nas-push.sh <本地文件> [远端子目录]`