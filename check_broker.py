import inspect
from bot.broker.deriv.broker import DerivBroker

print("Methods of DerivBroker:")
for name, method in inspect.getmembers(DerivBroker):
    if not name.startswith("__"):
        print(name)

if hasattr(DerivBroker, 'execute_trade'):
    print("\n✅ execute_trade EXISTS")
else:
    print("\n❌ execute_trade DOES NOT EXIST")
