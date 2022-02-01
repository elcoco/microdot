
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



def list_flat(self):
    """ Pretty print all dotfiles """
    print(colorize(f"\nchannel: {self.name}", self._colors.channel_name))

    encrypted =  [d for d in self.dotfiles if d.is_dir() and d.is_encrypted]
    encrypted += [f for f in self.dotfiles if f.is_file() and f.is_encrypted]
    items =  [d for d in self.dotfiles if d.is_dir() and not d.is_encrypted]
    items += [f for f in self.dotfiles if f.is_file() and not f.is_encrypted]

    if len(items) == 0 and len(encrypted) == 0:
        print(colorize(f"No dotfiles yet!", 'red'))
        return

    cols = Columnize(tree=True, prefix_color='magenta')

    for item in items:
        color = self._colors.linked if item.check_symlink() else self._colors.unlinked

        if item.is_dir():
            cols.add([colorize(f"[D]", color), item.name])
        else:
            cols.add([colorize(f"[F]", color), item.name])

    for item in encrypted:
        color = self._colors.linked if item.check_symlink() else self._colors.unlinked
        if item.is_dir():
            cols.add([colorize(f"[ED]", color),
                      item.name,
                      colorize(item.hash, 'green'),
                      colorize(f"{item.timestamp}", 'magenta')])
        else:
            cols.add([colorize(f"[EF]", color),
                      item.name,
                      colorize(item.hash, 'green'),
                      colorize(f"{item.timestamp}", 'magenta')])

    cols.show()

    cols = Columnize(prefix='  ', prefix_color='red')
    for item in encrypted:
        for conflict in item.get_conflicts():

            # color format conflict string
            name = conflict.name.parent / conflict.parse()

            if item.is_dir():
                cols.add([colorize(f"[CD]", self._colors.conflict), name])
            else:
                cols.add([colorize(f"[CF]", self._colors.conflict), name])
    cols.show()
