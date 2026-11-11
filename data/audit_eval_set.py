# -*- coding: utf-8 -*-
"""
评测集标注体检
==============
对每题计算「问题关键词」与「gold 条款正文 + 标题」的覆盖度。
覆盖度低的题目不一定错，但须人工复核——Q040 的标注错误即由此类信号发现。
"""
import json, io, os, re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ch = [json.loads(l) for l in io.open(os.path.join(ROOT, "data", "chunks_v2.jsonl"), encoding="utf-8")]
qs = json.load(io.open(os.path.join(ROOT, "data", "eval_set_100.json"), encoding="utf-8"))["questions"]

by_clause = {}
for c in ch:
    k = (c["doc_id"], c["clause_id"])
    by_clause.setdefault(k, []).append(c)

STOP = set("""what which who whom when where how why must should may can is are was were be been
the a an of to in on for with by from at as and or not no any all its it this that these those
under must_be does do done required requirement requirements apply applies applicable
licensed registered person persons fund manager code paragraph provision""".split())

def kw(t):
    return {w for w in re.findall(r'[a-z]{3,}', t.lower()) if w not in STOP}

rows = []
for q in qs:
    k = kw(q["question"])
    body = " ".join((c["clause_title"] + " " + c["text"])
                    for g in q["gold"] for c in by_clause[(g["doc_id"], g["clause_id"])])
    bk = kw(body)
    cov = len(k & bk) / max(len(k), 1)
    rows.append((cov, q, sorted(k - bk)))

rows.sort(key=lambda x: x[0])
print(f"关键词覆盖度最低的 15 题（需人工复核）：\n")
for cov, q, miss in rows[:15]:
    gold = "、".join(f"{g['clause_id']}" for g in q["gold"])
    print(f"  {q['qid']} cov={cov:.2f} [{q['category']}] gold={gold}")
    print(f"     Q: {q['question'][:92]}")
    print(f"     未覆盖词: {miss[:8]}")
print(f"\n覆盖度分布：{Counter(round(c*10)/10 for c,_,_ in rows).most_common()}")
print(f"中位覆盖度：{sorted(c for c,_,_ in rows)[len(rows)//2]:.2f}")
