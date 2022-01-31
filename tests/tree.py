#!/usr/bin/env python3

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


JOINT = '├── '
END   = '└── '
PPREFIX = '│   '
EPREFIX = '    '

@dataclass
class Node():
    _name: str
    _parent: 'Node' = None
    _next: 'Node'   = None
    _children: list = field(default_factory=list)

    def add_child(self, name):
        node = Node(name,
                    _parent = self)

        # connect siblings
        if self._children:
            self._children[-1]._next = node

        self._children.append(node)
        return node

    def follow(self, node, string=''):
        """ Follow tree back to root and find tree chars """
        if not node:
            return string

        # return if node is root node
        if not node._parent:
            return string

        if node._next:
            string += PPREFIX[::-1]
        else:
            string += EPREFIX[::-1]

        string = self.follow(node._parent, string)
        return string

    def has_children(self):
        return len(self._children)

    def display_tree(self):
        prefix = self.follow(self._parent)[::-1]

        # if node is not the root node
        if self._parent:
            if self._next:
                prefix += JOINT
            else:
                prefix += END

        print(f"{prefix}{self._name}")

        for node in self._children:
            node.display_tree()


def search(path: Path, node: Node):
    """ Fill tree """
    if path.is_file():
        node.add_child(f"{path.name}")
    elif path.is_symlink():
        node.add_child(f"{path.name}")
    else:
        d_node = node.add_child(f"{path.name}")
        for p in path.iterdir():
            search(p, d_node)


if len(sys.argv) < 2:
    print("Specify path")
    sys.exit()

path = Path(sys.argv[1])
root = Node(f"[ROOT] {path.name}")
search(path, root)
root.display_tree()

