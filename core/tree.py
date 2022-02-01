from dataclasses import dataclass, field

from core.utils import colorize

TREE_JOINT = '├── '
TREE_END   = '└── '
TREE_PPREFIX = '│   '
TREE_EPREFIX = '    '


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
