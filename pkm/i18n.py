# SPDX-License-Identifier: AGPL-3.0-or-later
import gettext
from pathlib import Path

DOMAIN = 'parch-kernel-manager'

# Local locales directory
LOCALES_DIR = Path(__file__).parent.parent / 'locales'
if not LOCALES_DIR.exists():
    LOCALES_DIR = Path('/usr/share/locale')

try:
    t = gettext.translation(DOMAIN, localedir=str(LOCALES_DIR), fallback=True)
    _ = t.gettext
except Exception:
    def _(s):
        return s
