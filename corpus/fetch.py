#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 SFC 官网拉取公开监管文件。

合规说明：
  · 仅下载 sfc.hk 官网公开发布的监管文件（codes / guidelines），不涉及任何登录或个人数据
  · 已核 https://www.sfc.hk/robots.txt —— 未禁止本脚本使用的路径
  · 单线程、带间隔，不对站点造成压力
"""
import hashlib, os, sys, time, urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")
BASE = "https://www.sfc.hk/-/media/EN/assets/components/codes/files-current/web/codes"
HERE = os.path.dirname(os.path.abspath(__file__))

DOCS = [
    ("sfc_code_of_conduct.pdf",
     "code-of-conduct-for-persons-licensed-by-or-registered-with-the-securities-and-futures-commission/"
     "code-of-conduct-for-persons-licensed-by-or-registered-with-the-securities-and-futures-commission.pdf",
     "SFC 操守准则（持牌人／注册人）"),
    ("sfc_fund_manager_code.pdf",
     "fund-manager-code-of-conduct/fund-manager-code-of-conduct.pdf",
     "SFC 基金经理操守准则"),
]

def fetch(fn: str, path: str, label: str) -> bool:
    out = os.path.join(HERE, fn)
    if os.path.exists(out) and os.path.getsize(out) > 50_000:
        print(f"  ✓ 已存在，跳过：{fn} ({os.path.getsize(out):,}B)")
        return True
    url = f"{BASE}/{path}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=90) as f:
            data = f.read()
    except Exception as e:
        print(f"  ✗ {label}: {type(e).__name__}: {e}")
        return False
    if data[:4] != b"%PDF":
        print(f"  ✗ {label}: 返回的不是 PDF（前 4 字节 {data[:4]!r}），可能官网改版，需重新定位链接")
        return False
    open(out, "wb").write(data)
    print(f"  ✓ {label}: {len(data):,}B  sha256={hashlib.sha256(data).hexdigest()[:16]}")
    return True

if __name__ == "__main__":
    print("拉取 SFC 公开监管文件…")
    ok = 0
    for fn, path, label in DOCS:
        if fetch(fn, path, label): ok += 1
        time.sleep(1.5)          # 对站点友好
    print(f"\n完成 {ok}/{len(DOCS)}")
    sys.exit(0 if ok else 1)
