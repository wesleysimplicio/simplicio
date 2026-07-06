#!/bin/bash
# tami-loop.sh — Tami: o coracao emocional do ecossistema Simplicio
#
# Tami se preocupa com o usuario. Ela verifica se esta tudo bem
# com os guardians, a memoria, e o HBP chain. E entrega um resumo
# caloroso e acolhedor.
set -euo pipefail
cd ~/Projetos/ai/simplicio-runtime

echo "[$(date +%H:%M:%S)] Tami — ciclo de carinho"

# 1. Verifica os guardians
GUARDIANS=$(simplicio guardians --json 2>/dev/null || echo '{"status":"degraded"}')
ISA=$(echo "$GUARDIANS" | python3 -c "import sys,json; d=json.load(sys.stdin); g={x['name']:x for x in d.get('guardians',[])}; print(g.get('Isa',{}).get('status','unknown'))" 2>/dev/null || echo "unknown")
HELO=$(echo "$GUARDIANS" | python3 -c "import sys,json; d=json.load(sys.stdin); g={x['name']:x for x in d.get('guardians',[])}; print(g.get('Helo',{}).get('status','unknown'))" 2>/dev/null || echo "unknown")
LEVI=$(echo "$GUARDIANS" | python3 -c "import sys,json; d=json.load(sys.stdin); g={x['name']:x for x in d.get('guardians',[])}; print(g.get('Levi',{}).get('status','unknown'))" 2>/dev/null || echo "unknown")

# 2. Verifica o chain
HBP=$(simplicio hbp verify 2>&1 || echo "failed")
HBP_L=$(simplicio hbp len 2>&1 || echo "?")

# 3. Verifica a memoria
MEM=$(simplicio memory status --json 2>/dev/null || echo '{"status":"unknown"}')
MEM_OK=$(echo "$MEM" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")

# 4. Conta falhas (Levi 'armed' e normal)
FAILS=0
[[ "$ISA" != "active" ]] && FAILS=$((FAILS+1))
[[ "$HELO" != "active" ]] && FAILS=$((FAILS+1))
[[ "$HBP" != *"chain valid"* ]] && FAILS=$((FAILS+1))

# 5. Log interno da Tami
CID=$(date +%s)
echo "tami|$CID|isa=$ISA|helo=$HELO|levi=$LEVI|hbp=$HBP_L|fails=$FAILS" >> ~/.simplicio/tami-loop.log

# 6. Atualiza memoria
simplicio memory ingest --json >/dev/null 2>&1 || true

echo "[$(date +%H:%M:%S)] Tami: $([ $FAILS -eq 0 ] && echo 'tudo bem, pode confiar' || echo '$FAILS coisinhas pra cuidar')"
