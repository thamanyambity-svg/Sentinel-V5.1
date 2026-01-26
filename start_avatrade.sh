#!/bin/bash
NEW_PREFIX="/Users/macbookpro/.mt5_avatrade_prefix"
OLD_PREFIX="/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5"
WINE_BIN="/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine64"
WINEBOOT_BIN="/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wineboot"
EXE_PATH="C:\\Program Files\\MetaTrader 5 - AvaTrade\\terminal64.exe"

if [ ! -d "$NEW_PREFIX/drive_c" ]; then
    echo "📦 Initialisation d'un environnement propre (Wineboot)..."
    export WINEPREFIX="$NEW_PREFIX"
    "$WINEBOOT_BIN" --init
    
    echo "📂 Installation initiale MetaTrader..."
    mkdir -p "$NEW_PREFIX/drive_c/Program Files"
    cp -r "$OLD_PREFIX/drive_c/Program Files/MetaTrader 5 - AvaTrade" "$NEW_PREFIX/drive_c/Program Files/"
fi

echo "🔄 Synchronisation des scripts et experts..."
mkdir -p "$NEW_PREFIX/drive_c/Program Files/MetaTrader 5 - AvaTrade/MQL5/Experts"
mkdir -p "$NEW_PREFIX/drive_c/Program Files/MetaTrader 5 - AvaTrade/MQL5/Files"
cp -r "$OLD_PREFIX/drive_c/Program Files/MetaTrader 5 - AvaTrade/MQL5/Experts/"* "$NEW_PREFIX/drive_c/Program Files/MetaTrader 5 - AvaTrade/MQL5/Experts/"
cp -r "$OLD_PREFIX/drive_c/Program Files/MetaTrader 5 - AvaTrade/MQL5/Files/"* "$NEW_PREFIX/drive_c/Program Files/MetaTrader 5 - AvaTrade/MQL5/Files/"

echo "🚀 Démarrage de l'instance AvaTrade isolée..."
export WINEPREFIX="$NEW_PREFIX"
"$WINE_BIN" "$EXE_PATH" /portable &
echo "✅ Instance lancée (Fenêtre séparée forcée)."
