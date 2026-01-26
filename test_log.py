print("HELLO FROM PYTHON")
import sys
print("HELLO FROM STDERR", file=sys.stderr)
with open("test_log_file.txt", "w") as f:
    f.write("FILE WRITE SUCCESS")
