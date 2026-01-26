#!/bin/bash
LOG="diag_log.txt"
echo "--- DIAGNOSTIC START ---" > $LOG

echo "Checking python3:" >> $LOG
which python3 >> $LOG 2>&1
python3 --version >> $LOG 2>&1
echo "Running python3 simple_test.py:" >> $LOG
python3 simple_test.py >> $LOG 2>&1

echo "Checking /usr/local/bin/python3.14:" >> $LOG
ls -l /usr/local/bin/python3.14 >> $LOG 2>&1
/usr/local/bin/python3.14 --version >> $LOG 2>&1
echo "Running /usr/local/bin/python3.14 simple_test.py:" >> $LOG
/usr/local/bin/python3.14 simple_test.py >> $LOG 2>&1

echo "Checking venv:" >> $LOG
ls -l venv/bin/python3 >> $LOG 2>&1
venv/bin/python3 --version >> $LOG 2>&1
echo "Running venv simple_test.py:" >> $LOG
venv/bin/python3 simple_test.py >> $LOG 2>&1

echo "--- DIAGNOSTIC END ---" >> $LOG
