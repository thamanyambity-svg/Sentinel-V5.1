import json, time, os
path = os.path.expanduser("~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/users/user/AppData/Roaming/MetaQuotes/Terminal/Common/Files/ml_signal.json")
while True:
    try:
        with open(path) as f:
            data = json.load(f)
        changed = False
        for s in data.get("signals", []):
            if s.get("threshold", 0) > 0.58:
                s["threshold"] = 0.58
                if s.get("proba", 0) >= 0.58:
                    s["signal"] = 1
                changed = True
        if changed:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
    except: pass
    time.sleep(10)
