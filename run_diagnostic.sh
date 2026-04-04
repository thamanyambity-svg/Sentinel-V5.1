
echo '=== 1. LOGS EA (50 dernières lignes) ===' && find ~/Library/Application\ Support/net.metaquotes.wine.metatrader5   -name '*.log' 2>/dev/null |   xargs grep -h 'Aladdin\|WARN\|SIM\|TIMER\|Session\|Blocked\|INIT\|ERROR\|signal\|trade\|TRADE'   2>/dev/null | tail -50

echo '' && echo '=== 2. STATUS.JSON ===' && cat ~/Library/Application\ Support/net.metaquotes.wine.metatrader5/drive_c/Program\ Files/MetaTrader\ 5/MQL5/Files/status.json 2>/dev/null || find ~/Library/Application\ Support/net.metaquotes.wine.metatrader5   -name 'status.json' 2>/dev/null | xargs cat 2>/dev/null || echo 'status.json INTROUVABLE'

echo '' && echo '=== 3. TICKS (symboles actifs) ===' && find ~/Library/Application\ Support/net.metaquotes.wine.metatrader5   -name 'ticks_v3.json' 2>/dev/null | xargs cat 2>/dev/null || echo 'ticks_v3.json INTROUVABLE'

echo '' && echo '=== 4. HEARTBEAT ===' && find ~/Library/Application\ Support/net.metaquotes.wine.metatrader5   -name 'heartbeat.txt' 2>/dev/null | xargs cat 2>/dev/null || echo 'heartbeat.txt INTROUVABLE'

echo '' && echo '=== 5. FICHIERS MQL5/Files ===' && find ~/Library/Application\ Support/net.metaquotes.wine.metatrader5   -name '*.json' -o -name '*.txt' 2>/dev/null | grep -v '\.wine\|cache\|temp' | head -30

