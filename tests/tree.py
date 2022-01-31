#!/usr/bin/env python3

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


CON_CHR = '│'
MID_CHR = '├─'
ENC_CHR = '└─'

# set level in Item

@dataclass
class Item():
    name: str
    level: int = 0
    parent: str = Optional[None]
    children: list = field(default_factory=list)

    def add_child(self, item):
        item.parent = self
        self.children.append(item)

    def has_children(self):
        return len(children)

    def display(self, level=0):
        #string = f"{CON_CHR} " * level + MID_CHR

        string = "  " * level
        print(string + self.name)

        for item in self.children:
            item.display(level+1)


def search(path: Path, item: Item):
    if path.is_file():
        f_item = Item(f"[F] {path.name}")
        item.add_child(f_item)
    else:
        d_item = Item(f"[D] {path.name}")
        item.add_child(d_item)

        for p in path.iterdir():
            search(p, d_item)


if len(sys.argv) < 2:
    print("Specify path")
    sys.exit()

path = Path(sys.argv[1])
root = Item(f"[ROOT] {path.name}")
search(path, root)
root.display()

