import sys
import os
sys.path.append(os.getcwd())

from services.stats_manager import update_stat
import inspect

print(f"File: {inspect.getfile(update_stat)}")
print(f"Signature: {inspect.signature(update_stat)}")

try:
    update_stat(1, 2, 3)
    print("Success with 3 arguments")
except TypeError as e:
    print(f"Error with 3 arguments: {e}")

try:
    update_stat(1, 2)
    print("Success with 2 arguments")
except TypeError as e:
    print(f"Error with 2 arguments: {e}")
