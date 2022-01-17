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
        return str(dotfile.encrypted_path.name) in self._list

    def exists(self, item):
        return item != None

    def write(self):
        self._path.write_text('\n'.join(self._list))

    def add(self, dotfile):
        logger.debug(f"STATUS: adding: {dotfile.encrypted_path.name}")
        self._list.append(str(dotfile.encrypted_path.name))

    def remove(self, dotfile):
        logger.debug(f"STATUS: removing: {dotfile.encrypted_path.name}")
        self._list.remove(str(dotfile.encrypted_path.name))

    def solve(self, a=None, b=None):
        """ Tries to solve a conflict.
            returns the dotfile that stays """
        self.read_list()

        try:
            a_name = a.encrypted_path.name
            b_name = b.encrypted_path.name
        except AttributeError:
            pass

        if not self.exists(a) and not self.exists(b):
            logger.error(f"SYNC: unreachable: both don't exist -> {a_name} and {b_name}")

        elif not self.in_list(a) and not self.exists(b):
            logger.debug(f"SYNC: A is new: {a_name}")
            self.add(a)

        elif self.in_list(a) and not self.exists(b):
            logger.debug("SYNC: We are in sync")

        elif self.in_list(a) and not self.in_list(b):
            logger.debug(f"SYNC: B is newer: {a_name} > {b_name}")
            self.remove(a)
            self.add(b)
            a.encrypted_path.unlink()

        elif not self.in_list(a) and self.in_list(b):
            logger.debug(f"SYNC: A is newer: {a_name} < {b_name}")
            self.add(a)
            self.remove(b)
            b.encrypted_path.unlink()

        elif not self.in_list(a) and not self.in_list(b):
            # A and B are new
            logger.error(f"SYNC: conflict: {a_name} <> {b_name}")

        elif self.in_list(a) and self.in_list(b):
            logger.error(f"SYNC: unreachable: both in list -> {a_name} and {b_name}")

        else:
            logger.error(f"SYNC: unreachable: {a_name}, {b_name}")


        self.write()
