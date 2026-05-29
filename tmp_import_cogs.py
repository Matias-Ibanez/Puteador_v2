import importlib
import traceback

modules = ["src.cogs.insult_cog", "src.cogs.voice_cog"]

for m in modules:
    try:
        mod = importlib.import_module(m)
        print(f"Imported {m} -> attributes: {', '.join(sorted([n for n in dir(mod) if not n.startswith('_')]) )}")
    except Exception as e:
        print(f"Failed to import {m}: {e}")
        traceback.print_exc()
