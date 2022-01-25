#!/usr/bin/env python3
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import logging
import sys
import tempfile
import shutil
from typing import Optional, Any

logger = logging.getLogger("microdot")

def colorize(string, color):
    colors = {}
    colors['black']    = '\033[0;30m'
    colors['bblack']   = '\033[1;30m'
    colors['red']      = '\033[0;31m'
    colors['bred']     = '\033[1;31m'
    colors['green']    = '\033[0;32m'
    colors['bgreen']   = '\033[1;32m'
    colors['yellow']   = '\033[0;33m'
    colors['byellow']  = '\033[1;33m'
    colors['blue']     = '\033[0;34m'
    colors['bblue']    = '\033[1;34m'
    colors['magenta']  = '\033[0;35m'
    colors['bmagenta'] = '\033[1;35m'
    colors['cyan']     = '\033[0;36m'
    colors['bcyan']    = '\033[1;36m'
    colors['white']    = '\033[0;37m'
    colors['bwhite']   = '\033[1;37m'
    colors['reset']    = '\033[0m'
    colors['default']    = '\033[0m'
    return colors[color] + str(string) + colors["reset"]

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
    name: str
    cmd: list[str]

    # check these paths after command run
    exist: dict[Path,str] = field(default_factory=dict)
    non_exist: dict[Path,str] = field(default_factory=dict)


    def add_exist(self, path: Path, dtype):
        self.exist[path] = dtype

    def add_non_exist(self, path: Path, dtype):
        self.non_exist[path] = dtype

    def __post_init__(self):
        # find md executable
        self.md = Path(__file__).parent.parent / 'md'
        if not self.md.exists():
            die(f"Failed to find microdot executable: {self.md}")

    def check(self):
        results = {}
        passed = colorize("passed", "bgreen")
        failed = colorize("failed", "bred")
        print(colorize('Results for:', 'bblue'), self.name)
        #print(colorize('Running tests for:', 'bblue'), ' '.join([str(x) for x in self.cmd]))

        for p,t in self.exist.items():

            match t:
                case "file":
                    print(passed if p.is_file() else failed, end='')
                case "link":
                    print(passed if p.is_symlink() else failed, end='')
                case "dir":
                    print(passed if p.is_dir() else failed, end='')
                case _:
                    print("Failed to check", end='')
            print(f" {p} == {t}")
        print()

    def run(self):
        try:
            self.cmd.insert(0, self.md)
            # check=True raises CalledProcessError on non zero exit code
            result = subprocess.run(self.cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(e)

        self.check()

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

channel = 'bever'
decrypted_dir = 'decrypted'

cmd = ["-d", dotfiles_dir, "-D", '-c', channel]


t1 = Test('unencrypted init', cmd+['-i', normal_file])
t1.add_exist(normal_file, 'link')
t1.add_exist(dotfiles_dir/ channel / normal_file.relative_to(Path.home()), 'file')
t1.run()

t2 = Test('encrypted init', cmd+['-e', '-i', encr_file])
t2.add_exist(normal_file, 'link')
t2.add_exist(dotfiles_dir/ decrypted_dir / channel / encr_file.relative_to(Path.home()), 'file')
t2.run()


lst = Test('list', cmd)
lst.run()

session.append(dotfiles_dir)
cleanup(session)
