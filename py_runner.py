import subprocess
import os

print("Runner starting...")
try:
    # Run the optimizer
    result = subprocess.run(
        ["python3", "bot/ai_agents/evolutionary_optimizer.py"],
        capture_output=True,
        text=True,
        cwd=os.getcwd()
    )
    
    # Write output to file
    with open("py_runner_output.txt", "w") as f:
        f.write("--- STDOUT ---\n")
        f.write(result.stdout)
        f.write("\n--- STDERR ---\n")
        f.write(result.stderr)
        f.write(f"\n--- RETURN CODE: {result.returncode} ---\n")
        
    print("Runner finished. Output saved to py_runner_output.txt")
    
except Exception as e:
    with open("py_runner_error.txt", "w") as f:
        f.write(f"Runner Exception: {e}")
    print(f"Runner failed: {e}")
