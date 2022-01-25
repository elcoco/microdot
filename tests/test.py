#!/usr/bin/env python3
from dataclasses import dataclass
from pathlib import Path
import subprocess
import logging
import sys
import tempfile
import shutil
from typing import Optional

logger = logging.getLogger("microdot")


def die(msg, code=1):
    logger.error(msg)
    sys.exit(code)

def cleanup(items):
    """ Cleanup list of files/dirs """
    for item in items:
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=False, onerror=None)
        elif item.is_file() or item.is_symlink():
            item.unlink()
        else:
            continue
        print("removed", item)



@dataclass
class Test():
    cmd: list[str]

    # check these paths after command run
    exist_paths: list[Path] = Optional[None]
    non_exist_paths: list[Path] = Optional[None]

    def __post_init__(self):
        # find md executable
        self.md = Path(__file__).parent.parent / 'md'
        if not self.md.exists():
            die(f"Failed to find microdot executable: {self.md}")

    def check(self):
        pass

    def run(self):
        try:
            self.cmd.insert(0, self.md)
            # check=True raises CalledProcessError on non zero exit code
            result = subprocess.run(self.cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(e)

encr_dir = Path.home() / '.config/encr_dir'
encr_file = Path.home() / '.config/encr_file.txt'
normal_dir = Path.home() / '.config/normal_dir'
normal_file = Path.home() / '.config/normal_file.txt'

dotfiles_dir  = Path(tempfile.mkdtemp(prefix=f'dotfiles_'))

session = [ normal_dir,
            normal_file,
            encr_dir,
            encr_file ]

cleanup(session)

normal_dir.mkdir()
encr_dir.mkdir()
normal_file.write_text("blabla")
encr_file.write_text("blabla")

cmd = ["-d", dotfiles_dir, "-D"]


t1 = Test(cmd+['-i', normal_file])
t1.run()

lst = Test(cmd)
lst.run()

session.append(dotfiles_dir)
cleanup(session)
