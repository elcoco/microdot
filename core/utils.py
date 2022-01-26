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


class Columnize():
    """ Returns justified 2d list of strings """
    def __init__(self, enum=False, tree=False, prefix='', header_color="default", prefix_color="default"):
        self._lines = []
        self._max_cols = []
        self._header = []
        self._enum = enum
        self._tree = tree
        self._prefix = prefix

        # colors for header and numbering/tree
        self._header_color = header_color
        self._prefix_color = prefix_color

    def colorize(self, string, color):
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
        return colors[color] + string + colors["reset"]

    def get_unprintable(self, string):
        """ Return amount of unprintable chars in string """
        ansi_escape = re.compile(r'(?:\x1B[@-Z\\-_]|[\x80-\x9A\x9C-\x9F]|(?:\x1B\[|\x9B)[0-?]*[ -/]*[@-~])')
        return len(string) - len(ansi_escape.sub('', string))

    def add(self, l):
        self._lines.append([str(x) for x in l])

    def set_header(self, header, color="default"):
        if color != None:
            self._header = [self.colorize(x, color) for x in header]
        else:
            self._header = header

    def justify_line(self, l, lines):
        ncols = self.get_n_cols(lines)
        out = []

        for ncol,s in enumerate(l):
            # calculate string length, considering unprintable chars like ansi color codes
            col_max = self.get_col_max(ncol, lines)
            s_len = (col_max - (len(s) - self.get_unprintable(s))) + len(s)
            out.append(s.ljust(s_len))
        return out

    def get_col_max(self, col, lines):
        """ Find len of biggest item - unprintable chars in column """
        col_max = 0
        for l in lines:
            try:
                col_clean = len(l[col]) - self.get_unprintable(l[col])
            except IndexError:
                continue

            if col_clean > col_max:
                col_max = col_clean
        return col_max

    def get_n_cols(self, lines):
        return max([ len(l) for l in lines ])

    def get_lines(self):
        out = []

        # header also needs to be justified
        all_lines = self._lines[:]
        all_lines.append(self._header)

        for l in self._lines:
            out.append(self.justify_line(l, all_lines))

        if self._header:
            out.insert(0, self.justify_line(self._header, all_lines))

        if self._enum:
            for i,l in enumerate(out, 0 if self._header else 1 ):
                if self._header and i == 0:
                    l.insert(0, len(str(len(out)))*' ')
                else:
                    l.insert(0, self.colorize(str(i), self._prefix_color))

        if self._prefix:
            for i,l in enumerate(out):
                if self._header and i == 0:
                    l.insert(0, len(str(self._prefix))*' ')
                else:
                    l.insert(0, self.colorize(str(self._prefix), self._prefix_color))

        if self._tree:
            for i,l in enumerate(out):
                if self._header and i == 0:
                    l.insert(0, self.colorize(f'  ', self._prefix_color))
                elif i == len(out)-1:
                    l.insert(0, self.colorize(f"└─", self._prefix_color))
                else:
                    l.insert(0, self.colorize(f"├─", self._prefix_color))
        return out

    def show(self):
        for l in self.get_lines():
            print(" ".join(l))


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

def confirm(msg, assume_yes=False, canceled_msg=None):
    """ Let user confirm, display canceled_msg on deny """
    if assume_yes:
        return True
    if input(msg + ' [y/N] ').lower() == 'y':
        return True
    if canceled_msg != None:
        info("confirm", "canceled", canceled_msg)

def info(category: str, action: str, msg: str):
    """ Display pretty messages """
    category = str(category).ljust(CATEGORY_JUST)
    category = colorize(category, 'green')

    action = action.ljust(ACTION_JUST)
    action = colorize(action, 'magenta')

    msg = colorize(msg, 'white')
    logger.info(f"{category} {action} {msg}")

def debug(category: str, action: str, msg: str):
    """ Display pretty messages """
    category = str(category).ljust(CATEGORY_JUST)
    category = colorize(category, 'green')
    action = action.ljust(ACTION_JUST)
    action = colorize(action, 'magenta')
    msg = colorize(msg, 'white')
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
    # TODO doesn't work when nested dir
    # TODO make recursive
    md5 = hashlib.md5()
    md5.update(path.name.encode())
    get_rec_hash(path, md5)
    return base64.b64encode(md5.digest(), altchars=BASE_64_ALT_CHARS.encode()).decode()[:n]
