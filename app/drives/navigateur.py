"""Démarrage du collecteur Edge sur le poste Windows du comparateur."""

import logging
import os
import subprocess
import sys
from pathlib import Path
from threading import Lock
from time import monotonic

logger = logging.getLogger(__name__)
_verrou = Lock()
_prochain_demarrage = 0.0


def reveiller_edge() -> None:
    """Une ouverture au plus toutes les 75 secondes."""
    if sys.platform != "win32":
        return
    global _prochain_demarrage
    with _verrou:
        instant = monotonic()
        if instant < _prochain_demarrage:
            return
        _prochain_demarrage = instant + 75
        for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            racine = os.environ.get(variable)
            if not racine:
                continue
            executable = Path(racine) / "Microsoft/Edge/Application/msedge.exe"
            if executable.is_file():
                try:
                    subprocess.Popen(
                        [str(executable)],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except OSError:
                    logger.warning("Impossible de démarrer Edge.", exc_info=True)
                return
