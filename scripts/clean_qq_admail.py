#!/usr/bin/env python3
"""
QQ邮箱广告邮件清理脚本
每周运行一次，清理收件箱中的过期邮件。

清理规则：
1. 超过2年的邮件（白名单除外）
2. 已知广告发件人（SolarWinds、AdGuard、NVIDIA等）
"""

import imaplib
import ssl
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import datetime
import re
import sys

# ====== 配置 ======
IMAP_HOST = "imap.qq.com"
IMAP_PORT = 993
USER = "452512209@qq.com"
PASSWORD = "lbxspwhcsljtcbcc"

# 2年期限
CUTOFF = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=730)

# 广告发件人匹配
AD_SENDERS = [
    "solarwinds",
    "adguard",
    "nvidia",
]

# 白名单——这些发件人的邮件不会被删除
WHITELIST_SENDERS = [
    "中信银行",
    "浦发银行",
    "广发银行",
]


def decode_mime_header(header_value):
    if header_value is None:
        return ""
    decoded_parts = decode_header(header_value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return " ".join(result)


def get_sender(from_header):
    decoded = decode_mime_header(from_header)
    match = re.search(r'<([^>]+@[^>]+)>', decoded)
    if match:
        return match.group(1), decoded
    return decoded.strip(), decoded.strip()


def is_whitelisted(text):
    for wl in WHITELIST_SENDERS:
        if wl.lower() in text.lower():
            return True
    return False


def parse_date(date_str):
    """解析邮件Date头，失败返回None"""
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    print(f"[{now.isoformat()}] 开始清理QQ邮箱...")
    print(f"📅 2年截止日期: {CUTOFF.date()}")

    ctx = ssl.create_default_context()
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
    mail.login(USER, PASSWORD)
    print("✅ IMAP 登录成功")

    mail.select("INBOX")
    result, data = mail.search(None, "ALL")
    if result != "OK":
        print("❌ 搜索邮件失败")
        mail.logout()
        return

    email_ids = data[0].split()
    total = len(email_ids)
    print(f"📧 收件箱共 {total} 封邮件")

    delete_ids = []
    delete_log = []

    for eid in email_ids:
        result, msg_data = mail.fetch(eid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
        if result != "OK":
            continue

        raw_header = msg_data[0][1]
        msg = email.message_from_bytes(raw_header)

        from_header = msg.get("From", "")
        subject_header = msg.get("Subject", "")
        date_header = msg.get("Date", "")

        from_addr, from_display = get_sender(from_header)
        subject = decode_mime_header(subject_header)
        full_text = f"{from_addr} {from_display} {subject}".lower()

        # 白名单跳过
        if is_whitelisted(full_text):
            continue

        # 自己发给自己的跳过
        if "452512209@qq.com" in full_text:
            continue

        should_delete = False
        reason = ""

        # 规则1：超过2年
        if date_header:
            dt = parse_date(date_header)
            if dt and dt < CUTOFF:
                should_delete = True
                days_old = (now - dt).days
                reason = f"超2年({days_old}天)"

        # 规则2：广告发件人（不限时间）
        if not should_delete:
            for sender in AD_SENDERS:
                if sender.lower() in full_text:
                    should_delete = True
                    reason = "广告发件人"
                    break

        if should_delete:
            delete_ids.append(eid)
            delete_log.append({
                "reason": reason,
                "from": from_display[:60],
                "subject": subject[:80],
                "date": date_header[:30] if date_header else "?",
            })

    if not delete_ids:
        print("✅ 没有需要清理的邮件")
    else:
        print(f"\n📋 发现 {len(delete_ids)} 封邮件待清理：")
        # 按原因分组展示
        old_emails = [e for e in delete_log if e["reason"].startswith("超2年")]
        ad_emails = [e for e in delete_log if e["reason"] == "广告发件人"]
        if old_emails:
            print(f"\n  📅 超2年 ({len(old_emails)}封)：")
            for e in old_emails:
                print(f"    [{e['date']}] [{e['from']}] {e['subject']}")
        if ad_emails:
            print(f"\n  📢 广告发件人 ({len(ad_emails)}封)：")
            for e in ad_emails:
                print(f"    [{e['date']}] [{e['from']}] {e['subject']}")

        for eid in delete_ids:
            mail.store(eid, "+FLAGS", "\\Deleted")
        mail.expunge()
        print(f"\n✅ 本次清理: {len(delete_ids)} 封邮件已删除")

    # 清理 Junk 文件夹
    mail.select("Junk")
    result, junk_data = mail.search(None, "ALL")
    if result == "OK" and junk_data[0]:
        junk_ids = junk_data[0].split()
        if junk_ids:
            print(f"📬 Junk 文件夹有 {len(junk_ids)} 封邮件，一并清理")
            for eid in junk_ids:
                mail.store(eid, "+FLAGS", "\\Deleted")
            mail.expunge()
            print(f"✅ Junk 文件夹 {len(junk_ids)} 封已清理")
    else:
        print("📬 Junk 文件夹为空")

    mail.logout()
    print(f"[{datetime.datetime.now().isoformat()}] 清理完成")


if __name__ == "__main__":
    main()