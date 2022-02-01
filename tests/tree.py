#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.append('../microdot')

from core.utils import TreeNode, colorize


def search(path: Path, node: TreeNode):
    """ Fill tree """
    if path.is_file():
        node.add_child(path.name)
    elif path.is_symlink():
        node.add_child(colorize(f"{path.name} -> {path.resolve()}", 'bmagenta'))
    elif path.is_fifo() or path.is_block_device() or path.is_char_device():
        node.add_child(f"{path.name}")
    elif path.is_dir():
        d_node = node.add_child(colorize(f"{path.name}/", 'bblue'))
        for p in path.iterdir():
            search(p, d_node)
    else:
        print("Unknown type:", path)


if len(sys.argv) < 2:
    print("Specify path")
    sys.exit()

path = Path(sys.argv[1])
root = TreeNode(f"[ROOT] {path.name}")

try:
    search(path, root)
except PermissionError as e:
    print(e)
    sys.exit(1)

root.display()
