#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║  SENTINEL V10 — run_backtest_pipeline.sh                        ║
# ║  Pipeline complet de backtest en 1 commande                     ║
# ║                                                                  ║
# ║  Usage:                                                          ║
# ║    ./run_backtest_pipeline.sh                                    ║
# ║    ./run_backtest_pipeline.sh --report trade_log_all.jsonl      ║
# ║    ./run_backtest_pipeline.sh --capital 500 --demo              ║
# ╚══════════════════════════════════════════════════════════════════╝

set -euo pipefail

# ── Couleurs terminal ─────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

# ── Valeurs par défaut ────────────────────────────────────────────
REPORT="trade_log_all.jsonl"
CAPITAL=1000
SPLIT_DATE=""
DEMO_MODE=false
SKIP_ML=false
SKIP_OPT=false
EXPORT_JSON="backtest_summary.json"

# ── Parsing des arguments ─────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --report)   REPORT="$2";      shift 2 ;;
        --capital)  CAPITAL="$2";     shift 2 ;;
        --split)    SPLIT_DATE="$2";  shift 2 ;;
        --demo)     DEMO_MODE=true;   shift   ;;
        --skip-ml)  SKIP_ML=true;     shift   ;;
        --skip-opt) SKIP_OPT=true;    shift   ;;
        --export)   EXPORT_JSON="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--report FILE] [--capital N] [--split DATE] [--demo] [--skip-ml] [--skip-opt]"
            exit 0 ;;
        *) echo -e "${RED}Argument inconnu: $1${RESET}"; exit 1 ;;
    esac
done

# ── Résolution du répertoire du projet ───────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Résolution Python ─────────────────────────────────────────────
PYTHON=""
for PY in python3 python; do
    if command -v "$PY" &>/dev/null; then
        PYTHON="$PY"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo -e "${RED}❌ Python introuvable — installez Python 3.9+${RESET}"
    exit 1
fi

# ── Activation du venv si disponible ─────────────────────────────
if [[ -f ".venv/bin/activate" ]]; then
    source ".venv/bin/activate"
    echo -e "${CYAN}[ENV] Venv .venv activé${RESET}"
elif [[ -f "venv/bin/activate" ]]; then
    source "venv/bin/activate"
    echo -e "${CYAN}[ENV] Venv venv activé${RESET}"
fi

# ── Banner ────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${CYAN}║     SENTINEL V10 — BACKTEST PIPELINE                ║${RESET}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
echo -e "  Répertoire : ${BOLD}$SCRIPT_DIR${RESET}"
echo -e "  Python     : ${BOLD}$($PYTHON --version 2>&1)${RESET}"
echo -e "  Capital    : ${BOLD}\$$CAPITAL${RESET}"
if $DEMO_MODE; then
    echo -e "  Mode       : ${YELLOW}DEMO (données synthétiques)${RESET}"
else
    echo -e "  Rapport    : ${BOLD}$REPORT${RESET}"
fi
echo ""

STEP=0
ERRORS=0
START_TIME=$(date +%s)

log_step() {
    STEP=$((STEP + 1))
    echo -e "\n${BOLD}${CYAN}── Étape $STEP : $1 ──────────────────────────────────────────${RESET}"
}

log_ok()    { echo -e "  ${GREEN}✅ $1${RESET}"; }
log_warn()  { echo -e "  ${YELLOW}⚠️  $1${RESET}"; }
log_error() { echo -e "  ${RED}❌ $1${RESET}"; ERRORS=$((ERRORS + 1)); }

# ════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Vérification de l'environnement
# ════════════════════════════════════════════════════════════════
log_step "Vérification de l'environnement"

for MOD in json math statistics argparse pathlib; do
    $PYTHON -c "import $MOD" 2>/dev/null && log_ok "$MOD" || log_error "Module manquant: $MOD"
done

# Vérification fichier de trades
if ! $DEMO_MODE && [[ ! -f "$REPORT" ]]; then
    log_warn "Fichier '$REPORT' introuvable → passage en mode DEMO automatique"
    DEMO_MODE=true
fi

# ════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Analyse Backtest (backtest_analyzer.py)
# ════════════════════════════════════════════════════════════════
log_step "Analyse Backtest (backtest_analyzer.py)"

if [[ ! -f "backtest_analyzer.py" ]]; then
    log_error "backtest_analyzer.py introuvable"
    exit 1
fi

ANALYZER_ARGS="--capital $CAPITAL --export $EXPORT_JSON"
if $DEMO_MODE; then
    ANALYZER_ARGS="$ANALYZER_ARGS --demo"
else
    ANALYZER_ARGS="$ANALYZER_ARGS --report $REPORT"
fi
if [[ -n "$SPLIT_DATE" ]]; then
    ANALYZER_ARGS="$ANALYZER_ARGS --split $SPLIT_DATE"
fi

if $PYTHON backtest_analyzer.py $ANALYZER_ARGS; then
    log_ok "Analyse terminée → $EXPORT_JSON"
else
    log_error "backtest_analyzer.py a échoué"
fi

# ════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Optimisation (optimizer.py)
# ════════════════════════════════════════════════════════════════
log_step "Optimisation des paramètres (optimizer.py)"

if $SKIP_OPT; then
    log_warn "Skipped (--skip-opt)"
elif [[ ! -f "optimizer.py" ]]; then
    log_warn "optimizer.py introuvable — étape ignorée"
else
    OPT_ARGS="--capital $CAPITAL"
    if ! $DEMO_MODE && [[ -f "$REPORT" ]]; then
        OPT_ARGS="$OPT_ARGS --history $REPORT"
    fi

    if $PYTHON optimizer.py $OPT_ARGS 2>&1 | head -50; then
        log_ok "Optimisation terminée → optimization_results.json"
    else
        log_warn "optimizer.py terminé avec des avertissements"
    fi
fi

# ════════════════════════════════════════════════════════════════
# ÉTAPE 4 — Module ML (ml_engine.py)
# ════════════════════════════════════════════════════════════════
log_step "Module ML / Feature Engine (ml_engine.py)"

if $SKIP_ML; then
    log_warn "Skipped (--skip-ml)"
elif [[ ! -f "ml_engine.py" ]]; then
    log_warn "ml_engine.py introuvable — étape ignorée"
else
    ML_ARGS=""
    if ! $DEMO_MODE && [[ -f "$REPORT" ]]; then
        ML_ARGS="--data $REPORT"
    fi

    if $PYTHON -c "
from ml_engine import generate_synthetic_trades
trades = generate_synthetic_trades(100, seed=42)
print(f'  ML Engine OK — {len(trades)} trades synthétiques générés')
" 2>&1; then
        log_ok "ML Engine fonctionnel"
    else
        log_warn "ML Engine non disponible"
    fi
fi

# ════════════════════════════════════════════════════════════════
# ÉTAPE 5 — AutoTrainer status (auto_trainer.py)
# ════════════════════════════════════════════════════════════════
log_step "Statut AutoTrainer (auto_trainer.py)"

if [[ ! -f "auto_trainer.py" ]]; then
    log_warn "auto_trainer.py introuvable — étape ignorée"
else
    TMPPY=$(mktemp /tmp/sentinel_at_XXXXXX.py)
    cat > "$TMPPY" <<'EOF'
import json, os, sys
path = 'training_history.json'
if os.path.exists(path):
    with open(path) as f:
        h = json.load(f)
    runs = h if isinstance(h, list) else h.get('runs', [])
    n = len(runs)
    print(f"  AutoTrainer OK: {n} session(s) enregistree(s)")
    if runs:
        last = runs[-1]
        ts  = str(last.get('ts', last.get('date', '?')))[:10]
        auc = last.get('auc', last.get('accuracy', '?'))
        wr  = last.get('win_rate', last.get('success', '?'))
        print(f"  Derniere session: {ts}  AUC={auc}  WR={wr}")
else:
    print("  AutoTrainer: aucune session (premier demarrage)")
EOF
    if $PYTHON "$TMPPY" 2>&1; then
        log_ok "AutoTrainer statut OK"
    else
        log_warn "Impossible de lire le statut AutoTrainer"
    fi
    rm -f "$TMPPY"
fi

# ════════════════════════════════════════════════════════════════
# ÉTAPE 6 — Lecture du résumé JSON généré
# ════════════════════════════════════════════════════════════════
log_step "Lecture du résumé final"

if [[ -f "$EXPORT_JSON" ]]; then
    $PYTHON -c "
import json, sys
with open('$EXPORT_JSON') as f:
    s = json.load(f)

pf  = s.get('profit_factor', 0)
wr  = s.get('win_rate', 0)
dd  = s.get('max_drawdown_pct', 0)
sh  = s.get('sharpe', 0)
ret = s.get('return_pct', 0)
wfe_val = s.get('wfe', {}).get('wfe', 0) if isinstance(s.get('wfe'), dict) else 0

ok_pf  = '✅' if pf  >= 1.25 else '❌'
ok_dd  = '✅' if dd  <= 20   else '❌'
ok_sh  = '✅' if sh  >= 0.8  else '⚠️'
ok_wfe = '✅' if wfe_val >= 0.4 else '⚠️'

print(f'''
  ┌─────────────────────────────────────────┐
  │  RÉSUMÉ FINAL                           │
  ├─────────────────────────────────────────┤
  │  Profit Factor : {pf:>6.3f}              {ok_pf}  │
  │  Win Rate      : {wr*100:>5.1f}%              │
  │  Max Drawdown  : {dd:>5.1f}%              {ok_dd}  │
  │  Sharpe Ratio  : {sh:>6.2f}              {ok_sh}  │
  │  Retour total  : {ret:>+6.1f}%                │
  │  WFE           : {wfe_val:>6.3f}              {ok_wfe}  │
  └─────────────────────────────────────────┘''')
" 2>&1
else
    log_warn "Aucun résumé JSON trouvé"
fi

# ════════════════════════════════════════════════════════════════
# FIN DU PIPELINE
# ════════════════════════════════════════════════════════════════
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════╗${RESET}"
if [[ $ERRORS -eq 0 ]]; then
    echo -e "${BOLD}${GREEN}║  ✅ PIPELINE TERMINÉ AVEC SUCCÈS ($DURATION sec)       ║${RESET}"
else
    echo -e "${BOLD}${YELLOW}║  ⚠️  PIPELINE TERMINÉ — $ERRORS erreur(s) ($DURATION sec)  ║${RESET}"
fi
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  Étapes suivantes :"
echo -e "  ${CYAN}python dashboard.py${RESET}          → Dashboard live temps réel"
echo -e "  ${CYAN}python start_production.py${RESET}   → Démarrer le système complet"
echo ""
