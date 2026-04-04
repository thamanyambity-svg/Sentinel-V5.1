"""
Dossier unique MT5 ↔ Python (bridge fichier).

Tout vit au même endroit : status.json, ticks_v3.json, metrics.json,
Command/, python_heartbeat.txt, ai_bias.json, etc.

Sous Mac + Wine, MetaTrader peut installer plusieurs racines (user/Common/Files,
Program Files/MetaTrader 5*, Terminal/<id>/MQL5/Files). On agrège toutes les
sources possibles et on retient le répertoire du status.json le plus récemment
modifié (preuve de vie EA), sauf si MT5_FILES_PATH pointe déjà vers un fichier
récent.
"""
from __future__ import annotations

import glob
import logging
import os
import time
from typing import List, Optional, Tuple

logger = logging.getLogger("MT5_PATH")

DRIVE_C = os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c"
)

DEFAULT_COMMON = os.path.expanduser(
    "~/Library/Application Support/net.metaquotes.wine.metatrader5"
    "/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files"
)


def _walk_status_metaquotes_files() -> List[str]:
    """Tout status.json sous .../MetaQuotes/.../Files (Common ou terminal ID)."""
    out: List[str] = []
    users = os.path.join(DRIVE_C, "users")
    if not os.path.isdir(users):
        return out
    for mq in glob.glob(os.path.join(users, "*", "AppData", "Roaming", "MetaQuotes")):
        if not os.path.isdir(mq):
            continue
        try:
            for root, _, files in os.walk(mq):
                if "status.json" not in files:
                    continue
                r = root.replace("\\", "/")
                if not r.rstrip("/").endswith("/Files"):
                    continue
                fp = os.path.join(root, "status.json")
                if os.path.isfile(fp):
                    out.append(fp)
        except OSError:
            continue
    return out


def _glob_status_files() -> List[str]:
    if not os.path.isdir(DRIVE_C):
        return []
    patterns = [
        os.path.join(
            DRIVE_C,
            "users",
            "*",
            "AppData",
            "Roaming",
            "MetaQuotes",
            "Terminal",
            "Common",
            "Files",
            "status.json",
        ),
        os.path.join(
            DRIVE_C,
            "users",
            "*",
            "AppData",
            "Roaming",
            "MetaQuotes",
            "Terminal",
            "*",
            "MQL5",
            "Files",
            "status.json",
        ),
        os.path.join(
            DRIVE_C,
            "Program Files",
            "MetaTrader 5",
            "MQL5",
            "Files",
            "status.json",
        ),
        os.path.join(DRIVE_C, "Program Files", "*", "MQL5", "Files", "status.json"),
        os.path.join(
            DRIVE_C,
            "Program Files (x86)",
            "*",
            "MQL5",
            "Files",
            "status.json",
        ),
    ]
    out: List[str] = []
    for pat in patterns:
        out.extend(glob.glob(pat))
    out.extend(_walk_status_metaquotes_files())
    return list(dict.fromkeys(out))


def list_status_candidates() -> List[Tuple[str, float, str]]:
    """Liste (dossier, mtime status.json, chemin fichier) triée par fraîcheur."""
    rows: List[Tuple[str, float, str]] = []
    for fp in _glob_status_files():
        try:
            m = os.path.getmtime(fp)
            rows.append((os.path.dirname(fp), m, fp))
        except OSError:
            continue
    rows.sort(key=lambda x: -x[1])
    return rows


def resolve_mt5_files_path(
    explicit: Optional[str] = None,
    stale_seconds: float = 120.0,
) -> Tuple[str, str]:
    """
    Retourne (chemin_dossier_unique, raison).

    * explicit_fresh : MT5_FILES_PATH OK (status récent)
    * auto_freshest : autre dossier a un status.json plus récent
    * explicit_only : pas de meilleur scan, on garde l’explicite
    * auto_or_default : pas d’explicite, meilleur trouvé
    * default_common : aucun status.json, repli Common Files user
    """
    explicit = (explicit or "").strip() or None

    candidates: List[Tuple[str, float]] = []
    for fp in _glob_status_files():
        try:
            m = os.path.getmtime(fp)
            candidates.append((os.path.dirname(fp), m))
        except OSError:
            continue

    newest_dir: Optional[str] = None
    newest_m = 0.0
    for d, m in candidates:
        if m > newest_m:
            newest_m = m
            newest_dir = d

    exp_t = 0.0
    if explicit and os.path.isdir(explicit):
        ef = os.path.join(explicit, "status.json")
        if os.path.isfile(ef):
            try:
                exp_t = os.path.getmtime(ef)
            except OSError:
                exp_t = 0.0

    if explicit and os.path.isdir(explicit) and exp_t > 0:
        exp_age = time.time() - exp_t
        if exp_age <= stale_seconds:
            return explicit, "explicit_fresh"

    if newest_dir and newest_m > exp_t:
        if explicit and exp_t > 0:
            logger.warning(
                "MT5: status.json dans MT5_FILES_PATH est vieux (%.0fs). "
                "Utilisation du plus récent: %s (%.0fs).",
                time.time() - exp_t,
                newest_dir,
                time.time() - newest_m,
            )
        elif explicit and exp_t == 0:
            logger.warning(
                "MT5: pas de status.json dans MT5_FILES_PATH (%s). "
                "Utilisation de: %s",
                explicit,
                newest_dir,
            )
        return newest_dir, "auto_freshest"

    if explicit and os.path.isdir(explicit):
        return explicit, "explicit_only"

    if newest_dir:
        return newest_dir, "auto_or_default"

    return DEFAULT_COMMON, "default_common"
