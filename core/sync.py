from pathlib import Path
import logging

logger = logging.getLogger("microdot")

class StatusList():
    def __init__(self):
        self._path = Path.home() / '.config/microdot/status.list'
        self._list = []

    def read_list(self):
        try:
            self._list = self._path.read_text().split('\n')
        except FileNotFoundError:
            logger.info(f"No status list found at: {self._path}")
            self._list = []

    def in_list(self, dotfile):
        return dotfile.encrypted_path in self._list

    def exists(self, item):
        return item != None

    def write(self):
        self._path.write_text('\n'.join(self._list))

    def solve(self, a=None, b=None):
        """ Tries to solve a conflict.
            returns the dotfile that stays """

        try:
            a_name = a.encrypted_path.name
            b_name = b.encrypted_path.name
        except AttributeError:
            pass

        if not self.exists(a) and not self.exists(b):
            logger.error(f"SYNC: unreachable: both don't exist -> {a_name} and {b_name}")

        elif not self.in_list(a) and not self.exists(b):
            logger.debug(f"SYNC: A is new: {a_name}")
            self._list.append(a.encrypted_path)

        elif self.in_list(a) and not self.exists(b):
            logger.debug("SYNC: We are in sync")

        elif self.in_list(a) and not self.in_list(b):
            logger.debug(f"SYNC: B is newer: {a_name} > {b_name}")
            self._list.remove(a.encrypted_path)
            self._list.append(b.encrypted_path)
            a.remove_file()

        elif not self.in_list(a) and self.in_list(b):
            logger.debug(f"SYNC: A is newer: {a_name} < {b_name}")
            self._list.append(a.encrypted_path)
            self._list.remove(b.encrypted_path)
            b.remove_file()

        elif not self.in_list(a) and not self.in_list(b):
            # A and B are new
            logger.error(ff"SYNC: conflict: {a_name} <> {b_name}")

        elif self.in_list(a) and self.in_list(b):
            logger.error(ff"SYNC: unreachable: both in list -> {a_name} and {b_name}")

        else:
            logger.error(ff"SYNC: unreachable: {a_name}, {b_name}")


        self.write()
