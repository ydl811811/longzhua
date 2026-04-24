#!/usr/bin/expect -f

set password "YDL32021976w"
set host "192.168.31.10"
set user "YDL"

spawn ssh -o StrictHostKeyChecking=no $user@$host

expect {
    "*password:" {
        send "$password\r"
        exp_continue
    }
    "$user@" {
        send "echo '✅ SSH连接成功'\r"
    }
    timeout {
        send_user "连接超时\n"
        exit 1
    }
}

# 保持交互
interact