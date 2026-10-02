# -*- coding: utf-8 -*-
"""Le point d'entrée de l'exécutable : il lance le paquet, et rien d'autre."""
import sys

from pdforensics.__main__ import principal

if __name__ == "__main__":
    sys.exit(principal())
