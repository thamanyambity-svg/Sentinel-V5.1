import csv
import os
import shutil
from datetime import datetime

class TradeLogger:
    def __init__(self, filename="training_data_v75.csv"):
        self.filename = filename
        self.headers = [
            "Timestamp",      # Date et heure
            "Symbol",         # Ex: Volatility 75 Index
            "Close_Price",    # Prix de fermeture de la bougie
            "RSI_Value",      # La valeur de votre indicateur actuel
            "AI_Decision",    # BUY, SELL, ou WAIT
            "AI_Confidence",  # (Optionnel) Si Groq donne un % de confiance
            "AI_Reasoning"    # L'explication textuelle complète de Groq
        ]
        self.backup_dir = os.path.join(os.path.dirname(self.filename), "backups")
        self.last_backup_hour = None
        self._initialize_file()

    def _initialize_file(self):
        """Crée le fichier avec les en-têtes si il n'existe pas encore."""
        # Use absolute path relative to bot root if needed, but relative to CWD is fine for now
        if not os.path.exists(self.filename):
            try:
                with open(self.filename, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow(self.headers)
                print(f"[LOGGER] Fichier {self.filename} créé avec succès.")
            except Exception as e:
                print(f"[ERREUR LOGGER] Impossible de créer le fichier CSV : {e}")
        
        # Ensure backup directory exists
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir, exist_ok=True)

    def _check_and_perform_backup(self):
        """
        Creates a backup copy of the CSV file if the hour has changed.
        This ensures we have hourly/daily snapshots.
        """
        current_hour = datetime.now().strftime("%Y-%m-%d_%H")
        
        # Only backup if we haven't done so this hour
        if self.last_backup_hour != current_hour:
            try:
                if os.path.exists(self.filename) and os.path.getsize(self.filename) > 0:
                    backup_filename = f"training_data_{current_hour}.csv"
                    backup_path = os.path.join(self.backup_dir, backup_filename)
                    shutil.copy2(self.filename, backup_path)
                    print(f"[BACKUP] Sauvegarde effectuée : {backup_path}")
                    self.last_backup_hour = current_hour
            except Exception as e:
                print(f"[ERREUR BACKUP] Échec de la sauvegarde : {e}")

    def log_tick(self, symbol, close_price, rsi, decision, reasoning, confidence="N/A"):
        """
        Enregistre une ligne de données.
        À appeler à chaque fois que le bot prend une décision (même WAIT).
        """
        # Check for backup before writing new data
        self._check_and_perform_backup()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Ensure SAFE strings for CSV (remove newlines in text fields)
        safe_reasoning = str(reasoning).replace("\n", " ").replace("\r", " ").strip()
        
        row_data = [
            timestamp,
            symbol,
            close_price,
            rsi,
            decision,
            confidence,
            safe_reasoning 
        ]

        try:
            with open(self.filename, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(row_data)
        except Exception as e:
            print(f"[ERREUR LOGGER] Impossible d'écrire dans le CSV : {e}")
