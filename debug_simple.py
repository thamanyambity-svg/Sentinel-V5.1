import os

target = "/Users/macbookpro/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files"
output_file = "/Users/macbookpro/Downloads/bot_project/debug_result.txt"

with open(output_file, "w") as f:
    f.write(f"Checking: {target}\n")
    if os.path.exists(target):
        f.write("DIR EXISTS!\n")
        try:
            files = os.listdir(target)
            f.write(f"Files found: {len(files)}\n")
            for filename in files:
                f.write(f" - {filename}\n")
        except Exception as e:
            f.write(f"Error listing: {e}\n")
    else:
        f.write("DIR NOT FOUND!\n")

print("Done writing to " + output_file)
