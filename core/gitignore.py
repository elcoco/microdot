#!/usr/bin/env python3

import logging
from pathlib import Path

logger = logging.getLogger("microdot")


class Gitignore():
    def __init__(self, dotfiles_dir):
        self._lines = []
        self._path = dotfiles_dir / '.gitignore'

    def add(self, line):
        logger.debug(f"Adding {line} to .gitignore")
        self._lines.append(str(line))

    def list(self):
        logger.info("listing:")
        for i,line in enumerate(self._lines):
            logger.info(f"{i}: {line}")

    def write(self):
        self._path.write_text('\n'.join(self._lines))
        logger.info(f"Wrote .gitignore to {self._path}")
