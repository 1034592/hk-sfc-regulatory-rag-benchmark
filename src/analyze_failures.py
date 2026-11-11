# -*- coding: utf-8 -*-
"""
失败案例归因
============
定义：若某题的任一 gold 条款在【四个基础配置】（BM25 / bge-small / 混合 / bge-m3）
的 top-5 条款中均未出现，则记为「全配置未命中」。
重排配置 B 是对 A 的 top-20 候选重排，A 的 top-20 若无 gold，B 必然同样未命中，
因此以四个基础配置界定失败集不会遗漏。
输出 results/failure_analysis.json，供白皮书正文引用。
"""
import json, os, io
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, "results", "_parts")

chunks = [json.loads(l) for l in io.open(os.path.join(ROOT, "data", "chunks_v2.jsonl"), encoding="utf-8")]
qs = json.load(io.open(os.path.join(ROOT, "data", "eval_set_100.json"), encoding="utf-8"))["questions"]


def fold(order):
    seen, out = set(), []
    for i in order:
        k = f"{chunks[int(i)]['doc_id']}::{chunks[int(i)]['clause_id']}"
        if k not in seen:
            seen.add(k); out.append(k)
    return out


bm = np.load(os.path.join(W, "order_bm25.npy"))
sm = np.load(os.path.join(W, "order_small.npy"))
m3 = np.load(os.path.join(W, "order_m3.npy"))
hy = []
for i in range(len(qs)):
    sc = {}
    for rl in (sm[i][:100], bm[i][:100]):
        for r, idx in enumerate(rl, 1):
            sc[int(idx)] = sc.get(int(idx), 0.0) + 1.0 / (60 + r)
    hy.append([x for x, _ in sorted(sc.items(), key=lambda t: -t[1])][:200])

CONF = {"E_bm25": bm, "C_dense_small": sm, "A_dense_m3": m3, "D_hybrid": hy}

rows, per_conf_only = [], {k: 0 for k in CONF}
for i, q in enumerate(qs):
    gold = {f"{g['doc_id']}::{g['clause_id']}" for g in q["gold"]}
    hit = {}
    for name, orders in CONF.items():
        top5 = set(fold(orders[i])[:5])
        hit[name] = bool(gold & top5)
    if not any(hit.values()):
        rows.append({"qid": q["qid"], "category": q["category"],
                     "category_name": q["category_name"], "question": q["question"],
                     "gold": [f"{g['doc_id']}::{g['clause_id']}" for g in q["gold"]],
                     "difficulty": q["difficulty"]})
    for name in CONF:
        if hit[name] and sum(hit.values()) == 1:
            per_conf_only[name] += 1

from collections import Counter
by_cat = Counter(r["category_name"] for r in rows)
out = {"definition": "四个基础配置（BM25 / bge-small / bge-small+BM25 / bge-m3）的 top-5 条款中均无任一 gold 条款",
       "n_total": len(qs), "n_failed": len(rows),
       "fail_rate_pct": round(100 * len(rows) / len(qs), 1),
       "by_category": dict(by_cat),
       "unique_save": {k: v for k, v in per_conf_only.items()},
       "cases": rows}
json.dump(out, io.open(os.path.join(ROOT, "results", "failure_analysis.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"全配置未命中 {len(rows)}/{len(qs)} 题（{out['fail_rate_pct']}%）")
print("分类分布：", dict(by_cat))
print("仅被单一配置救回的题数：", per_conf_only)
for r in rows[:12]:
    print(f"  {r['qid']} [{r['category']}] gold={r['gold']}  {r['question'][:74]}")
