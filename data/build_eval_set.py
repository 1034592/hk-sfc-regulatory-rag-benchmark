# -*- coding: utf-8 -*-
"""
SFC 监管 RAG 评测问答集（100 题）
=================================
出题原则：
  · 每题锚定 chunks_v2.jsonl 中真实存在的条款，gold 为 (doc_id, clause_id) 列表；
  · 场景取自对冲基金运营、券商法务与持牌法团合规官的真实查询，
    覆盖冷门条款、跨条款交叉、穿透式监管、客户资产隔离与利益冲突；
  · 统一使用英文——语料为英文法规原文，且轻量档 bge-small-en-v1.5 为英文单语模型，
    若用中文出题会系统性压低该档成绩，使双模对比失去可比性（见 ADR-005）。
  · 多 gold 题（跨条款）命中判定为「检出任一 gold 条款即算命中」，
    另单列 strict 口径（须检出全部 gold）作为对照。
"""
import json, io, os, sys

Q = []
def q(cat, cname, text, gold, diff="normal", note=""):
    Q.append({"qid": f"Q{len(Q)+1:03d}", "category": cat, "category_name": cname,
              "question": text, "gold": [{"doc_id": d, "clause_id": c} for d, c in gold],
              "difficulty": diff, "note": note})

C = "C1"; N = "客户资产隔离与托管"
q(C,N,"What general standard governs a licensed person's handling of client assets?",[("SFC-COC","GP8"),("SFC-COC","11.1")])
q(C,N,"Must a licensed person keep client money in accounts separate from its own funds?",[("SFC-COC","3.7")])
q(C,N,"What are a licensed person's obligations when collecting margin from clients?",[("SFC-COC","3.6")])
q(C,N,"Who is responsible for selecting and appointing a custodian for fund assets?",[("SFC-FMCC","4.1.2")])
q(C,N,"What due diligence must a Fund Manager carry out before appointing a custodian?",[("SFC-FMCC","4.2.1"),("SFC-FMCC","4.2.2")],"hard")
q(C,N,"Is a formal written custody agreement required for fund assets?",[("SFC-FMCC","4.3.1")])
q(C,N,"What ongoing monitoring of custody arrangements is expected after appointment?",[("SFC-FMCC","4.3.3")])
q(C,N,"What applies where a Fund Manager itself retains custody of fund assets rather than appointing a third party?",[("SFC-FMCC","4.4.2")],"hard")
q(C,N,"What segregation must custody arrangements achieve for fund assets?",[("SFC-FMCC","4.4.1")])
q(C,N,"How frequently should reconciliation of fund assets and positions be carried out?",[("SFC-FMCC","5.6")])

C = "C2"; N = "利益冲突与员工交易"
q(C,N,"What is the overarching principle on conflicts of interest for licensed persons?",[("SFC-COC","GP6")])
q(C,N,"When a conflict cannot be avoided, what must a licensed person do to ensure fair treatment?",[("SFC-COC","10.1")])
q(C,N,"What independence requirements apply when a firm has a material interest in a transaction?",[("SFC-COC","10.2")])
q(C,N,"Must a firm have a written policy on whether employees may deal for their own account?",[("SFC-COC","12.2")])
q(C,N,"How must client orders be prioritised against the firm's own orders?",[("SFC-COC","9.1"),("SFC-COC","9.2")])
q(C,N,"What internal rules must a Fund Manager have on personal account dealing by relevant persons?",[("SFC-FMCC","2.1.1")])
q(C,N,"May a Fund Manager permit relevant persons to deal ahead of client or fund orders?",[("SFC-FMCC","2.1.3")],"hard")
q(C,N,"What restrictions apply to cross trades between house accounts and client accounts?",[("SFC-FMCC","3.9.2")],"hard")
q(C,N,"What must a Fund Manager observe when dealing for a house account?",[("SFC-FMCC","3.10")])
q(C,N,"What conflict controls apply to analysts' trading and personal financial interests?",[("SFC-COC","16.4")])

C = "C3"; N = "客户身份穿透与 KYC"
q(C,N,"What must a licensed person establish about a client before providing services?",[("SFC-COC","5.1")])
q(C,N,"What must a firm do to identify the person ultimately responsible for originating an order?",[("SFC-COC","5.4")],"hard",
  "穿透式监管核心条款：originator of instructions 与 ultimate beneficiary")
q(C,N,"If an intermediary places orders on behalf of underlying clients, what identity information must be obtainable?",[("SFC-COC","5.4")],"hard")
q(C,N,"What is required when characterising whether a client has knowledge of derivatives?",[("SFC-COC","5.1A")],"hard")
q(C,N,"What steps apply where a client is assessed as not having derivative knowledge?",[("SFC-COC","5.1A"),("SFC-COC","5.3")],"hard")
q(C,N,"What information about a client's financial situation and investment objectives must be sought?",[("SFC-COC","GP4"),("SFC-COC","5.1")])
q(C,N,"What records support the firm's assessment of a client's investment experience?",[("SFC-COC","5.1"),("SFC-COC","5.1A")])
q(C,N,"What obligations arise if the firm cannot satisfy itself as to the beneficial identity behind an account?",[("SFC-COC","5.4")],"hard")
q(C,N,"What must a Fund Manager do to verify that a fund's investment strategy matches its stated risk profile?",[("SFC-FMCC","3.11.1")],"hard")
q(C,N,"How should a licensed person treat instructions received from a third party holding a power of attorney?",[("SFC-COC","5.4"),("SFC-COC","7.1")],"hard")

C = "C4"; N = "专业投资者认定与豁免"
q(C,N,"What is the general approach to dealing with Professional Investors under the Code?",[("SFC-COC","15.1")])
q(C,N,"What terminology distinguishes the categories of Professional Investor?",[("SFC-COC","15.2")])
q(C,N,"Which Code provisions may be dispensed with for Corporate Professional Investors?",[("SFC-COC","15.4")],"hard")
q(C,N,"What assessment must be completed before treating a corporate client as a Corporate Professional Investor?",[("SFC-COC","15.4")],"hard")
q(C,N,"What exempt provisions apply to Individual Professional Investors?",[("SFC-COC","15.5")],"hard")
q(C,N,"Is a client agreement still required when dealing with an Institutional Professional Investor?",[("SFC-COC","15.1"),("SFC-COC","6.1")],"hard")
q(C,N,"What must be disclosed to a client before it consents to be treated as a Professional Investor?",[("SFC-COC","15.2")],"hard",
  "15.2(a)(ii) 规定须说明被视为专业投资者的后果")
q(C,N,"Can a Professional Investor withdraw its consent to Professional Investor treatment?",[("SFC-COC","15.2")],"hard",
  "撤回权载于 15.2(a)(ii)(iii)，非 15.4 豁免清单")
q(C,N,"Do suitability obligations continue to apply to Corporate Professional Investors?",[("SFC-COC","15.4"),("SFC-COC","5.2")],"hard")
q(C,N,"How often must the Professional Investor assessment be reviewed?",[("SFC-COC","15.2")],"hard",
  "年度确认程序载于 15.2(b)")

C = "C5"; N = "适当性与复杂产品"
q(C,N,"What is the suitability obligation when recommending a product to a client?",[("SFC-COC","5.2")])
q(C,N,"What additional requirements apply to the sale of derivative products?",[("SFC-COC","5.3")])
q(C,N,"What obligations apply specifically to complex products?",[("SFC-COC","5.5")],"hard")
q(C,N,"What must a firm do when a transaction is executed without any solicitation or recommendation?",[("SFC-COC","5.5")],"hard")
q(C,N,"What is required regarding advice given with due skill, care and diligence?",[("SFC-COC","3.4")])
q(C,N,"What duty is owed to act in the best interests of clients when distributing products?",[("SFC-COC","3.10")])
q(C,N,"Which minimum terms must a client agreement contain?",[("SFC-COC","6.2")])
q(C,N,"May a client agreement include terms inconsistent with the Code?",[("SFC-COC","6.5")])
q(C,N,"What risk disclosure statements should a client agreement incorporate?",[("SFC-COC","Sch1"),("SFC-COC","6.2")],"hard")
q(C,N,"What applies where a firm provides services on a limited or execution-only basis?",[("SFC-COC","6.4")])

C = "C6"; N = "利益与收费披露"
q(C,N,"What monetary and non-monetary benefits must be disclosed to clients?",[("SFC-COC","8.3")])
q(C,N,"What transaction related information must be disclosed to clients?",[("SFC-COC","8.3A")],"hard")
q(C,N,"What must be disclosed where the firm receives a benefit for a discretionary account transaction?",[("SFC-COC","7.2")],"hard")
q(C,N,"Are charges to clients required to be fair and reasonable?",[("SFC-COC","2.2")])
q(C,N,"What governs the use of gifts by distributors promoting a specific investment product?",[("SFC-COC","3.11")],"hard")
q(C,N,"What information about the firm must be provided to clients in general?",[("SFC-COC","8.1")])
q(C,N,"How promptly must transaction confirmations be sent to clients?",[("SFC-COC","8.2")])
q(C,N,"What disclosure obligations does a Fund Manager have regarding charges, fees and mark-ups?",[("SFC-FMCC","8.2")])
q(C,N,"What must a Fund Manager disclose to a fund about benefits received?",[("SFC-FMCC","8.1")])
q(C,N,"What standards govern a Fund Manager's advertisements and marketing materials?",[("SFC-FMCC","7.2"),("SFC-COC","2.3")])

C = "C7"; N = "保荐人尽职调查"
q(C,N,"What are the key requirements applicable to a sponsor of a listing application?",[("SFC-COC","17.2")])
q(C,N,"What work must a sponsor complete before submitting a listing application?",[("SFC-COC","17.4")],"hard")
q(C,N,"What is the scope of a sponsor's due diligence obligation?",[("SFC-COC","17.6")],"hard")
q(C,N,"What due diligence must a sponsor perform on expert reports relied upon in a prospectus?",[("SFC-COC","17.7")],"hard")
q(C,N,"What records must a sponsor keep to evidence its due diligence?",[("SFC-COC","17.10")],"hard")
q(C,N,"What resources, systems and controls must a sponsor maintain?",[("SFC-COC","17.11")],"hard")
q(C,N,"Is an annual assessment of a sponsor's systems and controls required?",[("SFC-COC","17.12")],"hard")
q(C,N,"What applies to information a sponsor provides to analysts in a new listing?",[("SFC-COC","17.14")],"hard")
q(C,N,"What obligations govern a sponsor's communications with the regulators?",[("SFC-COC","17.9")])
q(C,N,"What is expected in the overall management of a public offer by a sponsor?",[("SFC-COC","17.13")],"hard")

C = "C8"; N = "电子交易、算法交易与另类流动性池"
q(C,N,"Who is responsible for orders transmitted through an internet trading or DMA system?",[("SFC-COC","18.3")])
q(C,N,"What management and supervision is required for electronic trading systems?",[("SFC-COC","18.4")])
q(C,N,"What system adequacy requirements apply to electronic trading?",[("SFC-COC","18.5"),("SFC-COC","Sch7-1.2")],"hard")
q(C,N,"What minimum client requirements apply before granting DMA access?",[("SFC-COC","18.8"),("SFC-COC","Sch7-2.2")],"hard")
q(C,N,"What qualification requirements apply to algorithmic trading systems?",[("SFC-COC","18.9"),("SFC-COC","Sch7-3.1")],"hard")
q(C,N,"What testing obligations apply to an algorithmic trading system before deployment?",[("SFC-COC","18.10"),("SFC-COC","Sch7-3.2")],"hard")
q(C,N,"What risk management controls are required for algorithmic trading?",[("SFC-COC","18.11"),("SFC-COC","Sch7-3.3")],"hard")
q(C,N,"Who may be given access to an alternative liquidity pool?",[("SFC-COC","19.4")],"hard")
q(C,N,"How must order priority be determined within an alternative liquidity pool?",[("SFC-COC","19.6")],"hard")
q(C,N,"Must users be able to opt out of having their orders routed to an ALP?",[("SFC-COC","19.8")],"hard")

C = "C9"; N = "基金估值、侧袋与运营"
q(C,N,"What must a Fund Manager ensure regarding valuation policies and procedures for fund assets?",[("SFC-FMCC","5.3.1")])
q(C,N,"What must the valuation policies describe in addition to the methodologies used?",[("SFC-FMCC","5.3.2")])
q(C,N,"How often should valuation policies and procedures be reviewed?",[("SFC-FMCC","5.3.3")])
q(C,N,"What applies where a third party is appointed to perform valuation?",[("SFC-FMCC","5.3.4")],"hard")
q(C,N,"What must be done before a side pocket is introduced in a fund?",[("SFC-FMCC","5.4.1")],"hard",
  "对冲基金运营高频痛点：side pocket 事前条件")
q(C,N,"What obligations arise once a Fund Manager decides to side pocket fund assets?",[("SFC-FMCC","5.4.3")],"hard")
q(C,N,"What must a Fund Manager ensure about the calculation of net asset value?",[("SFC-FMCC","5.5.1")])
q(C,N,"Must an independent auditor be appointed for a fund?",[("SFC-FMCC","5.2.1")])
q(C,N,"What applies where the Fund Manager is responsible for the overall operation of a fund?",[("SFC-FMCC","5.2.2"),("SFC-FMCC","6.2")],"hard")
q(C,N,"How should accounts and records of a Fund Manager be kept?",[("SFC-FMCC","5.1")])

C = "C10"; N = "跨条款交叉与穿透式监管"
q(C,N,"How do the obligations on client asset safeguarding interact with the requirement to keep separate accounts?",[("SFC-COC","GP8"),("SFC-COC","11.1"),("SFC-COC","3.7")],"hard")
q(C,N,"A licensed corporation extends financial exposure to a group affiliate — what governs this?",[("SFC-COC","20.1")],"hard",
  "冷门条款：集团关联方财务敞口")
q(C,N,"What applies when a licensed person solicits or recommends its own group's products?",[("SFC-COC","20.2")],"hard")
q(C,N,"Which comparable OTC derivative jurisdictions are recognised for the purposes of paragraph 20.3?",[("SFC-COC","20.5")],"hard","最冷门条款之一")
q(C,N,"Where a Fund Manager is part of a group with shared functions, what organisational requirements apply?",[("SFC-FMCC","1.3")],"hard")
q(C,N,"How does the duty of senior management responsibility connect to supervision of staff?",[("SFC-COC","GP9"),("SFC-COC","14.1"),("SFC-COC","4.2")],"hard")
q(C,N,"What must be notified to the Commission and in what circumstances?",[("SFC-COC","12.5")],"hard")
q(C,N,"What obligations apply to a licensed person acting as an expert witness?",[("SFC-COC","12.7")],"hard","极冷门条款")
q(C,N,"What are a firm's obligations under the Financial Dispute Resolution Scheme?",[("SFC-COC","12A"),("SFC-COC","12.6")],"hard")
q(C,N,"What must a Fund Manager do on withdrawing from business, and how does this compare with a licensed person's duty?",[("SFC-FMCC","1.11"),("SFC-COC","9.4")],"hard")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    chunks = [json.loads(l) for l in io.open(os.path.join(root, "data", "chunks_v2.jsonl"), encoding="utf-8")]
    have = {(c["doc_id"], c["clause_id"]) for c in chunks}
    bad = []
    for item in Q:
        for g in item["gold"]:
            if (g["doc_id"], g["clause_id"]) not in have:
                bad.append((item["qid"], g["doc_id"], g["clause_id"]))
    if bad:
        print("❌ gold 条款在语料中不存在：")
        for b in bad: print("   ", b)
        sys.exit(1)
    assert len(Q) == 100, f"题目数 {len(Q)} ≠ 100"
    out = os.path.join(here, "eval_set_100.json")
    meta = {"n_questions": len(Q), "corpus": "chunks_v2.jsonl",
            "n_chunks": len(chunks), "language": "en",
            "multi_gold": sum(1 for x in Q if len(x["gold"]) > 1),
            "hard": sum(1 for x in Q if x["difficulty"] == "hard")}
    json.dump({"meta": meta, "questions": Q}, io.open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    from collections import Counter
    print(f"✅ {len(Q)} 题 → {out}")
    print(f"   多 gold 跨条款题 {meta['multi_gold']} ｜ 高难度 {meta['hard']}")
    for c, n in sorted(Counter((x["category"], x["category_name"]) for x in Q).items()):
        print(f"   {c[0]:4} {c[1]:<24} {n} 题")

if __name__ == "__main__":
    main()
