#!/bin/sh
# print symbol, first and last complete date of the newest saved LSE macro_series tool-result file
d=/Users/rytty/.claude/projects/-Users-rytty-CCP-quant-v7/e3bb65bd-f34a-45ed-8f24-b212b5ca7be8/tool-results
f=$(ls -t $d/mcp-lse-terminal-macro_series-*.txt | head -1)
echo "$f"
grep -o '"symbol":"[^"]*","date":"[0-9-]*","value":[-0-9.e]*}' "$f" | sed -n '1p;$p'
grep -c truncated "$f"
