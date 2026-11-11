#!/usr/bin/env bash
# =============================================================================
#  SFC Regulatory RAG Benchmark — single-entry reproduction script
#
#  Usage:
#     ./run_eval.sh              full pipeline (chunk -> eval -> figures -> PDF)
#     ./run_eval.sh eval         retrieval evaluation only
#     ./run_eval.sh report       figures + whitepaper + PDF only
#     ./run_eval.sh rescore      re-score from cached rankings (no re-encoding)
#
#  Models are read from ./models/ or from $MODEL_DIR.
#  Heavy stages (m3, rerank) run as separate processes so the OS reclaims
#  memory between them — see docs/adr/adr-006.md.
# =============================================================================
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

MODE="${1:-all}"
PY="${PYTHON:-python3}"
log() { printf '\n\033[1;34m[%s]\033[0m %s\n' "$(date -u +%H:%M:%S)" "$*"; }
run() { log "$1"; shift; "$@"; }

build_corpus() {
    [ -f corpus/sfc_code_of_conduct.pdf ] || run "Fetching SFC source PDFs" $PY corpus/fetch.py
    run "Chunking regulations into clause-level units" $PY src/chunk2.py
    run "Building the 100-question evaluation set"     $PY data/build_eval_set.py
    run "Auditing gold-clause annotations"             $PY data/audit_eval_set.py
}

run_eval() {
    for STAGE in bm25 small hybrid m3 hybridm3 rerank merge; do
        log "Evaluation stage: ${STAGE}"
        free -m | sed -n '2p' || true
        $PY -u src/eval_rag_cpu.py "$STAGE"
    done
}

build_report() {
    run "Analysing retrieval failures" $PY src/analyze_failures.py
    run "Rendering figures"            $PY src/make_figs.py
    run "Generating whitepaper body"   $PY src/gen_whitepaper.py
    run "Compiling PDF"                $PY build_pdf.py
    run "Verifying deliverable"        $PY verify_whitepaper.py
}

case "$MODE" in
    all)     build_corpus; run_eval; build_report ;;
    corpus)  build_corpus ;;
    eval)    run_eval ;;
    rescore) run "Re-scoring from cached rankings" $PY -u src/eval_rag_cpu.py rescore
             $PY -u src/eval_rag_cpu.py merge; build_report ;;
    report)  build_report ;;
    *) echo "Unknown mode: $MODE (expected: all | corpus | eval | rescore | report)"; exit 2 ;;
esac

log "Done. Artefacts:"
printf '   %s\n' \
  "data/chunks_v2.jsonl        clause-level corpus" \
  "data/eval_set_100.json      evaluation set" \
  "results/metrics_rag.json    retrieval metrics (6 configurations)" \
  "results/failure_analysis.json" \
  "HK_Financial_Regulatory_RAG_Benchmark_Whitepaper.pdf"
