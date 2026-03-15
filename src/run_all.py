"""
Run all src code: figure generation + algorithm smoke test.
Called by run_src.ps1 / run_src.bat. Can also run directly:
  python -m src.run_all   (from repo root)
  or  python src/run_all.py
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
os.chdir(REPO_ROOT)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def main():
    print("Running figure generation (paper/fig) ...")
    # Run figure script with default out-dir (paper/fig)
    import figures.run_all_figures as run_figures_mod
    run_figures_mod.main()

    print("Running algorithm smoke test ...")
    from algorithms.differential_privacy import laplace_mechanism
    from algorithms.gdifsea import gdifsea
    x = laplace_mechanism(1.0, 0.5, 0.1)
    assert abs(x - 1.0) < 10, "laplace_mechanism sanity check"
    r = gdifsea(["coronavirus vaccine", "coronavirus infection"], support_threshold=1)
    print("  algorithms OK")

    print("All done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
