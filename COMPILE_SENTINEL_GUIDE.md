# 📋 GUIDE DE COMPILATION - SENTINEL DEMO v4.7

## ✅ Fichier copié automatiquement

**Emplacement** :

```
/Users/macbookpro/Library/Application Support/
  net.metaquotes.wine.metatrader5/drive_c/
  Program Files/MetaTrader 5/MQL5/Experts/
  → Sentinel_DEMO_Test.mq5
```

---

## 🔧 ÉTAPES DE COMPILATION

### 1. Ouvrir MT5

- Lancer MetaTrader 5
- Se connecter au compte DEMO XM (167933585)

### 2. Ouvrir MetaEditor

- Dans MT5, appuyer sur **F4**
- Ou : Tools → MetaQuotes Language Editor

### 3. Compiler le fichier

- Dans MetaEditor Navigator (gauche)
- Aller dans : **Experts** → `Sentinel_DEMO_Test.mq5`
- Clic droit → **Compiler** (ou F7)
- Vérifier : "0 error(s), 0 warning(s)"

### 4. Activer l'EA sur un graphique

- Retour dans MT5
- Ouvrir graphique **EURUSD** (M1 ou M5)
- Navigator (Ctrl+N) → **Expert Advisors**
- Glisser-déposer `Sentinel_DEMO_Test` sur le graphique
- Cocher :
  - ✅ "Allow Algo Trading"
  - ✅ "Allow DLL imports"
- Cliquer **OK**

### 5. Activer AutoTrading

- Cliquer le bouton **AutoTrading** (devient vert)
- Vérifier l'icône 😊 en haut à droite du graphique

---

## 🔍 VÉRIFICATIONS POST-COMPILATION

### Dans le dossier Files

Vérifier la création de :

```
/MQL5/Files/
  ├── Command/          ← Dossier pour commandes Python
  ├── status.json       ← Créé par Sentinel
  └── dashboard.html    ← Dashboard temps réel
```

### Dans les Logs MT5

Chercher :

```
🏰 SENTINEL V4.7: REPORTING ENGINE ACTIVE
```

### Test de communication

Depuis Python :

```bash
python test_bridge_xm.py
```

---

## ⚠️ EN CAS D'ERREUR DE COMPILATION

### Erreur: "Cannot open include file"

- Vérifier que Trade.mqh existe dans MQL5/Include/Trade/
- Réinstaller MT5 si nécessaire

### Erreur: "Syntax error"

- Le fichier peut être corrompu
- Re-copier depuis bot/broker/mt5_bridge/Sentinel_v4_7.mq5

### EA ne démarre pas

- Vérifier AutoTrading activé
- Vérifier "Allow Algo Trading" coché dans les settings

---

## 📞 COMMANDES UTILES

### Vérifier fichier copié

```bash
ls -lh "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Experts/" | grep Sentinel
```

### Re-copier si besoin

```bash
cd /Users/macbookpro/Downloads/bot_project
cp "bot/broker/mt5_bridge/Sentinel_v4_7.mq5" "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Experts/Sentinel_DEMO_Test.mq5"
```
