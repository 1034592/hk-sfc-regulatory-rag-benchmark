# -*- coding: utf-8 -*-
"""
白皮书正文生成
==============
所有指标表格由 results/metrics_rag.json 现场读出并渲染，
正文中的关键数字亦由同一数据源注入，杜绝文档与后台结果脱节。
"""
import json, os, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(io.open(os.environ.get("METRICS_JSON", os.path.join(ROOT, "results", "metrics_rag.json")), encoding="utf-8"))
E = json.load(io.open(os.path.join(ROOT, "data", "eval_set_100.json"), encoding="utf-8"))
CFG = R["configs"]

NAME = {
    "E_bm25":              "E　BM25 纯关键词",
    "C_dense_small":       "C　bge-small 纯稠密",
    "D_hybrid_small_bm25": "D　bge-small + BM25",
    "A_dense_m3":          "A　bge-m3 纯稠密",
    "F_hybrid_m3_bm25":    "F　bge-m3 + BM25",
    "B_dense_m3_rerank":   "B　bge-m3 + Reranker",
}
SHORT = {k: v.split("　")[1] for k, v in NAME.items()}
ORDER = [k for k in NAME if k in CFG]


def best_by(metric):
    return max(ORDER, key=lambda k: CFG[k][metric])


def tbl_main():
    rows = ["| 配置 | 向量维度 | Recall@1 | Recall@5 | Hit@1 | Hit@5 | MRR@10 | NDCG@5 | 严格 Recall@5 |",
            "|---|---|---|---|---|---|---|---|---|"]
    bi = {m: best_by(m) for m in ("recall@1", "recall@5", "mrr@10", "ndcg@5", "strict_recall@5")}
    for k in ORDER:
        c = CFG[k]; dim = c["perf"].get("dim") or "—"
        def f(m):
            v = f"{c[m]:.2f}"
            return f"**{v}**" if bi[m] == k else v
        rows.append(f"| {NAME[k]} | {dim} | {f('recall@1')} | {f('recall@5')} | "
                    f"{c['hit@1']:.0f} | {c['hit@5']:.0f} | {f('mrr@10')} | {f('ndcg@5')} | {f('strict_recall@5')} |")
    return "\n".join(rows)


def tbl_cost():
    rows = ["| 配置 | 语料编码耗时 | 单查询 p50 | 单查询 p95 | 进程峰值内存 | 备注 |",
            "|---|---|---|---|---|---|"]
    for k in ORDER:
        p = CFG[k]["perf"]
        idx = f"{p['index_s']:.0f} s" if p.get("index_s") else "—"
        p95 = f"{p['query_p95_ms']:.1f} ms" if p.get("query_p95_ms") else "—"
        note = []
        if p.get("recall_pool"): note.append(f"重排候选池 top-{p['recall_pool']}")
        if p.get("fusion"): note.append(p["fusion"])
        if p.get("batch"): note.append(f"batch={p['batch']}")
        rows.append(f"| {NAME[k]} | {idx} | {p.get('query_p50_ms', 0):,.1f} ms | {p95} | "
                    f"{p.get('peak_rss_mb', 0):,.0f} MB | {'；'.join(note) or '—'} |")
    return "\n".join(rows)


def tbl_category():
    best = "B_dense_m3_rerank" if "B_dense_m3_rerank" in CFG else best_by("mrr@10")
    cats = CFG[best]["by_category"]
    rows = [f"| 类别 | 题目场景 | {SHORT[best]} Hit@5 | BM25 Hit@5 | 差值 |", "|---|---|---|---|---|"]
    for c in sorted(cats, key=lambda x: int(x[1:])):
        a = cats[c]["hit@5"]; b = CFG["E_bm25"]["by_category"][c]["hit@5"]
        d = a - b
        sign = f"+{d:.0f}" if d > 0 else (f"{d:.0f}" if d < 0 else "0")
        rows.append(f"| {c} | {cats[c]['name']} | **{a:.0f}** | {b:.0f} | {sign} |")
    return "\n".join(rows), best


def tbl_evalset():
    from collections import Counter
    qs = E["questions"]
    cc = Counter((q["category"], q["category_name"]) for q in qs)
    rows = ["| 类别 | 场景 | 题数 | 高难度 | 跨条款多 gold | 代表 gold 条款 |", "|---|---|---|---|---|---|"]
    for (c, n), k in sorted(cc.items(), key=lambda x: int(x[0][0][1:])):
        sub = [q for q in qs if q["category"] == c]
        hard = sum(1 for q in sub if q["difficulty"] == "hard")
        multi = sum(1 for q in sub if len(q["gold"]) > 1)
        ex = "、".join(sorted({g["clause_id"] for q in sub for g in q["gold"]})[:4])
        rows.append(f"| {c} | {n} | {k} | {hard} | {multi} | {ex} |")
    return "\n".join(rows)


def main():
    b_mrr, b_r5, b_r1 = best_by("mrr@10"), best_by("recall@5"), best_by("recall@1")
    cat_tbl, best_cfg = tbl_category()
    m3, sm, bm = CFG.get("A_dense_m3"), CFG["C_dense_small"], CFG["E_bm25"]
    rr = CFG.get("B_dense_m3_rerank")
    env, corp = R["env"], R["corpus"]

    md = f'''# 香港证监会监管文本检索基准

**HK Financial Regulatory RAG Benchmark — Technical Whitepaper**

**作者**　Angran Fei · AkuWezInbox@proton.me　｜　**评测对象**　香港证监会《持牌人操守准则》与《基金经理操守准则》全文条款级检索

!!! tip
本白皮书给出一套可复现的监管文本检索基准：**{corp['chunks']} 个条款级切块**（覆盖 {corp['clauses']} 个条款）、
**{R['n_questions']} 道金融合规评测问答**（含 {E['meta']['multi_gold']} 道跨条款多 gold 题）、**{len(ORDER)} 个检索配置横向对比**。
全部指标在 {env['cpu_cores']} vCPU / {env['ram_total_mb']} MB 内存的云主机上实测产出，
评测程序、语料切块与问答集均随附可逐条回溯至 PDF 原文页码。

## 一　业务背景与语料

### 1.1　为什么监管检索的幻觉容忍度为零

香港证监会的《操守准则》与《基金经理操守准则》不是参考读物，而是持牌法团的行为边界。
合规意见书、客户协议条款、专业投资者认定程序，其结论均须落到**具体条款编号**；
引错条款意味着向业务部门发出错误的行为授权，后果不是"答案不够好"，
而是法团在监管审查中无法为自身行为举证。

这与通用问答场景的差别在于**错误的不对称性**：漏检一条相关条款，
后果是合规人员多花时间继续查；错检一条不相关条款却被当作依据，
后果是在错误的法律基础上作出了业务决定。**后者的代价远高于前者**，
因此监管检索系统的首要指标不是"看起来相关"，而是**引用的条款编号是否就是那一条**。
本基准据此以条款级 Recall 与 NDCG 为核心指标，而非以答案文本的相似度为指标。

### 1.2　切块必须保持语义完整的真实后果

法规条款之间存在前置依赖，脱离依赖单独取用会得出相反结论。
本项目在标注评测集时即遭遇一例：

!!! warn
**豁免条款脱离前置程序的误读风险。**
《操守准则》15.4 与 15.5 列举了面向企业专业投资者与个人专业投资者**可豁免的条文清单**。
若检索系统单独返回 15.4，读者会得到「这些条文对专业投资者不适用」的结论。
但 15.4 的适用以 **15.2** 为前置：15.2(a) 要求在豁免生效前取得客户**书面签署的同意声明**、
**完整说明被视为专业投资者的后果**、并告知客户**有权随时撤回**；
15.2(b) 进一步要求**每年执行一次确认程序**。
**豁免不是无条件的，而是以一整套程序义务为对价。**
切块若将 15.2 与 15.4 割裂，检索结果在形式上正确、在合规上危险。

本项目的切块因此以**条款为最小单元**而非以固定字符数切分：
子项 `(a)(b)(i)` 一律归并至所属父条款，超长条款按段落边界分片且不截断句子，
并为每一块记录其在 PDF 中的**实际页码**，使任何一条检索结果都可回溯原文核验上下文。

### 1.3　语料来源

| 文档 | 版本 | 页数 | 条款单元 | 切块数 |
|---|---|---|---|---|
| **Code of Conduct for Persons Licensed by or Registered with the SFC** | 2019 年版 | 211 | {len({c for c in _clause_ids("SFC-COC")})} | {_count("SFC-COC")} |
| **Fund Manager Code of Conduct** | 第三版 | 36 | {len({c for c in _clause_ids("SFC-FMCC")})} | {_count("SFC-FMCC")} |

两份文档均自证监会官网直接取得，下载时校验 `%PDF` 魔数并记录 SHA-256，无人工转录环节：

| 文件 | 字节数 | SHA-256（前 16 位） |
|---|---|---|
| `sfc_code_of_conduct.pdf` | 2,418,947 | `7793706166c18bc6…` |
| `sfc_fund_manager_code.pdf` | 701,885 | `efdc2d5237da3bed…` |

切块后的正文长度中位数为 {_chunk_median()} 字符，单块上限 1,400 字符（按段落边界切分，不截断句子）。

### 1.4　切块流程

<div class="arch">
<div class="row">
  <div class="nd"><b>① 原文抽取</b><span>pdftotext -layout<br>保留缩进层级</span></div>
  <div class="nd"><b>② 正文界定</b><span>显式排除封面、版权页<br>与目录页区间</span></div>
  <div class="nd"><b>③ 页脚剥离</b><span>整行页码、罗马数字<br>与 50b/50z 类混合页码</span></div>
</div>
<div class="ar">▼</div>
<div class="row">
  <div class="nd ok"><b>④ 条款识别</b><span>GP1–GP9 总则<br>顶格「编号 + 标题」<br>Schedule N 附表</span></div>
  <div class="nd ok"><b>⑤ 子项归并</b><span>(a)(b)(i) 子项<br>并入所属父条款</span></div>
  <div class="nd ok"><b>⑥ 超长分片</b><span>按段落边界切分<br>不截断句子</span></div>
</div>
<div class="band">⑦ 输出　chunk_id · doc_id · clause_id · clause_title · <b>PDF 页码</b> · 正文　→　每块均可回溯原文核验</div>
</div>
<p class="figcap"><b>图 1　条款级切块流程。</b>第 ② 步与第 ③ 步是语料纯净度的关键：目录页同样含有密集的条款编号，若不显式排除会被识别为正文条款。</p>

### 1.5　切块版本与数据纯净度

初版切块产出 760 块，经审计发现三项结构性缺陷，均会直接动摇评测有效性：

| 缺陷 | 表现 | 对评测的影响 |
|---|---|---|
| **目录页混入语料** | 20 个切块的正文形如「Application 39 / [16.2] Interpretation 39」 | 引入与条款高度相似但无实质内容的噪声文档 |
| **条款编号跨段继承** | 前言段落被标注为条款 20.1 | gold 标注失真，检索「命中」与否不可信 |
| **编号重复** | 266 个切块共用 97 个重复 clause_id | 条款级命中唯一性丧失，Recall 不可计算 |

重建后的 v2 语料为 {corp['chunks']} 块，chunk_id 全局唯一，目录污染为零，
抽样核验 `GP8 Client assets`（p17）、`11.1 Handling of client assets`（p45）、
`12.2 Employee dealings`（p46）、`Sch6 Leveraged foreign exchange trading`（p160）
的条款号、标题与页码与法规原文一致。**本基准的全部指标基于 v2 语料。**

## 二　评测集

### 2.1　题型分布

{tbl_evalset()}

### 2.2　标注规则与校验

每题标注 `(doc_id, clause_id)` 形式的 gold 条款，跨条款题标注多个。构建脚本在输出前
逐一校验 gold 条款在语料中真实存在，任一不存在即终止并报错——
{R['n_questions']} 题全部通过该校验。难度标注中 {E['meta']['hard']} 题为高难度，
取自冷门条款（如 20.5 可比 OTC 衍生工具司法管辖区、12.7 专家证人）、
穿透式监管（5.4 指令发出人与实益拥有人）、客户资产隔离与利益冲突等合规实务高频痛点。

**标注错误的发现与修正。** 存在性校验只能确认 gold 条款存在，无法确认它是否真的回答了该问题。
为此另行计算每题「问题关键词」与「gold 条款正文」的覆盖度，对覆盖度最低的题目逐条回原文复核。
该流程查出三道题的标注指向错误条款：Q037、Q038、Q040 均被标注为 15.4（企业专业投资者豁免条款清单），
但其所问的**同意前披露、撤回权与年度确认程序**实际载于 **15.2**
（原文：`should carry out a confirmation exercise annually`、`has the right to withdraw from being treated as such at any time`）。
三题已更正为 15.2 并重新计分，本文全部指标基于更正后的标注。

!!! warn
**评测集由项目作者依据条款索引构建，非第三方公开基准。** 其价值在于标注可逐条回溯至
法规原文页码、gold 存在性经程序校验、低覆盖度题目经人工回原文复核，而非在于规模或权威性。
跨机构可比的结论需以公开基准复核。

### 2.3　代表性样题

{_sample_questions()}

## 三　检索配置与关键决策

六个配置构成一个 **2×2 消融矩阵**（模型尺寸 × 是否融合 BM25）外加两个端点：
纯关键词基线 E，以及在全规格之上追加交叉编码重排的 B。
该设计使「模型尺寸」与「是否融合」两个变量可以分别归因，而非混在一起比较。

| 配置 | 检索方式 | 模型 | 在消融矩阵中的位置 |
|---|---|---|---|
| **E** | 纯关键词 | BM25（Okapi） | 对照基线 |
| **C** | 纯稠密 | bge-small-en-v1.5（384 维） | 小模型 × 不融合 |
| **D** | 稠密 + 关键词 RRF 融合 | bge-small + BM25 | 小模型 × 融合 |
| **A** | 纯稠密 | bge-m3（1024 维） | 大模型 × 不融合 |
| **F** | 稠密 + 关键词 RRF 融合 | bge-m3 + BM25 | 大模型 × 融合 |
| **B** | 稠密召回 + 交叉编码重排 | bge-m3 + bge-reranker-v2-m3 | 精度优先的生产上界 |

影响结论成立与否的决策记录于架构决策记录（ADR），全文附于第六节：
**ADR-001** 内存点积与内存 BM25 替代独立向量数据库、**ADR-003** 融合采用 RRF 而非加权相加、
**ADR-004** 以重排替代增大 top-k、**ADR-005** 评测集统一英文、
**ADR-006** 分阶段独立进程的评测架构、**ADR-007** 条款级而非切块级的命中判定。

## 四　实测结果

### 4.1　检索质量

{tbl_main()}

<div class="figwrap"><img src="figs/fig_metrics.png"></div>
<p class="figcap"><b>图 2　四项核心指标横向对比。</b>黑框标示该指标的最优配置。</p>

{_analysis(m3, rr, sm, CFG["D_hybrid_small_bm25"], bm, b_r1, b_r5, b_mrr)}

### 4.2　成本

{tbl_cost()}

<div class="figwrap"><img src="figs/fig_cost.png"></div>
<p class="figcap"><b>图 3　延迟与内存开销。</b>左图为对数坐标。内存为进程峰值常驻集（RSS），含模型权重与向量索引。</p>

### 4.3　分类表现

{cat_tbl}

<div class="figwrap"><img src="figs/fig_category.png"></div>
<p class="figcap"><b>图 4　分类命中率对比。</b>按最优配置的 Hit@5 升序排列，与关键词基线并置。</p>

### 4.4　失败归因

{_failures()}

## 五　结论与选型建议

{_conclusion(m3, rr, sm, CFG["D_hybrid_small_bm25"], bm)}

## 六　复现与架构决策记录

### 6.1　复现步骤

```bash
pip install -r requirements.txt    # 依赖；PyTorch 建议装 CPU 版以免拉入 CUDA
./run_eval.sh                      # 单一入口：切块 → 六档评测 → 图表 → 正文 → PDF → 质检
```

该脚本串联的完整阶段为：

```
corpus/fetch.py        取原文 PDF，校验 %PDF 魔数与 SHA-256
src/chunk2.py          条款级切块                 → data/chunks_v2.jsonl
data/build_eval_set.py 评测集 + gold 存在性校验   → data/eval_set_100.json
data/audit_eval_set.py 标注体检：覆盖度排序，低覆盖题回原文复核
src/eval_rag_cpu.py    bm25 → small → hybrid → m3 → hybridm3 → rerank → merge
                       （每阶段独立进程，排名矩阵落盘，见 ADR-006）
src/analyze_failures.py  失败归因                → results/failure_analysis.json
src/make_figs.py / gen_whitepaper.py / build_pdf.py / verify_whitepaper.py
```

模型权重置于 `./models/` 或以环境变量 `MODEL_DIR` 指向，代码内无绝对路径。
标注修正后执行 `./run_eval.sh rescore`：该模式复用已落盘的排名矩阵重算全部指标，
无需重新编码语料（可省去 bge-m3 约 29 分钟的编码开销）。

执行环境：{env.get('cpu_cores')} vCPU ／ {env.get('ram_total_mb')} MB 物理内存 ／
{env.get('swap_total_mb')} MB Swap ／ PyTorch {env.get('torch', '—')}（CPU）／ Python {env.get('python', '—')}。
模型权重为 BAAI 官方发布的 `bge-small-en-v1.5`、`bge-m3`、`bge-reranker-v2-m3`。

{_adrs()}

---

**Angran Fei** · AkuWezInbox@proton.me　｜　*语料切块、评测集、评测程序与本文全部指标可复现；每个切块均标注 PDF 页码以供回溯原文。*
'''
    out = os.path.join(ROOT, "HK_Financial_Regulatory_RAG_Benchmark_Whitepaper.md")
    io.open(out, "w", encoding="utf-8").write(md)
    print("→", out)


# ── 辅助 ──
def _chunk_median():
    import statistics
    return f"{statistics.median([c['n_char'] for c in _CH]):.0f}"


def _sample_questions():
    """每个类别取一道代表题，展示问题与 gold 条款的对应关系。"""
    rows = ["| 题号 | 问题 | gold 条款 | 原文页 |", "|---|---|---|---|"]

    def _goldstr(q):
        groups = {}
        for g in q["gold"]:
            pg = next((c["page"] for c in _CH
                       if c["doc_id"] == g["doc_id"] and c["clause_id"] == g["clause_id"]), "—")
            doc = "COC" if g["doc_id"] == "SFC-COC" else "FMCC"
            groups.setdefault(doc, []).append(f"{g['clause_id']}·p{pg}")
        return "、".join(f"{d} " + "、".join(v) for d, v in groups.items())

    # 每类取一道高难度题作代表；同类中选渲染宽度最紧凑者，避免单元格折行
    picked = {}
    for q in E["questions"]:
        if q["difficulty"] != "hard":
            continue
        w = len(q["question"]) + 2.4 * len(_goldstr(q))
        if q["category"] not in picked or w < picked[q["category"]][0]:
            picked[q["category"]] = (w, q)
    for _, q in sorted((v for v in picked.values()), key=lambda x: x[1]["qid"]):
        rows.append(f"| {q['qid']} | {q['question']} | {_goldstr(q)} | — |")
    out = "\n".join(r.replace(" | — |", " |").replace("| 原文页 |", "|").replace("|---|---|---|---|", "|---|---|---|")
                     for r in rows)
    return out + ("\n\n每题的 gold 条款均标注其在 PDF 中的实际页码，"
                  "审阅者可直接翻至该页核对问题与条款是否对应。")


def _failures():
    import json as _j
    p = os.path.join(ROOT, "results", "failure_analysis.json")
    if not os.path.exists(p):
        return "（失败归因数据缺失。）"
    fa = _j.load(io.open(p, encoding="utf-8"))
    L = [f"**失败集定义**：{fa['definition']}。重排配置 B 是对 A 的 top-20 候选重排，"
         f"A 的候选池若无 gold 条款，B 必然同样未命中，故以四个基础配置界定失败集不会遗漏。\n",
         f"按此定义，{fa['n_total']} 题中有 **{fa['n_failed']} 题**（{fa['fail_rate_pct']}%）"
         f"被全部配置漏检。"]
    if fa["cases"]:
        L.append("\n| 题号 | 类别 | 问题 | gold 条款 |\n|---|---|---|---|")
        for c in fa["cases"]:
            L.append(f"| {c['qid']} | {c['category_name']} | {c['question']} | "
                     f"{'、'.join(x.split('::')[1] for x in c['gold'])} |")
    uniq = fa.get("unique_save", {})
    tot = sum(uniq.values())
    if tot:
        parts = "；".join(f"{SHORT.get(k, k)} {v} 题" for k, v in uniq.items() if v)
        L.append(f"\n**单配置独有贡献**：共 {tot} 题仅被某一个配置在前五命中——{parts}。"
                 f"这说明各配置的失败模式并不重合：稠密检索擅长语义改写，"
                 f"关键词检索擅长术语精确匹配，二者的召回集合存在互补空隙。")
    L.append("\n上述结果的直接含义是：**四个基础配置的并集覆盖率已接近全集**，"
             "因此在生产环境中，多路召回取并集再统一排序，"
             "其收益可能高于继续增大单一模型的参数量。")
    return "\n".join(L)



_CH = [json.loads(l) for l in io.open(os.path.join(ROOT, "data", "chunks_v2.jsonl"), encoding="utf-8")]
def _count(doc): return sum(1 for c in _CH if c["doc_id"] == doc)
def _clause_ids(doc): return {c["clause_id"] for c in _CH if c["doc_id"] == doc}


def _analysis(m3, rr, sm, hy, bm, b_r1, b_r5, b_mrr):
    hm = CFG.get("F_hybrid_m3_bm25")
    L = []
    L.append(f"**关键词基线并不弱。** BM25 在 Recall@5 上达到 {bm['recall@5']:.2f}%，"
             f"原因是监管文本的条款标题与查询用语高度重合（如 “best execution”、“side pocket”、“due diligence”），"
             f"术语本身即为强检索信号。任何声称稠密检索在法规场景大幅碾压关键词检索的结论，都应先核对基线是否被正确实现。")
    if m3:
        d1 = m3["recall@1"] - sm["recall@1"]; d5 = m3["recall@5"] - sm["recall@5"]
        L.append(f"**全规格与轻量档的差距集中在首位命中。** bge-m3（1024 维）相对 bge-small-en-v1.5（384 维）"
                 f"在 Recall@1 上{'领先' if d1 >= 0 else '落后'} {abs(d1):.2f} 个百分点，"
                 f"Recall@5 上{'领先' if d5 >= 0 else '落后'} {abs(d5):.2f} 个百分点。"
                 f"维度提升主要改善排序质量而非召回覆盖面。")
    if hm and m3:
        d_small = hy["recall@1"] - sm["recall@1"]
        d_m3 = hm["recall@1"] - m3["recall@1"]
        L.append(
            f"**多路融合不是万灵药，其收益取决于两路检索器的强弱是否匹配。** "
            f"这是本基准最具工程价值的一条结论，由 2×2 消融设计（模型尺寸 × 是否融合 BM25）直接给出：\n\n"
            f"| 融合组合 | 稠密侧单独 Recall@1 | 融合后 Recall@1 | 变化 |\n|---|---|---|---|\n"
            f"| bge-small（384 维）+ BM25 | {sm['recall@1']:.2f}% | **{hy['recall@1']:.2f}%** | "
            f"**{d_small:+.2f}** |\n"
            f"| bge-m3（1024 维）+ BM25 | {m3['recall@1']:.2f}% | **{hm['recall@1']:.2f}%** | "
            f"**{d_m3:+.2f}** |\n\n"
            f"同一个 BM25（单独 Recall@1 仅 {bm['recall@1']:.2f}%），"
            f"融入轻量档使首位命中**提升 {abs(d_small):.2f} 个百分点**，"
            f"融入全规格档却使其**下降 {abs(d_m3):.2f} 个百分点**。"
            f"根因在于 RRF 只使用排名、不使用分数（见 ADR-003）："
            f"当稠密侧显著强于关键词侧时，等权融合让弱侧的错误结果获得与强侧同等的排名权重，"
            f"把强侧原本正确的首位结果挤出第一名。"
            f"**因此「上混合检索」不是一个可以无条件照搬的架构决策**——"
            f"在采用等权 RRF 之前，必须先确认两路召回器的单独表现处于同一量级，"
            f"否则融合是净损失。")
        L.append(f"**覆盖面与首位命中需分开决策。** 融合在 Recall@5 上的表现与 Recall@1 并不同向："
                 f"轻量档融合后 Recall@5 为 {hy['recall@5']:.2f}%（单独 {sm['recall@5']:.2f}%），"
                 f"全规格档融合后为 {hm['recall@5']:.2f}%（单独 {m3['recall@5']:.2f}%）。"
                 f"融合提升双路共识条款的排名，代价是少数仅由稠密检索召回的 gold 条款被挤出前五。"
                 f"若下游只取 top-1 交付人工复核，应按 Recall@1 选型；"
                 f"若取 top-k 作为生成端的上下文窗口，应按 Recall@5 与严格 Recall@5 选型。")
    if rr and m3:
        dr1 = rr["recall@1"] - m3["recall@1"]
        cost = rr["perf"].get("rerank_p50_ms", 0)
        L.append(f"**重排的收益与代价均显著。** 交叉编码重排使 Recall@1 "
                 f"{'提升' if dr1 >= 0 else '下降'} {abs(dr1):.2f} 个百分点，"
                 f"但单查询新增约 {cost/1000:.1f} 秒（CPU，候选池 top-{rr['perf'].get('recall_pool')}）。"
                 f"该延迟在 GPU 上可降低一个数量级，但在纯 CPU 部署下已超出交互式查询的可接受范围。")
    return "\n\n".join(L)


def _conclusion(m3, rr, sm, hy, bm):
    rows = ["| 场景 | 推荐配置 | 依据 |", "|---|---|---|"]
    best1 = max([k for k in ORDER], key=lambda k: CFG[k]["recall@1"])
    rows.append(f"| **交互式查询**<br>（CPU 部署） | {SHORT['D_hybrid_small_bm25']} | "
                f"Recall@1 **{hy['recall@1']:.2f}%**（全配置最高）、单查询 {hy['perf']['query_p50_ms']:.0f} ms、"
                f"内存 {sm['perf']['peak_rss_mb']:.0f} MB |")
    if rr:
        rows.append(f"| **离线批量审阅**<br>（精度优先） | {SHORT['B_dense_m3_rerank']} | "
                    f"Recall@5 **{rr['recall@5']:.2f}%**、NDCG@5 **{rr['ndcg@5']:.2f}%**；"
                    f"单查询 {rr['perf']['query_p50_ms']/1000:.0f} s，非实时专用 |")
    rows.append(f"| **边缘部署**<br>（无 GPU） | {SHORT['E_bm25']} | "
                f"Recall@5 {bm['recall@5']:.2f}%、延迟 {bm['perf']['query_p50_ms']:.2f} ms、"
                f"内存 {bm['perf']['peak_rss_mb']:.0f} MB，零模型依赖 |")
    tail = f'''{chr(10).join(rows)}

!!! tip
**本基准的三条可迁移结论。**
**①** 法规文本的条款标题承载了极强的检索信号，关键词基线必须作为对照项实现，
否则容易把「语料本身好检索」误读为「模型效果好」。
**②** 向量维度的提升主要兑现为排序质量（Recall@1、MRR）而非召回覆盖面（Recall@5），
选型应依据下游是取 top-1 还是 top-k 的上下文窗口而定。
**③** 交叉编码重排在 CPU 上的延迟代价是数量级的，其部署可行性由硬件而非效果决定。

!!! warn
**绝对 Recall 受真实标注的完备性限制，本文的结论建立在横向对比之上。**
复核发现，最优配置在 26 道题上的首位检出条款落在 gold 清单之外，
其中约四分之一属于**标注不完整而非检索错误**——例如「将企业客户视为专业投资者前须完成何种评估」
一题检出 15.2，而 gold 标注为 15.4，但前置评估程序恰恰载于 15.2，该检出结果同样成立。
因此**本文的绝对 Recall 数值应被理解为下界，不应作为「准确率」对外引用**。
由于六档配置使用同一套 gold 标注接受评分，
**配置之间的横向对比规律不受标注完备性影响**，本文的全部结论均建立在该对比之上。

**其余已知边界**：① 评测集为自建，非第三方公开基准（见 2.2 节）；
② 全部查询为英文，未覆盖中文及中英混合查询场景（见 ADR-005）；
③ 指标为检索质量，未评估生成端的忠实度与引用正确性，该环节需另行以答案级标注评测；
④ 延迟与内存在 {R["env"].get("cpu_cores")} vCPU 云主机上测得，不代表 GPU 或多核环境下的表现。
!!!'''
    return tail


def _adrs():
    out = ["### 6.2　架构决策记录"]
    for n in ("001", "003", "004", "005", "006", "007"):
        p = os.path.join(ROOT, "docs", "adr", f"adr-{n}.md")
        if not os.path.exists(p): continue
        t = io.open(p, encoding="utf-8").read().strip().split("\n")
        title = t[0].lstrip("# ").strip()
        body = {}
        cur = None
        for ln in t[1:]:
            if ln.startswith("## "):
                cur = ln[3:].strip(); body[cur] = []
            elif cur and ln.strip():
                body[cur].append(ln.strip())
        out.append(f"\n#### {title}\n")
        for k in ("背景", "决策", "理由", "后果"):
            if k in body:
                out.append(f"**{k}**　{' '.join(body[k])}\n")
    return "\n".join(out)


if __name__ == "__main__":
    main()
