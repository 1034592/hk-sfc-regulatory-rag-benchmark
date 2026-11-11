# -*- coding: utf-8 -*-
"""白皮书图表：指标对比柱状图 + 分类雷达化条形图。全部数据取自 results/metrics_rag.json。"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 中文字体：复用项目内已验证可用的思源/Noto 字体
for cand in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
             "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
             "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"):
    if os.path.exists(cand):
        font_manager.fontManager.addfont(cand)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=cand).get_name()
        break
plt.rcParams["axes.unicode_minus"] = False

NAVY, GREEN, AMBER, GREY, RED = "#0f3d6e", "#2e8b57", "#b8860b", "#8795a8", "#c0392b"
LABEL = {
    "C_dense_small":       ("bge-small\n纯稠密", AMBER),
    "D_hybrid_small_bm25": ("bge-small\n+ BM25", "#3d6ea8"),
    "A_dense_m3":          ("bge-m3\n纯稠密", NAVY),
    "F_hybrid_m3_bm25":    ("bge-m3\n+ BM25", RED),
    "B_dense_m3_rerank":   ("bge-m3\n+ Reranker", GREEN),
    "E_bm25":              ("BM25\n纯关键词", GREY),
}


def fig_metrics(cfg, out):
    keys = [k for k in LABEL if k in cfg]
    metrics = [("recall@1", "Recall@1"), ("recall@5", "Recall@5"),
               ("mrr@10", "MRR@10"), ("ndcg@5", "NDCG@5")]
    fig, axes = plt.subplots(1, 4, figsize=(14.6, 3.6))
    for ax, (mk, title) in zip(axes, metrics):
        vals = [cfg[k][mk] for k in keys]
        bars = ax.bar(range(len(keys)), vals,
                      color=[LABEL[k][1] for k in keys], width=.66, zorder=3)
        best = max(range(len(vals)), key=lambda i: vals[i])
        bars[best].set_edgecolor("#111"); bars[best].set_linewidth(1.6)
        for i, v in enumerate(vals):
            ax.text(i, v + 1.6, f"{v:.1f}", ha="center", va="bottom",
                    fontsize=8.6, fontweight="bold" if i == best else "normal")
        ax.set_title(title, fontsize=11, fontweight="bold", color=NAVY, pad=8)
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels([LABEL[k][0] for k in keys], fontsize=6.9)
        ax.set_ylim(0, 108); ax.set_ylabel("%", fontsize=8)
        ax.grid(axis="y", alpha=.25, zorder=0)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=190, bbox_inches="tight")
    plt.close(fig)
    print("  →", out)


def fig_latency(cfg, out):
    keys = [k for k in LABEL if k in cfg]
    lat = [cfg[k]["perf"].get("query_p50_ms", 0) for k in keys]
    rss = [cfg[k]["perf"].get("peak_rss_mb", 0) for k in keys]
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 3.4))
    for ax, vals, title, unit, log in ((axes[0], lat, "单查询延迟 p50", "ms", True),
                                       (axes[1], rss, "进程峰值内存", "MB", False)):
        ax.bar(range(len(keys)), vals, color=[LABEL[k][1] for k in keys], width=.62, zorder=3)
        for i, v in enumerate(vals):
            ax.text(i, v * (1.12 if log else 1.0) + (0 if log else max(vals) * .02),
                    f"{v:,.0f}" if v >= 10 else f"{v:.1f}", ha="center", va="bottom", fontsize=8.6)
        if log: ax.set_yscale("log")
        ax.set_title(f"{title}（{unit}）", fontsize=11, fontweight="bold", color=NAVY, pad=8)
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels([LABEL[k][0] for k in keys], fontsize=6.9)
        ax.grid(axis="y", alpha=.25, zorder=0)
        for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(out, dpi=190, bbox_inches="tight"); plt.close(fig)
    print("  →", out)


def fig_category(cfg, out):
    best = "B_dense_m3_rerank" if "B_dense_m3_rerank" in cfg else "A_dense_m3"
    cats = cfg[best]["by_category"]
    order = sorted(cats, key=lambda c: cats[c]["hit@5"])
    names = [f"{c}　{cats[c]['name']}" for c in order]
    series = [(best, LABEL[best][1]), ("E_bm25", GREY)]
    series = [(k, c) for k, c in series if k in cfg]
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    h = 0.38
    for si, (k, color) in enumerate(series):
        vals = [cfg[k]["by_category"][c]["hit@5"] for c in order]
        ypos = [i + (si - .5) * h for i in range(len(order))]
        ax.barh(ypos, vals, height=h, color=color, zorder=3,
                label=LABEL[k][0].replace("\n", " "))
        for y, v in zip(ypos, vals):
            ax.text(v + 1.2, y, f"{v:.0f}", va="center", fontsize=7.8)
    ax.set_yticks(range(len(order))); ax.set_yticklabels(names, fontsize=8.2)
    ax.set_xlim(0, 112); ax.set_xlabel("Hit@5（%）", fontsize=9)
    ax.set_title("分类命中率：最优配置 vs 关键词基线", fontsize=11.5,
                 fontweight="bold", color=NAVY, pad=10)
    ax.grid(axis="x", alpha=.25, zorder=0); ax.legend(fontsize=8.4, loc="lower right")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(out, dpi=190, bbox_inches="tight"); plt.close(fig)
    print("  →", out)


def main():
    res = json.load(open(os.environ.get("METRICS_JSON", os.path.join(ROOT, "results", "metrics_rag.json")), encoding="utf-8"))
    cfg = res["configs"]
    d = os.path.join(ROOT, "figs"); os.makedirs(d, exist_ok=True)
    fig_metrics(cfg, os.path.join(d, "fig_metrics.png"))
    fig_latency(cfg, os.path.join(d, "fig_cost.png"))
    fig_category(cfg, os.path.join(d, "fig_category.png"))


if __name__ == "__main__":
    main()
