#!/bin/sh
# 旁路由（ImmortalWrt 192.168.31.50）Overlay 扩容脚本
# 适用：将 /overlay 从 loop0(288M) 切到 /dev/sda4 (48G)
# 实测成功：2026-07-31（脚本会改 fstab + cp overlay 内容到 sda4，最后需要手动 reboot）
# 注意：reboot 这一步 agent 不能自动跑（系统黑名单），需要老大 SSH 上手动执行

set -e

echo "🔵 [1/6] 创建临时挂载目录"
mkdir -p /mnt/new_overlay

echo "🔵 [2/6] 挂载 /dev/sda4（48G 已格式化 ext4）"
mount /dev/sda4 /mnt/new_overlay

echo "🔵 [3/6] 复制当前 overlay 内容到 sda4"
cp -rp /overlay/. /mnt/new_overlay/
echo "复制完成："
du -sh /mnt/new_overlay

echo "🔵 [4/6] 重写 /etc/config/fstab（target /overlay 指向 sda4）"
cat > /etc/config/fstab <<'FSTAB_EOF'
config global
	option anon_swap '0'
	option anon_mount '1'
	option auto_swap '1'
	option auto_mount '1'
	option delay_root '5'
	option check_fs '0'

config mount
	option target '/overlay'
	option device '/dev/sda4'
	option fstype 'ext4'
	option options 'rw,sync'
	option enabled '1'
	option enabled_fsck '1'

config mount
	option target '/mnt/sda4'
	option uuid 'f12dce33-f89a-4478-ae8f-28ca2af9ffc5'
	option enabled '1'

config mount
	option target '/boot'
	option uuid '1234-ABCD'
	option enabled '0'

config mount
	option target '/mnt/sda3'
	option uuid 'ba92341c-598d-4e7d-bd12-287f47a4ae1b'
	option enabled '0'
FSTAB_EOF

echo "🔵 [5/6] 验证 fstab"
echo "--- 新 fstab 内容 ---"
cat /etc/config/fstab

echo ""
echo "🔵 [6/6] 卸载临时挂载"
umount /mnt/new_overlay

echo ""
echo "=== ✅ 脚本执行完成 ==="
echo "下一步：手动执行 reboot"
echo "  ssh root@192.168.31.50 'reboot'"
echo ""
echo "重启后验证："
echo "  df -h /overlay"
echo "  # 期望：/dev/sda4  48.2G  564M  45G  /overlay"