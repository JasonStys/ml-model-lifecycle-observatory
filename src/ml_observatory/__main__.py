"""File: __main__.py
Purpose: Support ``python -m ml_observatory`` through the package command-line interface.
Symbols and line locations: see docs/code-index.md; main is imported from the CLI module.
"""

from ml_observatory.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
