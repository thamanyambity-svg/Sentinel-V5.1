#!/bin/bash
# Extract path from .env
PATH_LINE=$(grep "MT5_FILES_PATH" bot/.env)
clean_path=$(echo $PATH_LINE | cut -d'=' -f2 | tr -d '"')

echo "DEBUG: Raw Line: $PATH_LINE" > debug_output.txt
echo "DEBUG: Clean Path: $clean_path" >> debug_output.txt

if [ -d "$clean_path" ]; then
    echo "✅ Path Exists" >> debug_output.txt
    
    echo "--- Command Folder Content ---" >> debug_output.txt
    ls -l "$clean_path/Command" >> debug_output.txt
    
    echo "--- Search for Sentinel.mq5 in Parent/Experts ---" >> debug_output.txt
    parent=$(dirname "$clean_path")
    experts="$parent/Experts"
    find "$experts" -name "Sentinel.mq5" >> debug_output.txt
else
    echo "❌ Path DOES NOT EXIST" >> debug_output.txt
fi
