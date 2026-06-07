"""Frozen-app entry point (PyInstaller).

Uses an absolute import because, unlike ``python -m pdfreader``, the frozen
bootloader runs this as a top-level script with no parent package.
"""

import sys

from pdfreader.app import main

if __name__ == "__main__":
    sys.exit(main())
