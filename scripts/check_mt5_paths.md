# Vérifier que le bot et l’EA utilisent le même dossier

## 1. Où Python écrit

Dans ton projet, le bot utilise le chemin défini dans **bot/.env** :

- **MT5_FILES_PATH** = dossier où sont créés `Command/`, `ticks_v3.json`, `status.json`.

Exemple actuel (à vérifier dans ton .env) :
```
MT5_FILES_PATH=/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files
```

## 2. Où l’EA lit (MT5)

Quand tu attaches **Sentinel_ToCompile** au graphique, regarde l’onglet **Experts** dans MT5. Au démarrage, l’EA affiche une ligne du type :

```
EA FILES PATH (copier dans .env MT5_FILES_PATH si différent): C:\...\MQL5\Files
```

- C’est le chemin **sous Windows (Wine)** que l’EA utilise pour lire `Command\*.json` et écrire `ticks_v3.json`, `status.json`.

## 3. Si les chemins ne correspondent pas

- **Sous Mac/Wine**, le `C:\...` de MT5 correspond en général à un chemin sous ton dossier Wine, par exemple :
  - `.../net.metaquotes.wine.metatrader5/drive_c/users/ton_user/Application Data/MetaQuotes/Terminal/XXXXX/MQL5/Files`
  - ou un autre `Terminal\XXXXX` selon l’installation.

À faire :

1. **Copier le chemin exact** affiché par l’EA dans l’onglet Experts (la ligne `EA FILES PATH`).
2. **Le convertir en chemin Mac** : remplace `C:\` par le répertoire Wine, par ex.  
   `.../net.metaquotes.wine.metatrader5/drive_c/`  
   et les `\` par `/`.
3. Mettre **ce chemin Mac** dans **bot/.env** comme **MT5_FILES_PATH**, puis redémarrer le bot.

Ainsi, le bot écrit dans le même dossier que celui où l’EA lit.

## 4. Vérifier que l’EA traite bien les ordres

- Recompile **Sentinel_ToCompile.mq5**, réattache-le au graphique.
- Dans l’onglet Experts, tu dois voir au démarrage :
  - `EA FILES PATH: ...`
  - `tradingEnabled: true`
- Toutes les ~10 s, si le bot envoie des ordres **dans ce même dossier**, tu devrais voir des lignes du type :
  - `Processed N command(s)` et/ou des messages d’exécution de trade.

Si tu ne vois **jamais** `Processed ... command(s)`, soit :
- l’EA lit un autre dossier (aligner MT5_FILES_PATH comme au §3),  
- soit le bot n’écrit pas dans le dossier affiché par l’EA (vérifier MT5_FILES_PATH dans .env).

## 5. Réinitialiser le Kill Switch (tradingEnabled)

Si l’EA affiche `tradingEnabled: false` :

- Supprimer le fichier d’état de l’EA (dans le même dossier que `MQL5\Files`) :  
  **Sentinel_State.dat**
- Redémarrer l’EA (détacher puis réattacher, ou redémarrer MT5).

Avec **TestingMode=true**, l’EA force désormais `tradingEnabled = true` au démarrage si c’était false.
