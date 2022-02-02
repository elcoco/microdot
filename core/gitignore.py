#!/usr/bin/env python3

import logging
from pathlib import Path
from core.utils import debug

logger = logging.getLogger("microdot")


class Gitignore():
    def __init__(self, dotfiles_dir):
        self._lines = [ '*.py[cod]', '*.__pycache__/', '.gitignore', 'decrypted' ]
        self._path = dotfiles_dir / '.gitignore'

    def list(self):
        for i,line in enumerate(self._lines):
            debug('gitignore', 'list', f"{i}: {line}")

    def read(self):
        for l in self._path.read_text().split():
            if l not in self._lines:
                self._lines.append(l)

    def write(self):
        if self._path.exists():
            self.read()
        self._path.write_text('\n'.join(self._lines))
        self.list()
        debug('gitignore', 'written', self._path)
