import logging
from pathlib import Path
import shutil
import hashlib
import base64
import tarfile
import tempfile
from itertools import groupby
import datetime
import re

from core.exceptions import MicrodotError
from core import state
from core import CONFLICT_EXT, ENCRYPTED_DIR_EXT, ENCRYPTED_FILE_EXT, ENCRYPTED_DIR_FORMAT, ENCRYPTED_FILE_FORMAT
from core import CONFLICT_FILE_EXT, CONFLICT_DIR_EXT, TIMESTAMP_FORMAT, DECRYPTED_DIR, SCAN_CHANNEL_BLACKLIST, SCAN_DIR_BLACKLIST
from core import SCAN_DIR_FILE
from core.utils import confirm, colorize, debug, info, get_hash, get_tar
from core.utils import Columnize

from cryptography.fernet import Fernet
import cryptography

logger = logging.getLogger("microdot")


class DotFileBaseClass():
    def __init__(self, path, channel):
        """ path is where dotfile source is: /home/eco/.dotfiles/common/testfile.txt """

        self.channel = channel
        self.path = path
        self.name = path.relative_to(channel)
        self.link_path = Path.home() / self.name
        self.is_encrypted = False
        self.cleanup_link()

        if not self.path.parent.is_dir():
            debug(self.name, 'mkdir', self.path.parent)
            self.path.parent.mkdir(parents=True)

    def cleanup_link(self):
        # find orphan links (symlink that points 
        if self.link_path.is_symlink():
            if not self.path.exists():
                self.link_path.unlink()
                info("link_check", "remove", f"orphan link found: {self.link_path}")
            elif not self.link_path.resolve() == self.path:
                info("link_check", "remove", f"link doesn't point to data: {self.link_path}")
                self.link_path.unlink()

    def check_symlink(self):
        # check if link links to src
        if not self.link_path.is_symlink():
            return
        return self.link_path.resolve() == self.path

    def is_dir(self):
        return self.path.is_dir()

    def is_file(self):
        return self.path.is_file()

    def link(self, target=None, force=False):
        if self.check_symlink():
            raise MicrodotError(f"Dotfile is not linked: {self.name}")

        link = self.link_path

        if not target:
            target = self.path

        if link.is_symlink():
            link.unlink()

        if link.exists() and force:
            logger.info(f"Path exists, using --force to overwrite: {link}")
            self.remove_path(link)

        if link.is_symlink():
            raise MicrodotError(f"Dotfile already linked: {link}")

        if link.exists():
            raise MicrodotError(f"Path exists: {link}")

        link.symlink_to(target)
        debug(self.name, 'linked', f'{link} -> {target.name}')
        return True
    
    def unlink(self):
        if not self.check_symlink():
            raise MicrodotError(f"Dotfile is not linked: {self.name}")

        self.link_path.unlink()
        debug(self.name, 'unlinked', self.link_path)
        return True

    def init(self, src):
        """ Move source path to dotfile location """
        shutil.move(src, self.path)
        #src.replace(self.path)
        debug(self.name, 'moved', f'{src} -> {self.path}')
        self.link()

        # create managed dir indicator file
        if self.is_dir():
            (self.path / SCAN_DIR_FILE).touch()

    def remove_path(self, path: Path):
        """ Remove file or directory """
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=False, onerror=None)
        else:
            path.unlink()

    def to_encrypted(self, key):
        """ Encrypt an unencrypted dotfile """
        # TODO raises error because self.path doesn't exist
        if self.is_encrypted:
            raise MicrodotError(f"Dotfile is already encrypted: {self.name}")

        if (was_linked := self.check_symlink()):
            self.unlink()

        path = self.path.relative_to(self.channel) / DECRYPTED_DIR / self.name

        if self.path.is_dir():
            df = DotDirEncrypted(self.path, self.channel, key)
        else:
            df = DotFileEncrypted(self.path, self.channel, key)

        df.encrypt(self.path)
        self.remove_path(self.path)
        if was_linked:
            df.link()
        

class DotFileEncryptedBaseClass(DotFileBaseClass):
    """ Baseclass for all encrypted files/directories """
    def __init__(self, path, channel, key):
        try: # parse ENCRYPTED file: ~/.dotfiles/common/testdir#IzjOuV4h#20220121162145#D#CRYPT
            name, self.hash, ts,  _, _ = path.name.split('#')
            self.path = channel.parent / DECRYPTED_DIR / channel.name / path.relative_to(channel).parent / name
            self.encrypted_path = path
            self.name = self.path.relative_to(channel.parent / DECRYPTED_DIR / channel.name)
            self.timestamp = datetime.datetime.strptime(ts, TIMESTAMP_FORMAT)

            # cleanup orphan links (symlink that points to non existing data
            # don't do this for conflict files or shit breaks loose
            self.link_path = Path.home() / self.name
            self.cleanup_link()
        except ValueError:
            try: # parse CONFLICT file: ~/.dotfiles/common/testdir#IzjOuV4h#20220121162145#D#CRYPT
                name, self.hash, ts,  _, _, _ = path.name.split('#')
                self.path = channel.parent / DECRYPTED_DIR / channel.name / path.relative_to(channel).parent / name
                self.encrypted_path = path
                self.name = self.path.relative_to(channel.parent / DECRYPTED_DIR / channel.name)
                self.timestamp = datetime.datetime.strptime(ts, TIMESTAMP_FORMAT)
            except ValueError:
                try: # parse path that will be used by init to initiate new encrypted dotfile: ~/.dotfiles/common/testfile.txt
                     # allow incomplete data. missing data will be added later
                    self.hash = None
                    self.path = channel.parent / DECRYPTED_DIR / channel.name / path.relative_to(channel)
                    self.name = path.relative_to(channel)
                    try:
                        self.encrypted_path = self.get_encrypted_path(channel, self.name)
                    except FileNotFoundError:
                        self.encrypted_path = None

                    self.timestamp = datetime.datetime.utcnow()
                except ValueError:
                    raise MicrodotError(f"Failed to parse path: {path}")

        self.channel = channel
        self.link_path = Path.home() / self.name
        self.is_encrypted = True
        self._key = key


        # ensure decrypted dir exists
        if not self.path.parent.is_dir():
            debug(self.name, 'mkdir', self.path.parent)
            self.path.parent.mkdir(parents=True)

        # ensure encrypted dir exists
        if self.encrypted_path and not self.encrypted_path.parent.is_dir():
            debug(self.name, 'mkdir', self.encrypted_path.parent)
            self.encrypted_path.parent.mkdir(parents=True)

    def encrypt(self, src, key=None, force=False):
        """ Do some encryption here and write to self.encrypted_path """
        # TODO encrypt should decide on encrypted_path here because it depends on the given src

        if key == None:
            key = self._key

        self.encrypted_path = self.get_encrypted_path(self.channel, self.name, src=src)

        # if dir, compress dir into tmp tar file
        if src.is_dir():
            src = get_tar(src)

        if self.encrypted_path.exists():
            if force:
                self.remove_path(self.encrypted_path)
            else:
                raise MicrodotError(f"Encrypted file exists in channel: {self.encrypted_path}")

        fernet = Fernet(key)
        encrypted = fernet.encrypt(src.read_bytes())

        # cleanyp tmp file
        if src.is_dir():
            src.unlink()

        self.encrypted_path.write_bytes(encrypted)
        debug(self.name, 'encrypted', f'{src.name} -> {self.encrypted_path}')

    def decrypt(self, dest=None):
        """ Do some decryption here and write to dest path """
        if dest == None:
            dest = self.path

        if dest.exists():
            dest.unlink()

        try:
            fernet = Fernet(self._key)
            decrypted = fernet.decrypt(self.encrypted_path.read_bytes())
        except cryptography.fernet.InvalidToken:
            raise MicrodotError(f"Failed to decrypt {self.encrypted_path}, invalid key.")

        dest.write_bytes(decrypted)
        debug(self.name, 'decrypted', f'{self.encrypted_path.name} -> {dest}')

    def link(self, force=False):
        self.decrypt()
        DotFileBaseClass.link(self, force=force)

    def update(self):
        """ Update encrypted file if decrypted file/dir has changed from encrypted file """
        if not self.check_symlink():
            logger.error(f"Dotfile not linked {self.name}")
            return
        if not self.is_changed():
            return
        info(self.name, 'changed', self.path)

        old_encrypted_path = self.encrypted_path
        self.encrypt(self.path, self._key, force=True)
        self.unlink()
        old_encrypted_path.unlink()
        self.link()

        info(self.name, 'updated', f'{self.name} -> {self.encrypted_path.name}')

    def is_changed(self):
        """ Indicate if decrypted dir has changed from encrypted file
            Checks current file md5 against last md5 """
        return not self.check_symlink() or self.hash != get_hash(self.path)

    def get_encrypted_path(self, channel, name, src=None):
        """ If src is specified, calculate hash from this source instead of standard decrypted data location """
        if src == None:
            md5 = get_hash(Path.home() / name)
        else:
            md5 = get_hash(src)

        ts = datetime.datetime.utcnow().strftime(TIMESTAMP_FORMAT)
        if self.is_dir():
            return channel / ENCRYPTED_DIR_FORMAT.format(name=name, ts=ts, md5=md5)
        else:
            return channel / ENCRYPTED_FILE_FORMAT.format(name=name, ts=ts, md5=md5)

    def unlink(self):
        if not DotFileBaseClass.unlink(self):
            return
        self.remove_path(self.path)
        debug(self.name, 'removed', f'decrypted path: {self.path.name}')

    def init(self, src):
        """ Move source path to dotfile location """

        # create managed dir indicator file before encrypting
        if self.is_dir():
            (self.link_path / SCAN_DIR_FILE).touch()

        self.encrypt(src, self._key)
        self.remove_path(src)
        debug(self.name, 'init', f'removed original path: {src}')
        self.link()

    def to_decrypted(self):
        """ Convert encrypted dotfile to decrypted dotfile """
        if not self.is_encrypted:
            raise MicrodotError(f"Dotfile is already encrypted: {self.name}")

        if (was_linked := self.check_symlink()):
            self.unlink()

        path = self.channel / self.name
        self.decrypt(path)
        self.encrypted_path.unlink()

        if was_linked:
            df = DotFileBaseClass(path, self.channel)
            df.link()


class DotFileEncrypted(DotFileEncryptedBaseClass):
    def __init__(self, *args):
        super().__init__(*args)

    def is_file(self):
        return True

    def is_dir(self):
        return False


class DotDirEncrypted(DotFileEncryptedBaseClass):
    def __init__(self, *args):
        super().__init__(*args)

    def is_file(self):
        return False

    def is_dir(self):
        return True

    def decrypt(self, dest=None):
        if dest == None:
            dest = self.path

        tmp_dir = Path(tempfile.mkdtemp())
        tmp_file = Path(tempfile.mktemp())

        DotFileEncryptedBaseClass.decrypt(self, tmp_file)

        with tarfile.open(tmp_file, 'r') as tar:
            tar.extractall(tmp_dir)

        if dest.exists():
            shutil.rmtree(dest, ignore_errors=False, onerror=None)
        # TODO new path doesn't exist yet

        # cant use pathlib's replace because files need to be on same filesystem
        shutil.move((tmp_dir / self.name.name), dest)
        debug(self.name, "moved", f"{tmp_dir/self.name.name} -> {dest}")

        tmp_file.unlink()


class Channel():
    """ Represents a channel, holds encrypted and unencrypted dotfiles. """
    def __init__(self, path, state):
        self._key = state.encryption.key
        self._path = path
        self.name = path.name
        self.dotfiles = self.search_dotfiles(self._path)
        self.dotfiles = self.filter_decrypted(self.dotfiles)
        self._colors = state.colors
        self.conflicts = sorted(self.search_conflicts(self._path, state.core.check_dirs), key=lambda x: x.timestamp, reverse=True)

    def create_obj(self, path):
        """ Create a brand new DotFileBaseClass object """
        if path.name.endswith(ENCRYPTED_DIR_EXT) or path.name.endswith(CONFLICT_DIR_EXT):
            return DotDirEncrypted(path, self._path, self._key)
        elif path.name.endswith(ENCRYPTED_FILE_EXT) or path.name.endswith(CONFLICT_FILE_EXT):
            return DotFileEncrypted(path, self._path, self._key)
        return DotFileBaseClass(path, self._path)

    def filter_decrypted(self, dotfiles):
        """ Check if there are decrypted paths in the list """
        ret = [df for df in dotfiles if df.is_encrypted]
        encr_paths = [df.path for df in dotfiles if df.is_encrypted]

        for df in dotfiles:
            if df.path not in encr_paths:
                ret.append(df)
        return ret

    def is_child_of(self, child: Path, parents: list) -> bool:
        """ Check if one of the paths is a parent of child path """
        for d in parents:
            try:
                child.relative_to(d)
                return d
            except ValueError:
                pass

    def scan_dir(self, path):
        """ Recursive find dotfiles/dirs.
            Dirs contain the SCAN_DIR_FILE, other dirs are ignored.
        """
        paths = []

        for p in path.iterdir():
            if (p / SCAN_DIR_FILE).is_file():
                paths.append(p)
            elif p.is_dir():
                paths += self.scan_dir(p)
            else:
                paths.append(p)
        return paths

    def search_dotfiles(self, directory: Path) -> list:
        items = []
        paths = self.scan_dir(directory)
        for path in paths:
            if path.name.endswith(CONFLICT_EXT):
                continue
            items.append(self.create_obj(path))
        return sorted(items, key=lambda item: item.name)

    def search_conflicts(self, directory, search_dirs):
        """ recursive find of files and dirs in channel when file/dir is in search_dirs """
        items = []
        paths = self.scan_dir(directory)
        for path in paths:
            if path.name.endswith(CONFLICT_EXT):
                items.append(self.create_obj(path))
        return sorted(items, key=lambda item: item.name)

    def parse_conflict(self, name: str) -> str:
        """ Use regex to parse conflict file name, return colored string """
        try:
            r = re.search(r"(.+)#(.+)#([0-9]+)#([A-Z])#([A-Z]+)#([A-Z]+)", name)
        except re.error as e:
            raise MicrodotError(f"Failed to parse string, {e}")
        except TypeError as e:
            raise MicrodotError(f"Failed to parse string, {e}")

        n = []
        n.append(colorize(r.group(1), 'default'))
        n.append(colorize(r.group(2), 'green'))
        n.append(colorize(r.group(3), 'magenta'))
        n.append(colorize(r.group(4), 'blue'))
        n.append(colorize(r.group(5), 'blue'))
        n.append(colorize(r.group(6), 'blue'))
        return colorize('#', 'default').join(n)

    def list(self):
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

        #cols = Columnize()
        cols = Columnize(prefix='  ', prefix_color='red')
        for item in self.conflicts:

            # color format conflict string
            name = self.parse_conflict(item.encrypted_path.name)

            if item.is_dir():
                cols.add([colorize(f"[CD]", self._colors.conflict),
                          name])
            else:
                cols.add([colorize(f"[CF]", self._colors.conflict),
                          name])
        cols.show()

    def get_dotfile(self, name):
        """ Get dotfile object by filename """
        # TODO should raise exception on not found?
        for df in self.dotfiles:
            if str(df.name) == str(name):
                return df
        raise MicrodotError(f"Dotfile not found: {name}")

    def get_encrypted_dotfile(self, name):
        """ Get an encrypted dotfile object by filename """
        for df in self.dotfiles:
            if not df.is_encrypted:
                continue
            if str(df.name) == str(name):
                return df
        raise MicrodotError(f"Encrypted dotfile not found: {name}")

    def get_conflict(self, name):
        """ Get DotFile object by conflict file name """
        for df in self.conflicts:
            if str(df.encrypted_path.name) == str(name):
                return df
        raise MicrodotError(f"Conflict not found: {name}")

    def link_all(self, force=False):
        """ Link all dotfiles in channel """
        dotfiles = [df for df in self.dotfiles if not df.check_symlink()]
        if not (dotfiles := [df for df in self.dotfiles if not df.check_symlink()]):
            info("link_all", "link_all", "Nothing to link")
            return

        for dotfile in dotfiles:
            dotfile.link(force=force)
            info("link_all", "linked", dotfile.name)

    def unlink_all(self):
        """ Unlink all dotfiles in channel """
        if not (dotfiles := [df for df in self.dotfiles if df.check_symlink()]):
            info("unlink_all", "unlink_all", "Nothing to link")
            return

        for dotfile in dotfiles:
            dotfile.unlink()
            info("unlink_all", "unlinked", dotfile.name)

        while path != Path('/'):
            path = path.parent
            if (path/search_name).exists():
                return path

    def dotfile_exists(self, name: str) -> bool:
        try:
            return self.get_dotfile(name)
        except MicrodotError:
            pass

    def search_parents(self, path):
        """ Find an ancestor of path that is already managed by microdot """
        paths = self.scan_dir(self._path)

        while path != Path.home():
            print(path)
            p = self._path / path.relative_to(Path.home())
            if p in paths:
                return p
            path = path.parent

    def init(self, path: Path, encrypted: bool=False) -> DotFileBaseClass:
        """ Start using a dotfile
            Copy dotfile to channel directory and create symlink. """

        try:
            src = self._path / path.absolute().relative_to(Path.home())
        except ValueError:
            raise MicrodotError(f"Path is not relative to homedir: {path}")

        if (ret := self.search_parents(path.absolute())):
            raise MicrodotError(f"A parent of this path is already managed by microdot: {ret}")

        if self.is_child_of(path, [self._path.parent]):
            raise MicrodotError(f"Path should not be inside dotfiles dir: {path}")

        if encrypted:
            if path.is_file():
                dotfile = DotFileEncrypted(src, self._path, self._key)
            elif path.is_dir():
                dotfile = DotDirEncrypted(src, self._path, self._key)
            else:
                raise MicrodotError(f"Path is not a file or directory: {path}")
        else:
            if path.is_file() or path.is_dir():
                dotfile = DotFileBaseClass(src, self._path)
            else:
                raise MicrodotError(f"Path is not a file or directory: {path}")

        # raise error if dotfile already exists
        if self.dotfile_exists(dotfile.name):
            raise MicrodotError(f"Dotfile already managed: {dotfile.name}")

        if not (path.is_file() or path.is_dir()):
            raise MicrodotError(f"Source path is not a file or directory: {path}")

        if path.is_symlink():
            raise MicrodotError(f"Source path is a symlink: {path}")

        dotfile.init(path)

        return dotfile


def get_channels(state):
    """ Find all channels in dotfiles dir and create Channel objects """
    path      = state.core.dotfiles_dir
    blacklist = state.core.channel_blacklist + SCAN_CHANNEL_BLACKLIST
    return [ Channel(d, state) for d in Path(path).iterdir() if d.is_dir() and d.name not in blacklist ]

def get_channel(name, state, create=False, assume_yes=False):
    """ Find or create and return Channel object """
    name         = name if name else "common"
    dotfiles_dir = state.core.dotfiles_dir
    path         = dotfiles_dir / name

    if not path.is_dir():
        if not create:
            raise MicrodotError(f"Channel {name} not found")

        if not confirm(f"Channel {name} doesn't exist, would you like to create it?", assume_yes=assume_yes):
            return
        try:
            path.mkdir(parents=True)
            info("get_channel", "created_channel", name)
        except PermissionError as e:
            logger.error(f"Failed to create channel: {name}")
            raise MicrodotError("Failed to create channel: {name}")

    for channel in get_channels(state):
        if channel.name == name:
            return channel

    raise MicrodotError(f"This should be unreachable, failed to find channel: {name}")

# TODO below should be part of channel class??
def get_encrypted_dotfiles(linked=False, grouped=False):
    """ Return encrypted dotfiles
        grouped=True: doubles are grouped by filename, will be used to find conflicting files
        linked=True:  only return dotfiles that are linked """

    items = []
    keyfunc = lambda x: x.name

    for channel in get_channels(state):
        data = [x for x in channel.dotfiles if x.is_encrypted]

        if linked:
            data = [x for x in data if x.check_symlink()]

        data = sorted(data, key=keyfunc)

        if grouped:
            for k, g in groupby(data, keyfunc):
                items.append(list(g))
        else:
            items += data
    return items

def update_encrypted_from_decrypted():
    for df in get_encrypted_dotfiles(linked=True):
        df.update()
