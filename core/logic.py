from pathlib import Path
import logging
from core.utils import info, debug
from core import state

logger = logging.getLogger("microdot")


class LastSyncIndex():
    """ Keep a list of encrypted filenames that represent the last known state """

    def __init__(self):
        self._path = Path.home() / '.config/microdot/sync_index.db'
        self._list = []

    def read_list(self):
        try:
            self._list = self._path.read_text().split('\n')
        except FileNotFoundError:
            logger.info(f"No status list found at: {self._path}")
            self._list = []

    def in_list(self, path):
        self.read_list()
        return str(path.absolute()) in self._list

    def exists(self, path):
        return path != None

    def write(self):
        self._path.write_text('\n'.join(self._list))

    def add(self, path):
        # TODO better matching
        self.read_list()
        name = path.name.split('#')[0]
        for item in self._list:
            if f"{name}#" in item:
                self._list.remove(item)

        #logger.debug(f"STATUS: list_add: {path}")
        self._list.append(str(path.absolute()))
        self.write()

    def remove(self, path):
        self.read_list()
        #logger.debug(f"STATUS: list_rm: {path}")
        self._list.remove(str(path.absolute()))
        self.write()


class SyncAlgorithm(LastSyncIndex):
    """ Sync() makes logic decisions about the fate of file A and B """
    # TODO use paths, not dotfile objects to make it a bit more modular
    def __init__(self):
        super().__init__()

    def check_removed(self, dotfiles):
        """ Check if items from list don't have corresponding data on system.
            If so, this indicates a deletion """

        for path in [x.strip() for x in self._list]:
            if not path:
                continue

            encrypted_path = Path(path)
            name = encrypted_path.name.split('#')[0]
            decrypted_path = Path(path).parent / name
            decrypted_path = (state.core.dotfiles_dir / 'decrypted' / Path(path).relative_to(state.core.dotfiles_dir)).parent / name

            # see if status list entry has a corresponding file on disk
            for dotfile in dotfiles:
                if decrypted_path == dotfile.path:
                    break
            else:
                if decrypted_path.exists():
                    decrypted_path.unlink()
                    info("sync," "removed", decrypted_path)

                debug("sync", "removed", encrypted_path)
                self.remove(encrypted_path)

    def a_is_new(self, a, b):
        if not self.in_list(a) and not self.exists(b):
            info("sync", "new", f"A is new: {a.name}")
            self.add(a)
            return True

    def b_is_new(self, a, b):
        if not self.exists(a) and not self.in_list(b):
            info("sync", "new", f"B is new: {a.name}")
            self.add(b)
            return True

    def is_in_sync(self, a, b):
        if self.in_list(a) and not self.exists(b):
            info("sync", "in_sync", 'in sync')
            return True

#    def b_is_newer(self, a, b):
#        if self.in_list(a) and not self.in_list(b):
#            info('sync', 'newer', f'B is newer: {a.name} < {b.name}')
#            self.remove(a)
#            self.add(b)
#            return True
#
#    def a_is_newer(self, a, b):
#        if not self.in_list(a) and self.in_list(b):
#            info('sync', 'newer', f'A is newer: {a.name} > {b.name}')
#            self.add(a)
#            self.remove(b)
#            return True

    def is_in_conflict(self, a, b):
        """ Solve a conflict by choosing the local data and renaming the other file """
        if self.exists(a) and self.exists(b) and not self.in_list(a) and not self.in_list(b):
            #info('sync', 'conflict', 'in conflict')
            return True
