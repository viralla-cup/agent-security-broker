"""Host CLI entry point; standard library only, with no Docker or executor access."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from security_audit.__main__ import main

if __name__ == '__main__':
    raise SystemExit(main())
