"""Clean workspace helper.

Usage:
    python scripts/clean.py

This script will remove all `__pycache__` directories under the project.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def remove_pycache(root: Path):
    removed = []
    for p in root.rglob('__pycache__'):
        try:
            shutil.rmtree(p)
            removed.append(str(p))
        except Exception as e:
            print(f"Failed to remove {p}: {e}")
    return removed

if __name__ == '__main__':
    print(f"Cleaning __pycache__ under {ROOT}")
    removed = remove_pycache(ROOT)
    if removed:
        print("Removed:")
        for r in removed:
            print(" -", r)
    else:
        print("No __pycache__ directories found.")
