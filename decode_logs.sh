#!/bin/bash
LOG_FILE="/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Logs/20260119.log"
OUTPUT_FILE="decoded_logs_shell.txt"

if [ -f "$LOG_FILE" ]; then
    echo "Found log file. converting..." > debug_iconv.txt
    # Use iconv to convert from UTF-16LE to UTF-8
    # Tail last 5000 bytes first to avoid processing huge files, then convert
    tail -c 10000 "$LOG_FILE" > temp_tail.log
    
    # Try iconv; if it fails, try simple cat (some logs might be utf8)
    if iconv -f UTF-16LE -t UTF-8 temp_tail.log > "$OUTPUT_FILE"; then
        echo "Conversion successful." >> debug_iconv.txt
    else
        echo "Iconv failed. Trying direct copy..." >> debug_iconv.txt
        cat temp_tail.log > "$OUTPUT_FILE"
    fi
    
    rm temp_tail.log
else
    echo "Log file not found at: $LOG_FILE" > debug_iconv.txt
fi
