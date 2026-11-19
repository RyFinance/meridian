#!/bin/zsh
# ing.sh <tool-result id> <symbol> <order> <start> [dataset]  -- ingest one direct MCP macro_series reply
TR=/Users/rytty/.claude/projects/-Users-rytty-CCP-quant-v7/e3bb65bd-f34a-45ed-8f24-b212b5ca7be8/tool-results
DS=${5:-bonds}
cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.cycle7.data_fi.lse_ingest $TR/mcp-lse-terminal-macro_series-$1.txt "{\"symbol\":\"$2\",\"dataset\":\"$DS\",\"start\":\"$4\",\"end\":\"2026-09-30\",\"limit\":5000,\"order\":\"$3\"}" 2>&1 | grep -v cpu_info | sed "s/^/$2 $3 $4: /"
