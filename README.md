# 香港证监会监管文本检索基准（资产 A）

条款级 RAG 检索基准。语料为香港证监会《持牌人操守准则》与《基金经理操守准则》全文，
在 100 道金融合规问答上横向评测 **6 个检索配置**，构成「模型尺寸 × 是否融合 BM25」的 2×2 消融矩阵。

## 快速开始

```bash
pip install -r requirements.txt     # PyTorch 建议装 CPU 版，避免拉入 CUDA
./run_eval.sh                       # 单一入口：切块 → 六档评测 → 图表 → 正文 → PDF → 质检
```

其他模式：`./run_eval.sh corpus | eval | rescore | report`。
`rescore` 复用已落盘的排名矩阵重算指标，不重新编码语料。

模型权重置于 `./models/` 或以环境变量 `MODEL_DIR` 指向，代码内无绝对路径：
`BAAI/bge-small-en-v1.5`、`BAAI/bge-m3`、`BAAI/bge-reranker-v2-m3`。

## 评测配置

| 代号 | 检索方式 | 模型 | 消融位置 |
|---|---|---|---|
| E | 纯关键词 | BM25（Okapi） | 对照基线 |
| C | 纯稠密 | bge-small-en-v1.5（384 维） | 小模型 × 不融合 |
| D | 稠密 + BM25（RRF） | bge-small + BM25 | 小模型 × 融合 |
| A | 纯稠密 | bge-m3（1024 维） | 大模型 × 不融合 |
| F | 稠密 + BM25（RRF） | bge-m3 + BM25 | 大模型 × 融合 |
| B | 稠密召回 + 交叉编码重排 | bge-m3 + bge-reranker-v2-m3 | 精度上界 |

## 目录

```
corpus/      原文 PDF 与下载脚本（校验 %PDF 魔数与 SHA-256）
data/        条款级切块、100 题评测集、评测集构建与标注体检脚本
src/         切块器、评测主程序、失败归因、图表、正文生成
docs/adr/    架构决策记录 ADR-001 / 003 / 004 / 005 / 006 / 007
results/     指标、失败归因、分阶段中间产物
figs/        白皮书图表
```

## 核心结论

多路融合的收益取决于两路检索器的强弱是否匹配：同一个 BM25 融入 384 维小模型使
Recall@1 提升 5.00 个百分点，融入 1024 维大模型却使其下降 6.50 个百分点。
根因是 RRF 只用排名不用分数，等权融合让弱侧的错误获得与强侧同等的权重。
详见白皮书 4.1 节与 ADR-003。

## 语料来源与版权

本仓库**不包含**法规原文，也不重新分发它们。

评测语料为香港证券及期货事务监察委员会（SFC）的两部法规：
《Code of Conduct for Persons Licensed by or Registered with the SFC》与
《Fund Manager Code of Conduct》。两份文件均载明
`© Securities and Futures Commission — All rights reserved.`，
明确禁止复制与存储，因此**原文 PDF 及其切块衍生文件（`data/chunks_v2.jsonl`）均已排除在版本库之外**。

仓库内提供的是取得与处理流程，复现方式：

```bash
./run_eval.sh          # 自动执行 corpus/fetch.py 从证监会官网取得原文（校验 %PDF 魔数与 SHA-256），
                       # 再由 src/chunk2.py 确定性地重建 498 个条款级切块
```

本仓库内属于作者原创、可自由取用的部分包括：100 题评测集（`data/eval_set_100.json`，
仅含问题文本与条款编号，不含法规正文）、全部评测与切块代码、指标结果、图表、
架构决策记录，以及白皮书。白皮书中对法规的引用均为供评述用途的简短摘引。

## 执行环境

1 vCPU / 约 1.5 GB 可用物理内存 / 3.6 GB Swap，PyTorch CPU 版。
bge-m3 与 reranker 的 fp32 权重各约 2.2 GB，单进程内无法共存，
故采用分阶段独立进程架构（见 ADR-006）。
