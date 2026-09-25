#!/usr/bin/env python3
import json, re

INPUT = '/home/YDL/tvbox-repo/merged_32in1.json'

STD_CATS = [
    "动作片","喜剧片","爱情片","科幻片","恐怖片","剧情片","战争片",
    "国产剧","欧美剧","韩剧","日剧","港剧","台剧","泰剧","海外剧",
    "纪录片","大陆综艺","日韩综艺","港台综艺","欧美综艺",
    "国产动漫","日韩动漫","欧美动漫","动画片","港台动漫","海外动漫",
    "演唱会","体育赛事","篮球","足球","斯诺克","预告片","影视解说"
]

def clean_name(name):
    return re.sub(r'[\U0001F300-\U0001F9FF]', '', name).strip()

def site_key(s):
    return (s.get('key') or s.get('name') or '', s.get('api') or '')

with open(INPUT) as f:
    data = json.load(f)

sites = data['sites']
print('原始站点数:', len(sites))

# 1. 清理 emoji（保留原 name 用于去重判断，先记录原文）
for s in sites:
    s['_orig_name'] = s.get('name','')

# 2. 去重：用 (key, api) 组合判断，不以 name 为唯一依据
seen = set()
deduped = []
removed = 0
for s in sites:
    sk = site_key(s)
    if sk[0] and sk[1] and sk not in seen:
        seen.add(sk)
        deduped.append(s)
    elif sk[0] and sk[1]:
        print('  [去重]', s.get('name'), '|', s.get('api','')[:50])
        removed += 1
    else:
        # 没有 key 或 api 的也保留（本地脚本类）
        deduped.append(s)
sites = deduped
print('去重后:', len(sites), '(移除', removed, ')')

# 3. 清理 name 的 emoji（不影响 key/api）
for s in sites:
    s['name'] = clean_name(s.get('name',''))
    # 删除临时字段
    s.pop('_orig_name', None)

# 4. 补字段 + 类型标准化
for s in sites:
    # categories
    if 'categories' not in s and s.get('type') == 1:
        s['categories'] = STD_CATS
    # searchable/quickSearch/changeable
    is_direct = s.get('type') == 1 and s.get('api','').startswith(('http','./'))
    for f in ('searchable','quickSearch','changeable'):
        if f not in s:
            s[f] = 1 if is_direct else 0
        elif isinstance(s[f], str):
            s[f] = int(s[f])
    if 'type' in s:
        s['type'] = int(s['type'])

# 5. spider 路径
data['spider'] = './pg.jar'
data['sites'] = sites

with open(INPUT, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('写完，验证:', end=' ')
with open(INPUT) as f:
    t = json.load(f)
print('OK', len(t['sites']), 'sites')

# 统计
s_searchable = sum(1 for s in t['sites'] if s.get('searchable') == 1)
s_quick = sum(1 for s in t['sites'] if s.get('quickSearch') == 1)
s_change = sum(1 for s in t['sites'] if s.get('changeable') == 1)
print(' searchable=1:', s_searchable, '/', len(t['sites']))
print(' quickSearch=1:', s_quick, '/', len(t['sites']))
print(' changeable=1:', s_change, '/', len(t['sites']))
print(' 含 categories:', sum(1 for s in t['sites'] if 'categories' in s))
