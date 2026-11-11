# -*- coding: utf-8 -*-
"""
SFC 监管 RAG 双模检索基准（VPS CPU 版）
=======================================
执行环境：1 vCPU / 约 1.5 GB 可用物理内存 + 3.6 GB Swap。
bge-m3 与 reranker 的 fp32 权重各约 2.2 GB，单进程内连续加载必然触发 OOM，
故采用【分阶段独立进程】架构：每个阶段跑完即进程退出，由操作系统完整回收内存，
中间排名以 .npy 落盘，最后由 merge 阶段汇总。此设计亦使任一阶段失败可单独重跑。

阶段：
  bm25    E 纯关键词基线（rank_bm25）
  small   C bge-small-en-v1.5（384 维）纯稠密
  hybrid  D bge-small + BM25，RRF 融合（复用 bm25/small 的落盘排名）
  hybridm3 F bge-m3 + BM25，RRF 融合 —— 填补 2×2 消融设计中「强稠密 + 关键词」的空格
  m3      A bge-m3（1024 维）纯稠密
  rerank  B bge-m3 召回 top-20 → bge-reranker-v2-m3 重排
  merge     汇总为 results/metrics_rag.json

命中判定在条款级：同一 clause_id 的多个切块折叠为一个条款，取最佳名次。
"""
import json, os, sys, time, gc, re, argparse, statistics, resource
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.environ.get("MODEL_DIR", os.path.join(ROOT, "models"))
WORK = os.path.join(ROOT, "results", "_parts")
TOPK_POOL = 20
KS = (1, 3, 5, 10)
TOP_KEEP = 200


def peak_rss_mb():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def load_data():
    chunks = [json.loads(l) for l in open(os.path.join(ROOT, "data", "chunks_v2.jsonl"), encoding="utf-8")]
    ev = json.load(open(os.path.join(ROOT, "data", "eval_set_100.json"), encoding="utf-8"))
    return chunks, ev["questions"]


def clause_key(c):
    return f"{c['doc_id']}::{c['clause_id']}"


def fold(order, chunks):
    seen, out = set(), []
    for i in order:
        k = clause_key(chunks[int(i)])
        if k not in seen:
            seen.add(k); out.append(k)
    return out


def score_run(orders, chunks, questions):
    agg = {f"recall@{k}": [] for k in KS}
    agg.update({f"hit@{k}": [] for k in KS})
    agg["mrr@10"] = []; agg["ndcg@5"] = []
    strict5, per_cat = [], {}
    for order, q in zip(orders, questions):
        ranks = fold(order, chunks)
        gold = {f"{g['doc_id']}::{g['clause_id']}" for g in q["gold"]}
        for k in KS:
            found = len(gold & set(ranks[:k]))
            agg[f"recall@{k}"].append(found / len(gold))
            agg[f"hit@{k}"].append(1.0 if found else 0.0)
        rr = 0.0
        for i, r in enumerate(ranks[:10], 1):
            if r in gold: rr = 1.0 / i; break
        agg["mrr@10"].append(rr)
        dcg = sum(1.0 / np.log2(i + 1) for i, r in enumerate(ranks[:5], 1) if r in gold)
        idcg = sum(1.0 / np.log2(i + 1) for i in range(1, min(len(gold), 5) + 1))
        agg["ndcg@5"].append(dcg / idcg if idcg else 0.0)
        strict5.append(1.0 if gold <= set(ranks[:5]) else 0.0)
        c = q["category"]
        per_cat.setdefault(c, {"name": q["category_name"], "h": [], "m": []})
        per_cat[c]["h"].append(agg["hit@5"][-1]); per_cat[c]["m"].append(rr)
    out = {k: round(100 * statistics.fmean(v), 2) for k, v in agg.items()}
    out["strict_recall@5"] = round(100 * statistics.fmean(strict5), 2)
    out["by_category"] = {c: {"name": v["name"],
                              "hit@5": round(100 * statistics.fmean(v["h"]), 1),
                              "mrr@10": round(100 * statistics.fmean(v["m"]), 1)}
                          for c, v in sorted(per_cat.items())}
    return out


def save_part(name, payload):
    os.makedirs(WORK, exist_ok=True)
    json.dump(payload, open(os.path.join(WORK, f"{name}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"  → {WORK}/{name}.json", flush=True)


def tok(t):
    return re.findall(r'[a-z0-9]+', t.lower())


# ───────────────────────── 阶段实现 ─────────────────────────

def stage_bm25(chunks, questions):
    from rank_bm25 import BM25Okapi
    bm = BM25Okapi([tok(c["clause_title"] + " " + c["text"]) for c in chunks])
    orders, lat = [], []
    for q in questions:
        t0 = time.perf_counter()
        s = bm.get_scores(tok(q["question"]))
        o = np.argsort(-s)[:TOP_KEEP]
        lat.append((time.perf_counter() - t0) * 1000)
        orders.append(o)
    np.save(os.path.join(WORK, "order_bm25.npy"), np.asarray(orders, dtype=np.int32))
    save_part("E_bm25", {**score_run(orders, chunks, questions),
                         "perf": {"dim": None, "query_p50_ms": round(statistics.median(lat), 2),
                                  "query_p95_ms": round(sorted(lat)[int(len(lat)*.95)], 2),
                                  "peak_rss_mb": peak_rss_mb()}})


def stage_dense(chunks, questions, model_dir, tag, batch, max_len):
    import torch
    torch.set_num_threads(1)
    from sentence_transformers import SentenceTransformer
    t0 = time.perf_counter()
    m = SentenceTransformer(os.path.join(MODELS, model_dir), device="cpu")
    m.max_seq_length = max_len
    load_s = time.perf_counter() - t0
    texts = [(c["clause_title"] + "\n" + c["text"]).strip() for c in chunks]
    t0 = time.perf_counter()
    D = m.encode(texts, batch_size=batch, normalize_embeddings=True,
                 convert_to_numpy=True, show_progress_bar=False).astype(np.float32)
    index_s = time.perf_counter() - t0
    print(f"  语料编码完成 {D.shape} 用时 {index_s:.1f}s", flush=True)
    lat, Q = [], np.zeros((len(questions), D.shape[1]), dtype=np.float32)
    for i, q in enumerate(questions):
        t0 = time.perf_counter()
        Q[i] = m.encode([q["question"]], normalize_embeddings=True,
                        convert_to_numpy=True, show_progress_bar=False)[0]
        lat.append((time.perf_counter() - t0) * 1000)
    del m; gc.collect()
    orders = [np.argsort(-(D @ Q[i]))[:TOP_KEEP] for i in range(len(questions))]
    np.save(os.path.join(WORK, f"order_{tag}.npy"), np.asarray(orders, dtype=np.int32))
    save_part(f"{'C_dense_small' if tag=='small' else 'A_dense_m3'}",
              {**score_run(orders, chunks, questions),
               "perf": {"dim": int(D.shape[1]), "load_s": round(load_s, 2),
                        "index_s": round(index_s, 1), "batch": batch, "max_len": max_len,
                        "query_p50_ms": round(statistics.median(lat), 2),
                        "query_p95_ms": round(sorted(lat)[int(len(lat)*.95)], 2),
                        "peak_rss_mb": peak_rss_mb()}})


def _rrf_fuse(chunks, questions, dense_npy, dense_part, out_name):
    """稠密排名与 BM25 排名的 RRF 融合。两路各取 top-100，k=60。"""
    bm = np.load(os.path.join(WORK, "order_bm25.npy"))
    dn = np.load(os.path.join(WORK, dense_npy))
    E = json.load(open(os.path.join(WORK, "E_bm25.json"), encoding="utf-8"))
    Dp = json.load(open(os.path.join(WORK, dense_part), encoding="utf-8"))
    orders = []
    for i in range(len(questions)):
        sc = {}
        for rl in (dn[i][:100], bm[i][:100]):
            for r, idx in enumerate(rl, 1):
                sc[int(idx)] = sc.get(int(idx), 0.0) + 1.0 / (60 + r)
        orders.append([i2 for i2, _ in sorted(sc.items(), key=lambda x: -x[1])][:TOP_KEEP])
    # 融合后各题的唯一候选数可能少于 TOP_KEEP，以 -1 右填充为等长矩阵
    padded = [o + [-1] * (TOP_KEEP - len(o)) for o in orders]
    np.save(os.path.join(WORK, f"order_{out_name}.npy"),
            np.asarray(padded, dtype=np.int32))
    save_part(out_name,
              {**score_run(orders, chunks, questions),
               "perf": {"dim": Dp["perf"]["dim"], "fusion": "RRF k=60，两路各取 top-100",
                        "query_p50_ms": round(Dp["perf"]["query_p50_ms"] + E["perf"]["query_p50_ms"], 2),
                        "peak_rss_mb": max(Dp["perf"]["peak_rss_mb"], E["perf"]["peak_rss_mb"])}})


def stage_hybrid(chunks, questions):
    _rrf_fuse(chunks, questions, "order_small.npy", "C_dense_small.json", "D_hybrid_small_bm25")


def stage_hybrid_m3(chunks, questions):
    _rrf_fuse(chunks, questions, "order_m3.npy", "A_dense_m3.json", "F_hybrid_m3_bm25")


def stage_rerank(chunks, questions):
    import torch
    torch.set_num_threads(1)
    from sentence_transformers import CrossEncoder
    m3 = np.load(os.path.join(WORK, "order_m3.npy"))
    A = json.load(open(os.path.join(WORK, "A_dense_m3.json"), encoding="utf-8"))
    t0 = time.perf_counter()
    ce = CrossEncoder(os.path.join(MODELS, "bge-reranker-v2-m3"), device="cpu", max_length=512)
    load_s = time.perf_counter() - t0
    orders, lat = [], []
    for n, q in enumerate(questions, 1):
        cand = [int(x) for x in m3[n-1][:TOPK_POOL]]
        pairs = [(q["question"], (chunks[i]["clause_title"] + "\n" + chunks[i]["text"])[:1500]) for i in cand]
        t0 = time.perf_counter()
        s = ce.predict(pairs, batch_size=4, show_progress_bar=False)
        lat.append((time.perf_counter() - t0) * 1000)
        orders.append([cand[j] for j in np.argsort(-np.asarray(s))])
        np.save(os.path.join(WORK, "order_rerank.npy"),
                np.asarray([o + [-1]*(TOPK_POOL-len(o)) for o in orders], dtype=np.int32))
        if n % 10 == 0:
            print(f"  重排进度 {n}/{len(questions)}  均耗 {statistics.fmean(lat)/1000:.1f}s/题", flush=True)
    del ce; gc.collect()
    save_part("B_dense_m3_rerank",
              {**score_run(orders, chunks, questions),
               "perf": {"dim": A["perf"]["dim"], "recall_pool": TOPK_POOL,
                        "load_s": round(load_s, 2),
                        "rerank_p50_ms": round(statistics.median(lat), 2),
                        "rerank_p95_ms": round(sorted(lat)[int(len(lat)*.95)], 2),
                        "query_p50_ms": round(A["perf"]["query_p50_ms"] + statistics.median(lat), 2),
                        "peak_rss_mb": peak_rss_mb()}})


def stage_rescore(chunks, questions):
    """标注修正后重新计分：复用已落盘的排名，不重新编码语料。"""
    import numpy as _np
    jobs = [("E_bm25", "order_bm25.npy"), ("C_dense_small", "order_small.npy"),
            ("A_dense_m3", "order_m3.npy"), ("B_dense_m3_rerank", "order_rerank.npy")]
    for name, npy in jobs:
        pj = os.path.join(WORK, f"{name}.json"); pn = os.path.join(WORK, npy)
        if not (os.path.exists(pj) and os.path.exists(pn)):
            print(f"  跳过 {name}（缺排名或分值文件）", flush=True); continue
        perf = json.load(open(pj, encoding="utf-8"))["perf"]
        arr = _np.load(pn)
        orders = [[int(x) for x in row if int(x) >= 0] for row in arr]
        save_part(name, {**score_run(orders, chunks, questions), "perf": perf})
    # 两个混合档由两路排名现场重算
    if os.path.exists(os.path.join(WORK, "order_bm25.npy")):
        if os.path.exists(os.path.join(WORK, "order_small.npy")):
            stage_hybrid(chunks, questions)
        if os.path.exists(os.path.join(WORK, "order_m3.npy")):
            stage_hybrid_m3(chunks, questions)


def stage_merge(chunks, questions):
    import platform, subprocess
    order = ["A_dense_m3", "B_dense_m3_rerank", "C_dense_small", "D_hybrid_small_bm25",
             "E_bm25", "F_hybrid_m3_bm25"]
    cfg = {}
    for name in order:
        p = os.path.join(WORK, f"{name}.json")
        if os.path.exists(p):
            cfg[name] = json.load(open(p, encoding="utf-8"))
        else:
            print(f"  ⚠ 缺少 {name}", flush=True)
    mem = subprocess.run(["free", "-m"], capture_output=True, text=True).stdout.split("\n")[1].split()
    res = {"env": {"host": "VPS", "cpu_cores": os.cpu_count(),
                   "ram_total_mb": int(mem[1]), "swap_total_mb": int(
                       subprocess.run(["free","-m"],capture_output=True,text=True).stdout.split("\n")[2].split()[1]),
                   "device": "cpu", "python": platform.python_version()},
           "corpus": {"chunks": len(chunks), "clauses": len({clause_key(c) for c in chunks}),
                      "source": "chunks_v2.jsonl"},
           "n_questions": len(questions), "configs": cfg}
    try:
        import torch; res["env"]["torch"] = torch.__version__
    except Exception: pass
    out = os.path.join(ROOT, "results", "metrics_rag.json")
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    hdr = f"{'配置':26}{'R@1':>7}{'R@5':>7}{'Hit@1':>7}{'Hit@5':>7}{'MRR':>7}{'NDCG5':>7}{'p50ms':>9}{'RSS MB':>9}"
    print("\n" + hdr); print("-" * len(hdr))
    for k, v in cfg.items():
        print(f"{k:26}{v['recall@1']:>7}{v['recall@5']:>7}{v['hit@1']:>7}{v['hit@5']:>7}"
              f"{v['mrr@10']:>7}{v['ndcg@5']:>7}{v['perf'].get('query_p50_ms',0):>9}"
              f"{v['perf'].get('peak_rss_mb',0):>9}")
    print("\n→", out, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["bm25","small","hybrid","m3","hybridm3",
                                  "rerank","rescore","merge"])
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    chunks, questions = load_data()
    print(f"[{a.stage}] 语料 {len(chunks)} 切块 / "
          f"{len({clause_key(c) for c in chunks})} 条款 ｜ {len(questions)} 题", flush=True)
    t0 = time.perf_counter()
    if   a.stage == "bm25":   stage_bm25(chunks, questions)
    elif a.stage == "small":  stage_dense(chunks, questions, "bge-small-en-v1.5", "small", 16, 512)
    elif a.stage == "hybrid": stage_hybrid(chunks, questions)
    elif a.stage == "m3":     stage_dense(chunks, questions, "bge-m3", "m3", 4, 512)
    elif a.stage == "hybridm3":stage_hybrid_m3(chunks, questions)
    elif a.stage == "rerank": stage_rerank(chunks, questions)
    elif a.stage == "rescore":stage_rescore(chunks, questions)
    elif a.stage == "merge":  stage_merge(chunks, questions)
    print(f"[{a.stage}] 完成，用时 {time.perf_counter()-t0:.1f}s，峰值 RSS {peak_rss_mb()} MB", flush=True)


if __name__ == "__main__":
    main()
