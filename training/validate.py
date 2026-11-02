"""validate.py -- kept for backwards compatibility. Use evaluate.py (writes evaluation.json for export.py)."""
import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    print("validate.py is now evaluate.py (it also writes evaluation.json).\n")
    sys.argv[0] = str(Path(__file__).with_name("evaluate.py"))
    runpy.run_path(sys.argv[0], run_name="__main__")
