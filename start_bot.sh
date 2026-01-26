#!/bin/bash
# Script pour lancer le bot Alpha Sentinel
cd "$(dirname "$0")"
source venv/bin/activate
export PYTHONPATH=$PYTHONPATH:.
python3 bot/main.py
