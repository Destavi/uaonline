import services.stats_manager
import inspect

sig = inspect.signature(services.stats_manager.update_stat)
print(f"Signature of update_stat: {sig}")
print(f"Number of parameters: {len(sig.parameters)}")
for name, param in sig.parameters.items():
    print(f"  - {name}: {param.kind} (default: {param.default})")
