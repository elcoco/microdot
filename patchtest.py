#!/usr/bin/env python3

import logging
from pathlib import Path
import sys

from core.patch import Diff
from core.utils import debug, info, confirm
from core.exceptions import MicrodotError

logger = logging.getLogger("microdot")
logger.setLevel(logging.DEBUG)

file1 = Path('/home/eco/tmp/misc/file1.txt')
file2 = Path('/home/eco/tmp/misc/file2.txt')

try:
    d = Diff(file1, file2)
    patch = d.create()
except MicrodotError as e:
    logger.error(e)
    sys.exit()

if not patch:
    sys.exit()


while True:
    patch.edit()
    patch.list()

    if confirm(f"Apply patch to {patch.orig}?"):
        try:
            patch.apply()
            break
        except MicrodotError as e:
            logger.error(e)
            if not confirm("Failed to apply patch, would you like to edit the patch again?"):
                break


for l in patch.orig.read_text().split('\n'):
    print(l)

