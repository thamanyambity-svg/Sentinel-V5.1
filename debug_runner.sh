#!/bin/bash
echo "--- WRAPPER START ---" > debug_out.txt
echo "Trying python3:" >> debug_out.txt
python3 -c "import sys; print(sys.executable); print(sys.path)" >> debug_out.txt 2>&1

echo "Trying /usr/local/bin/python3.14:" >> debug_out.txt
/usr/local/bin/python3.14 -c "import sys; print(sys.executable); print(sys.path)" >> debug_out.txt 2>&1

echo "Running debug_start.py with /usr/local/bin/python3.14:" >> debug_out.txt
/usr/local/bin/python3.14 debug_start.py >> debug_out.txt 2>&1

echo "--- WRAPPER END ---" >> debug_out.txt
