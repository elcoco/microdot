import sys
from pathlib import Path
import inspect
import time
import logging
import tempfile
import hashlib
import base64
import tarfile
import re

import git
from git import Repo

logger = logging.getLogger("microdot")


CATEGORY_JUST = 5
ACTION_JUST = 5

# characters to use instead of the filsystem unsafe +/
BASE_64_ALT_CHARS = "@-"

class Lock():
    """ Does lock things """
    def __init__(self, path):
        self._holder = None
        self._debugging = False
        self._path = Path(path)

    def __enter__(self):
        try:
            class_name = inspect.stack()[1][0].f_locals['self'].__class__.__name__
        except KeyError:
            class_name = "None"
        method_name = inspect.stack()[1][3]
        caller = f"{class_name}.{method_name}"
        self.wait_for_lock(caller)

    def __exit__(self, type, value, traceback):
        self.release_lock()

    def is_locked(self):
        return self._path.exists()

    def do_lock(self):
        self._path.write_text(self._holder)

    def release_lock(self):
        if not self._path.exists():
            logger.error("Lock file is missing")
            return
        self._path.unlink()

    def set_debugging(self, state):
        self._debugging = state

    def wait_for_lock(self, caller, debug=False):
        while self.is_locked():
            if debug or self._debugging:
                logger.debug(f"[{caller}] is waiting for lock that is held by {self._holder}...")
            time.sleep(0.1)

        self._holder = caller
        self.do_lock()


def colorize(string: str, color: str) -> str:
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

def confirm(msg, assume_yes: bool=False, canceled_msg=None):
    """ Let user confirm, display canceled_msg on deny """
    if assume_yes:
        return True
    if input(msg + ' [y/N] ').lower() == 'y':
        return True
    if canceled_msg != None:
        info("confirm", "canceled", canceled_msg)

def info(category: str, action: str, msg: str):
    """ Display pretty messages """
    category = colorize(category, 'green')
    action = colorize(action, 'magenta')
    msg = colorize(msg, 'default')
    logger.info(f"{category} {action} {msg}")

def debug(category: str, action: str, msg: str):
    """ Display pretty messages """
    category = colorize(category, 'green')
    action = colorize(action, 'magenta')
    msg = colorize(msg, 'default')
    logger.debug(f"{category} {action} {msg}")

def die(msg, code=1):
    logger.error(msg)
    sys.exit(code)

def get_tar(src):
    """ Compress path into tar archive and save in tmp file """
    tmp_file = Path(tempfile.mktemp())

    with tarfile.open(tmp_file, 'w') as f:
        f.add(src, arcname=src.name)
    return tmp_file

def get_rec_hash(path, md5):
    """ Do some recursive path seeking """
    md5.update(path.name.encode())
    if path.is_dir():
        for i in sorted(path.iterdir(), key=lambda x: x.name):
            get_rec_hash(i, md5)
    else:
        md5.update(path.read_bytes())

def get_hash(path, n=8):
    """ Get hash of file name and contents """
    md5 = hashlib.md5()
    md5.update(path.name.encode())
    get_rec_hash(path, md5)
    return base64.b64encode(md5.digest(), altchars=BASE_64_ALT_CHARS.encode()).decode()[:n]

def get_git_remote(path: Path) -> str:
    try:
        return Repo(path).remotes.origin.url
    except git.exc.InvalidGitRepositoryError:
        return None
