#!/bin/bash
echo "Starting installation..." > install_log.txt
which python3 >> install_log.txt 2>&1
python3 --version >> install_log.txt 2>&1
which pip3 >> install_log.txt 2>&1

echo "Installing pandas..." >> install_log.txt
pip3 install pandas numpy discord.py python-dotenv fastapi uvicorn requests >> install_log.txt 2>&1

echo "Verifying pandas..." >> install_log.txt
python3 -c "import pandas; print(f'Pandas version: {pandas.__version__}')" >> install_log.txt 2>&1
echo "Done." >> install_log.txt
