#!/bin/bash
LOG_FILE="/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Logs/20260119.log"
OUTPUT_FILE="/Users/macbookpro/Downloads/bot_project/recent_mt5_log.txt"

# Use strings to handle potential encoding issues, then tail
strings "$LOG_FILE" | tail -n 1000 > "$OUTPUT_FILE"
