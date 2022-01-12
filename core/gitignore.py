#!/usr/bin/env python3

import logging
from pathlib import Path

logger = logging.getLogger("microdot")


class Gitignore():
    def __init__(self):
        self._lines = []
        self._path = None

    def set_dotfiles_dir(self, path):
        """ Set path of .gitignore file """
        self._path = path / '.gitignore'

    def add(self, line):
        print(f"Adding {line} to .gitignore")
        self._lines.append(str(line))

    def list(self):
        print("listing:")
        for i,line in enumerate(self._lines):
            print(f"{i}: {line}")

    def write(self):
        self._path.write_text('\n'.join(self._lines))
        logger.info(f"Wrote .gitignore to {self._path}")
