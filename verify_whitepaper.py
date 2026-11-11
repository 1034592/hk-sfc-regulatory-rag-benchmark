# -*- coding: utf-8 -*-
"""
白皮书交付验证
==============
① 排版：页数、空白页、乱码、页尾悬挂、标题悬挂、单元格折行碎片、边距对称
② 指标一致性：PDF 正文数字与 results/metrics_rag.json 逐项比对
③ 内容完备性：六档配置、ADR、业务痛点章节、局限性声明均在位
④ 文风：署名正确、无第一人称与出戏表述
任一不过即以非零码退出。
"""
import json, os, re, subprocess, sys, io

ROOT = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(ROOT, "HK_Financial_Regulatory_RAG_Benchmark_Whitepaper.pdf")
FAIL = []

def ok(cond, label, detail=""):
    print(f"  {'✅' if cond else '❌'} {label}{('  ' + detail) if detail else ''}")
    if not cond: FAIL.append(label)

t = subprocess.run(["pdftotext", "-layout", PDF, "-"], capture_output=True, text=True).stdout
pages = t.split("\f")[:-1]
flat = re.sub(r"\s+", " ", t)

print("═══ ① 排版 ═══")
ok(8 <= len(pages) <= 12, "页数在 8–12 区间", f"实得 {len(pages)}")
ok(not [i for i, p in enumerate(pages) if len(p.strip()) < 40], "无空白页")
ok("�" not in t, "无乱码")

orphan, hang, frag = [], [], []
for i, p in enumerate(pages):
    lines = [l.strip() for l in p.strip().split("\n") if l.strip()]
    if i < len(pages) - 1 and lines:
        last = lines[-1]
        if len(last) < 22 and not re.search(r"[。）》%?]$", last) and not re.match(r"^[第图表]", last):
            orphan.append((i + 1, last))
        if re.match(r"^(一|二|三|四|五|六|七)\s|^\d\.\d\s", last):
            hang.append((i + 1, last))
    for ln in p.split("\n"):
        b = ln.strip(); indent = len(ln) - len(ln.lstrip())
        if indent >= 20 and 0 < len(b) <= 10 and b not in ("▼", "▲", "—", "·", "|"):
            frag.append((i + 1, b))
ok(not orphan, "无页尾悬挂", str(orphan))
ok(not hang, "无标题页尾悬挂", str(hang))
ok(not frag, "无单元格折行碎片", str(frag[:6]))

bbox = subprocess.run(["pdftotext", "-bbox", PDF, "-"], capture_output=True, text=True).stdout
spans = re.findall(r'xMin="([\d.]+)"[^>]*xMax="([\d.]+)"', bbox)
left, right = min(float(a) for a, _ in spans), 595 - max(float(b) for _, b in spans)
ok(abs(left - right) < 6, "左右边距对称", f"左 {left:.1f}pt / 右 {right:.1f}pt")

print("\n═══ ② 指标一致性 ═══")
R = json.load(io.open(os.path.join(ROOT, "results", "metrics_rag.json"), encoding="utf-8"))
cfg = R["configs"]
ok(len(cfg) == 6, "六档配置齐备", f"实得 {len(cfg)}")
for k, v in cfg.items():
    for m in ("recall@1", "recall@5", "mrr@10", "ndcg@5"):
        val = f"{v[m]:.2f}"
        ok(val in flat, f"{k} {m} = {val}")

print("\n═══ ③ 内容完备性 ═══")
for key, label in [
    ("幻觉", "幻觉零容忍论述"), ("15.2", "豁免条款前置程序案例"),
    ("语义完整", "切块语义完整性论述"), ("ADR-001", "ADR-001（内存计算 vs 向量库）"),
    ("ADR-005", "ADR-005"), ("ADR-006", "ADR-006"), ("ADR-007", "ADR-007"),
    ("标注完备性", "绝对 Recall 局限性声明"), ("横向对比", "横向对比规律声明"),
    ("bge-m3 + BM25", "第六档消融"),
]:
    ok(key in flat, label)
ok("pgvector" not in flat or "弃用" in flat or "替代" in flat,
   "无与实现矛盾的 pgvector 主张")

print("\n═══ ④ 文风与署名 ═══")
ok("AkuWezInbox@proton.me" in t and "Angran Fei" in t, "署名正确")
for bad in ["Aaron", "startorch", "我踩", "纸上", "碎碎念", "自嗨"]:
    ok(bad not in t, f"无「{bad}」")
ok(len(re.findall(r"(?<![A-Za-z])我(?![们])", t)) == 0, "无第一人称「我」")

print("\n" + "═" * 56)
if FAIL:
    print(f"  ❌ 未通过 {len(FAIL)} 项：{FAIL[:8]}"); sys.exit(1)
print("  ✅ 全部检查通过"); sys.exit(0)
