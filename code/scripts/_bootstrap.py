"""Make the `its` package importable when a script is run directly.

Every script does `import _bootstrap` first, so it works the same from
a terminal, VS Code or PyCharm, without installing anything.
"""

import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[1]
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
