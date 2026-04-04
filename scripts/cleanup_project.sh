#!/bin/bash
# =============================================================
# cleanup_project.sh — Aladdin Bot Project Cleanup
# Version : 1.0 — Safe cleanup with archive & confirmation
# Usage   : bash cleanup_project.sh
# =============================================================

set -e  # Stop on first error

# ── Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ── Répertoire racine du projet
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESEARCH_DIR="$PROJECT_DIR/research"
BACKUP_DIR="$PROJECT_DIR/backups_archive"
DATE=$(date +%Y%m%d_%H%M%S)

echo ""
echo -e "${BOLD}${CYAN}=============================================================${RESET}"
echo -e "${BOLD}${CYAN}   ALADDIN BOT — CLEANUP & LOGGING OPTIMIZATION v1.0        ${RESET}"
echo -e "${BOLD}${CYAN}=============================================================${RESET}"
echo -e "  Répertoire projet : ${PROJECT_DIR}"
echo -e "  Date              : ${DATE}"
echo ""

# =============================================================
# ÉTAPE 0 — CONFIRMATION BOT ARRÊTÉ
# =============================================================
echo -e "${BOLD}${YELLOW}⚠️  ÉTAPE 0 — SÉCURITÉ${RESET}"
echo -e "Ce script va vider les logs et déplacer des fichiers."
echo -e "${RED}Le bot Aladdin et sentinel_server DOIVENT être arrêtés.${RESET}"
echo ""
read -p "Confirmes-tu que le bot est bien ARRÊTÉ ? (oui/non) : " confirm_stop
if [[ "$confirm_stop" != "oui" ]]; then
    echo -e "${RED}Abandon. Arrête le bot d'abord, puis relance ce script.${RESET}"
    exit 1
fi

# Vérification processus actifs
if pgrep -f "sentinel_server" > /dev/null 2>&1; then
    echo -e "${RED}ERREUR : sentinel_server tourne encore ! Arrête-le d'abord.${RESET}"
    exit 1
fi
if pgrep -f "run_bot.sh" > /dev/null 2>&1; then
    echo -e "${RED}ERREUR : run_bot.sh tourne encore ! Arrête-le d'abord.${RESET}"
    exit 1
fi

echo -e "${GREEN}✅ Bot arrêté confirmé.${RESET}"
echo ""

# =============================================================
# ÉTAPE 1 — CRÉER LES DOSSIERS
# =============================================================
echo -e "${BOLD}📁 ÉTAPE 1 — Création des dossiers${RESET}"

mkdir -p "$RESEARCH_DIR"
mkdir -p "$BACKUP_DIR"

echo -e "  ${GREEN}✅ research/${RESET} créé"
echo -e "  ${GREEN}✅ backups_archive/${RESET} créé"
echo ""

# =============================================================
# ÉTAPE 2 — ARCHIVER LES FICHIERS .BAK ET BACKUPS .PKL
# =============================================================
echo -e "${BOLD}💾 ÉTAPE 2 — Archive des backups${RESET}"

moved_bak=0
for f in "$PROJECT_DIR"/*.bak* "$PROJECT_DIR"/*_backup.pkl "$PROJECT_DIR"/*.bak; do
    [ -f "$f" ] || continue
    filename=$(basename "$f")
    mv "$f" "$BACKUP_DIR/${filename}"
    echo -e "  ${CYAN}→ $filename${RESET} archivé dans backups_archive/"
    ((moved_bak++)) || true
done

# CRITIQUE : s'assurer que les modèles actifs n'ont pas été bougés
CRITICAL_FILES=("model_xgb.pkl" "nexus_quantum_weights.pth")
for cf in "${CRITICAL_FILES[@]}"; do
    # Si par erreur déplacé, on le remet
    if [ -f "$BACKUP_DIR/$cf" ] && [ ! -f "$PROJECT_DIR/$cf" ]; then
        mv "$BACKUP_DIR/$cf" "$PROJECT_DIR/$cf"
        echo -e "  ${YELLOW}⚠️  $cf restauré (modèle actif protégé)${RESET}"
    fi
    if [ -f "$PROJECT_DIR/$cf" ]; then
        echo -e "  ${GREEN}🛡️  $cf en place (modèle actif — intouché)${RESET}"
    fi
done

echo -e "  ${GREEN}✅ $moved_bak fichier(s) backup archivé(s)${RESET}"
echo ""

# =============================================================
# ÉTAPE 3 — DÉPLACER LES SCRIPTS UTILITAIRES VERS RESEARCH
# =============================================================
echo -e "${BOLD}🔬 ÉTAPE 3 — Déplacement scripts utilitaires → research/${RESET}"

UTIL_PATTERNS=(
    "test_*.py"
    "check_*.py"
    "verify_*.py"
    "debug_*.py"
    "diagnose*.sh"
    "force_*.py"
    "send_test_*.py"
    "check_account.py"
    "send_test_trade.py"
)

moved_scripts=0
for pattern in "${UTIL_PATTERNS[@]}"; do
    for f in "$PROJECT_DIR"/$pattern; do
        [ -f "$f" ] || continue
        filename=$(basename "$f")
        # Ne pas déplacer le script lui-même (si lancé depuis un autre endroit)
        [[ "$f" == *"/scripts/cleanup_project.sh" ]] && continue
        mv "$f" "$RESEARCH_DIR/$filename"
        echo -e "  ${CYAN}→ $filename${RESET} déplacé vers research/"
        ((moved_scripts++)) || true
    done
done

echo -e "  ${GREEN}✅ $moved_scripts script(s) déplacé(s)${RESET}"
echo ""

# =============================================================
# ÉTAPE 4 — NETTOYAGE SÉCURISÉ DES LOGS
# =============================================================
echo -e "${BOLD}📋 ÉTAPE 4 — Nettoyage sécurisé des logs${RESET}"

LOGS_TO_CLEAR=(
    "bot.log"
    "server_uvicorn.log"
    "debug_run.log"
    "bot_output.log"
    "system.log"
)

cleared_logs=0
for log in "${LOGS_TO_CLEAR[@]}"; do
    logpath="$PROJECT_DIR/$log"
    [ -f "$logpath" ] || continue

    size=$(du -sh "$logpath" 2>/dev/null | cut -f1)
    echo ""
    echo -e "  ${YELLOW}Log trouvé : $log ($size)${RESET}"
    read -p "  Vider ce log ? (oui/non) : " confirm_log

    if [[ "$confirm_log" == "oui" ]]; then
        # Backup avant vidage
        cp "$logpath" "$BACKUP_DIR/${log}_${DATE}.bak"
        : > "$logpath"
        echo -e "  ${GREEN}✅ $log vidé (backup dans backups_archive/)${RESET}"
        ((cleared_logs++)) || true
    else
        echo -e "  ${CYAN}⏭️  $log ignoré${RESET}"
    fi
done

echo ""
echo -e "  ${GREEN}✅ $cleared_logs log(s) vidé(s) proprement${RESET}"
echo ""

# =============================================================
# ÉTAPE 5 — MISE À JOUR .GITIGNORE
# =============================================================
echo -e "${BOLD}📝 ÉTAPE 5 — Mise à jour .gitignore${RESET}"

GITIGNORE="$PROJECT_DIR/.gitignore"
touch "$GITIGNORE"

GITIGNORE_ENTRIES=(
    "# Logs"
    "*.log"
    "bot_output.log"
    "# Archives et backups"
    "backups_archive/"
    "*.bak"
    "*_backup.pkl"
    "# Modèles ML (trop lourds pour git)"
    "*.pth"
    "# Environnement Python"
    "__pycache__/"
    "*.pyc"
    ".env"
    "venv/"
)

echo "" >> "$GITIGNORE"
echo "# === Ajouté par cleanup_project.sh $DATE ===" >> "$GITIGNORE"
for entry in "${GITIGNORE_ENTRIES[@]}"; do
    # N'ajouter que si pas déjà présent
    if ! grep -qF "$entry" "$GITIGNORE" 2>/dev/null; then
        echo "$entry" >> "$GITIGNORE"
        echo -e "  ${CYAN}+ $entry${RESET}"
    fi
done

echo -e "  ${GREEN}✅ .gitignore mis à jour${RESET}"
echo ""

# =============================================================
# ÉTAPE 6 — VÉRIFICATION FINALE
# =============================================================
echo -e "${BOLD}🔍 ÉTAPE 6 — Vérification finale${RESET}"

root_count=$(ls -1 "$PROJECT_DIR"/*.py "$PROJECT_DIR"/*.sh 2>/dev/null | wc -l)
research_count=$(ls -1 "$RESEARCH_DIR" 2>/dev/null | wc -l)
backup_count=$(ls -1 "$BACKUP_DIR" 2>/dev/null | wc -l)

echo ""
echo -e "${BOLD}${CYAN}=============================================================${RESET}"
echo -e "${BOLD}  RÉSUMÉ DU CLEANUP${RESET}"
echo -e "${BOLD}${CYAN}=============================================================${RESET}"
echo -e "  Scripts racine restants : ${BOLD}$root_count${RESET}"
echo -e "  Fichiers dans research/ : ${BOLD}$research_count${RESET}"
echo -e "  Fichiers archivés       : ${BOLD}$backup_count${RESET}"
echo -e "  Scripts déplacés        : ${GREEN}$moved_scripts${RESET}"
echo -e "  Logs vidés              : ${GREEN}$cleared_logs${RESET}"
echo -e "  Backups archivés        : ${GREEN}$moved_bak${RESET}"
echo ""

# Vérification modèles critiques
echo -e "${BOLD}  Modèles actifs (vérification finale) :${RESET}"
for cf in "${CRITICAL_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$cf" ]; then
        echo -e "  ${GREEN}✅ $cf — en place${RESET}"
    else
        echo -e "  ${RED}❌ $cf — MANQUANT ! Vérifie dans backups_archive/${RESET}"
    fi
done

echo ""
echo -e "${BOLD}${GREEN}✅ Cleanup terminé. Tu peux relancer le bot.${RESET}"
echo -e "${BOLD}${CYAN}=============================================================${RESET}"
echo ""
