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
from dataclasses import dataclass, field

logger = logging.getLogger("microdot")


CATEGORY_JUST = 5
ACTION_JUST = 5

# characters to use instead of the filsystem unsafe +/
BASE_64_ALT_CHARS = "@-"

TREE_JOINT = '├── '
TREE_END   = '└── '
TREE_PPREFIX = '│   '
TREE_EPREFIX = '    '

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


@dataclass
class TreeNode():
    """ Draws a nice tree """
    _name: str
    _parent: 'TreeNode' = None
    _next: 'TreeNode'   = None
    _children: list = field(default_factory=list)

    def add_child(self, name: str) -> 'TreeNode':
        """ Create new node object and add to tree. """
        node = TreeNode(name, _parent=self)

        # connect sibling
        if self._children:
            self._children[-1]._next = node

        self._children.append(node)
        return node

    def add_child_node(self, node) -> 'TreeNode':
        """ Add node object to tree. """
        # connect sibling
        node._parent = self
        if self._children:
            self._children[-1]._next = node

        self._children.append(node)
        return node

    def get_child(self, name: str) -> 'TreeNode':
        """ Get or add child """
        for child in self._children:
            if child._name == name:
                return child
        return self.add_child(name)

    def follow(self, node, string: str='') -> str:
        """ Recursive follow tree back to root and find tree chars """
        if not node:
            return string

        # return if node is root node
        if node.is_root():
            return string

        if node.is_last():
            string += TREE_EPREFIX[::-1]
        else:
            string += TREE_PPREFIX[::-1]

        string = self.follow(node._parent, string)
        return string

    def is_root(self) -> bool:
        return self._parent is None

    def is_last(self) -> bool:
        # if this is last node or all next nodes have empty name field
        return self._next is None or not self.has_valid_children(self._next)

    def is_empty(self) -> bool:
        return not self._name

    def has_valid_children(self, node):
        """ Return True if any node next to $node is valid """
        while True:
            if not node.is_empty():
                return True
            if not node._next:
                break
            node = node._next

    def display(self, tree_color='magenta') -> None:
        prefix = self.follow(self._parent)[::-1]

        if not self.is_root():
            if self.is_empty():
                if self.is_last():
                    prefix += TREE_EPREFIX
                else:
                    prefix += TREE_PPREFIX
            else:
                if self.is_last():
                    prefix += TREE_END
                else:
                    prefix += TREE_JOINT

        prefix = colorize(prefix, tree_color)

        print(f"{prefix}{self._name}")

        for node in self._children:
            node.display(tree_color=tree_color)


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
