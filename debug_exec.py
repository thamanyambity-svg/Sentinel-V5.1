import os
try:
    with open("debug_proof.txt", "w") as f:
        f.write("Python is working. Cwd: " + os.getcwd())
except Exception as e:
    print(e)
