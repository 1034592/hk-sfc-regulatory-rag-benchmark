# -*- coding: utf-8 -*-
"""
SFC 法规条款级切块 v2
=====================
v1 的三个缺陷（已由审计确认）：
  ① 目录页被当作正文摄入，产生 20 个「条款编号 + 页码」索引块；
  ② clause_id 由「最近一次见到的编号」继承，导致前言段落被错标为 20.1；
  ③ 266 个块共用 97 个重复 clause_id，使 hit@k 评估失去意义。

v2 的处理原则：
  · 显式界定正文页范围，目录与版权页不进入语料；
  · 条款编号只认【行首顶格的编号 + 标题】这一种结构，不做跨段继承；
  · clause_id 以文档前缀命名空间化，附表内编号加 Sch 前缀，确保全局唯一；
  · 每个切块记录真实 PDF 页码，使标注可逐条回溯原文核验。
"""
import json, re, io, os, subprocess, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DOCS = [
    {"doc_id": "SFC-COC", "pdf": "corpus/sfc_code_of_conduct.pdf",
     "title": "Code of Conduct for Persons Licensed by or Registered with the SFC",
     "body_from": 14},     # 1-based：1-3 封面与版权，4-13 目录
    {"doc_id": "SFC-FMCC", "pdf": "corpus/sfc_fund_manager_code.pdf",
     "title": "Fund Manager Code of Conduct",
     "body_from": 3},      # 1 封面，2 目录
]

# ── 结构识别 ──
RE_GP       = re.compile(r'^(GP\d{1,2})\.\s+(.{2,80})$')
RE_SCHEDULE = re.compile(r'^\s{0,6}(Schedule\s+\d{1,2}[A-Z]?)\b(.*)$', re.I)
# 顶格编号 + 两个以上空格 + 标题（COC 体例）
RE_CLAUSE_T = re.compile(r'^(\d{1,2}[A-Z]?(?:\.\d{1,2}[A-Z]?)*)\s{2,}(\S.{0,90})$')
# 顶格编号 + 单空格 + 正文（FMCC 体例）
RE_CLAUSE_B = re.compile(r'^(\d{1,2}(?:\.\d{1,2})+)\s+(\S.*)$')
RE_SUBITEM  = re.compile(r'^\s{0,10}\(([a-z]{1,3}|[ivx]{1,4})\)\s+\S')
# 页脚：整行只有页码（阿拉伯、罗马、或 50b/50z 这类带字母页码）
RE_FOOTER   = re.compile(r'^\s*(?:\d{1,3}[a-z]?|[ivxlcdm]{1,7})\s*$', re.I)

MAX_CHARS = 1400      # 超长条款分片上限
MIN_CHARS = 60        # 过短片段并入上一块


def pdf_pages(pdf):
    out = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True, check=True).stdout
    return out.split("\f")


def clean_page(raw):
    """去掉页脚页码与空白噪声，保留缩进（缩进是判定条款层级的依据）"""
    lines = []
    for ln in raw.split("\n"):
        if RE_FOOTER.match(ln):
            continue
        lines.append(ln.rstrip())
    # 去掉首尾空行
    while lines and not lines[0].strip(): lines.pop(0)
    while lines and not lines[-1].strip(): lines.pop()
    return lines


def parse_doc(doc):
    pages = pdf_pages(os.path.join(ROOT, doc["pdf"]))
    body = [(i + 1, p) for i, p in enumerate(pages)][doc["body_from"] - 1:]
    units = []           # (clause_id, title, page, [lines])
    cur = None
    section = "Explanatory notes"
    schedule = None

    for pno, raw in body:
        for ln in clean_page(raw):
            s = ln.strip()
            if not s:
                if cur: cur["lines"].append("")
                continue

            m = RE_SCHEDULE.match(ln)
            if m and len(s) < 120:
                schedule = m.group(1).replace("  ", " ").title().replace("Schedule ", "Sch")
                section = m.group(1).strip()
                if cur: units.append(cur)
                cur = {"clause_id": schedule, "title": m.group(1).strip(),
                       "page": pno, "lines": [m.group(2).strip()] if m.group(2).strip() else []}
                continue

            m = RE_GP.match(ln)
            if m:
                if cur: units.append(cur)
                section = "General principles"
                cur = {"clause_id": m.group(1), "title": m.group(2).strip(),
                       "page": pno, "lines": []}
                continue

            if not RE_SUBITEM.match(ln):          # 子项不开新条款
                m = RE_CLAUSE_T.match(ln) or RE_CLAUSE_B.match(ln)
                if m:
                    num, rest = m.group(1), m.group(2).strip()
                    cid = f"{schedule}-{num}" if schedule else num
                    if cur: units.append(cur)
                    is_title = bool(RE_CLAUSE_T.match(ln)) and len(rest) < 95 and not rest.endswith(".")
                    cur = {"clause_id": cid, "title": rest if is_title else "",
                           "page": pno, "lines": [] if is_title else [rest]}
                    continue

            if cur is None:                        # 正文开始前的说明段落
                cur = {"clause_id": "front", "title": section, "page": pno, "lines": []}
            cur["lines"].append(ln)
    if cur: units.append(cur)
    return units


def to_chunks(doc, units):
    chunks, seen = [], {}
    for u in units:
        text = re.sub(r'\n{3,}', '\n\n', "\n".join(u["lines"])).strip()
        if len(text) < MIN_CHARS and chunks and chunks[-1]["doc_id"] == doc["doc_id"]:
            chunks[-1]["text"] += "\n" + (u["title"] + "\n" if u["title"] else "") + text
            chunks[-1]["n_char"] = len(chunks[-1]["text"])
            continue
        if not text:
            continue
        parts = [text]
        if len(text) > MAX_CHARS:                 # 按段落边界分片，不切断句子
            parts, buf = [], ""
            for para in text.split("\n\n"):
                if buf and len(buf) + len(para) > MAX_CHARS:
                    parts.append(buf.strip()); buf = para
                else:
                    buf += ("\n\n" if buf else "") + para
            if buf.strip(): parts.append(buf.strip())
        for k, part in enumerate(parts, 1):
            cid = u["clause_id"]
            seen[cid] = seen.get(cid, 0) + 1
            suffix = "" if (len(parts) == 1 and seen[cid] == 1) else f"#{seen[cid] if len(parts)==1 else k}"
            chunks.append({
                "chunk_id": f"{doc['doc_id']}::{cid}{suffix}",
                "doc_id": doc["doc_id"], "doc_title": doc["title"],
                "clause_id": cid, "clause_title": u["title"],
                "page": u["page"], "text": part, "n_char": len(part),
            })
    return chunks


def main():
    allc = []
    for doc in DOCS:
        units = parse_doc(doc)
        cs = to_chunks(doc, units)
        print(f"  {doc['doc_id']:10} 条款单元 {len(units):4}  →  切块 {len(cs):4}")
        allc += cs
    out = os.path.join(ROOT, "data", "chunks_v2.jsonl")
    with io.open(out, "w", encoding="utf-8") as f:
        for c in allc:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    ids = [c["chunk_id"] for c in allc]
    print(f"\n  总块数 {len(allc)} ｜ chunk_id 唯一 {len(set(ids))} ｜ "
          f"clause_id 基数 {len({c['clause_id'] for c in allc})}")
    print(f"  → {out}")


if __name__ == "__main__":
    main()
