from pathlib import Path
import logging

logger = logging.getLogger("microdot")


class StatusList():
    """ Keep a list of encrypted filenames that represent the last known state """

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
        self.read_list()
        return str(dotfile.encrypted_path.absolute()) in self._list

    def exists(self, dotfile):
        return dotfile != None

    def write(self):
        self._path.write_text('\n'.join(self._list))

    def add(self, path):
        # TODO better matching
        self.read_list()
        name = path.name.split('#')[0]
        for item in self._list:
            if f"{name}#" in item:
                self._list.remove(item)

        logger.debug(f"STATUS: list_add: {path}")
        self._list.append(str(path.absolute()))
        self.write()

    def remove(self, path):
        self.read_list()
        logger.debug(f"STATUS: list_rm: {path}")
        self._list.remove(str(path.absolute()))
        self.write()


class Sync(StatusList):
    """ Sync() makes logic decisions about the fate of file A and B """
    # TODO use paths, not dotfile objects to make it a bit more modular
    def check_removed(self, dotfiles):
        """ Check if items from list don't have corresponding data on system.
            If so, this indicates a deletion """

        for path in [x.strip() for x in self._list]:
            if not path:
                continue

            encrypted_path = Path(path)
            name = encrypted_path.name.split('#')[0]
            path = Path(path).parent / name

            # see if status list entry has a corresponding file on disk
            for dotfile in dotfiles:
                if path == dotfile.path:
                    break
            else:
                if path.exists():
                    logger.info(f"Removing {path}")
                    path.unlink()

                self.remove(encrypted_path)

    def a_is_new(self, a, b):
        if not self.in_list(a) and not self.exists(b):
            self.add(a.encrypted_path)
            if a.check_symlink():
                a.decrypt()
            return True

    def b_is_new(self, a, b):
        if not self.exists(a) and not self.in_list(b):
            self.add(b.encrypted_path)
            if b.check_symlink():
                b.decrypt()
            return True

    def is_in_sync(self, a, b):
        return self.in_list(a) and not self.exists(b)

    def a_is_newer(self, a, b):
        if self.in_list(a) and not self.in_list(b):
            self.remove(a.encrypted_path)
            self.add(b.encrypted_path)
            a.encrypted_path.unlink()
            if a.check_symlink():
                b.decrypt()
            return True

    def b_is_newer(self, a, b):
        if not self.in_list(a) and self.in_list(b):
            self.add(a.encrypted_path)
            self.remove(b.encrypted_path)
            b.encrypted_path.unlink()
            if a.check_symlink():
                a.decrypt()
            return True

    def is_in_conflict(self, a, b):
        """ Solve a conflict by choosing the local data and renaming the other file """
        if self.exists(a) and self.exists(b) and not self.in_list(a) and not self.in_list(b):
            d_hash = a.get_hash(a.path)

            # TODO attach hostname and date for easy identification
            if d_hash == a.hash:
                logger.info(f"Choosing A: {a.encrypted_path.name}")
                b.encrypted_path.rename(b.encrypted_path.parent / (b.encrypted_path.name + '#CONFLICT'))
            elif d_hash == b.hash:
                logger.info(f"Choosing B: {b.encrypted_path.name}")
                a.encrypted_path.rename(a.encrypted_path.parent / (a.encrypted_path.name + '#CONFLICT'))
            else:
                logger.error("Failed to find a resolution")
            return True
