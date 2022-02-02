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
from dataclasses import dataclass

from core.exceptions import MicrodotError, MDConflictError, MDLinkError, MDEncryptionError
from core.exceptions import MDDotNotFoundError, MDChannelNotFoundError, MDPathNotFoundError
from core.exceptions import MDPathLocationError, MDPathExistsError, MDPermissionError, MDParseError
from core import state
from core import CONFLICT_EXT, ENCRYPTED_DIR_EXT, ENCRYPTED_FILE_EXT, ENCRYPTED_DIR_FORMAT, ENCRYPTED_FILE_FORMAT
from core import CONFLICT_FILE_EXT, CONFLICT_DIR_EXT, TIMESTAMP_FORMAT, DECRYPTED_DIR, SCAN_CHANNEL_BLACKLIST, SCAN_DIR_BLACKLIST
from core import SCAN_DIR_FILE
from core.utils import confirm, colorize, debug, info, get_hash, get_tar
from core.tree import TreeNode

from cryptography.fernet import Fernet
import cryptography

logger = logging.getLogger("microdot")


@dataclass
class Conflict():
    """ Represents a conflict file, is instantiated by DotEncryptedBaseClass """
    path: Path
    name: str

    def parse(self) -> str:
        """ Use regex to parse conflict file name, return colored string """
        try:
            r = re.search(r"(.+)#(.+)#([0-9]+)#([A-Z])#([A-Z]+)#([A-Z]+)", self.name.name)
        except re.error as e:
            # TODO needs unittest
            raise MDParseError(f"Failed to parse string, {e}")
        except TypeError as e:
            raise MDParseError(f"Failed to parse string, {e}")

        n = []
        n.append(colorize(r.group(1), 'blue'))
        n.append(colorize(r.group(2), 'green'))
        n.append(colorize(r.group(3), 'magenta'))
        n.append(colorize(r.group(4), 'blue'))
        n.append(colorize(r.group(5), 'blue'))
        n.append(colorize(r.group(6), 'blue'))
        return colorize("CONFLICT ",state.colors.conflict) + colorize('#', 'blue').join(n)


class DotBaseClass():
    """ Represents an unencrypted dotfile/dir.
        Is also the baseclass for DotEncryptedBaseClass """
    def __init__(self, path, channel):
        """ path is where dotfile source is: /home/eco/.dotfiles/common/testfile.txt """

        self.channel = channel
        self.path = path
        self.name = path.relative_to(channel)
        self.link_path = Path.home() / self.name
        self.is_encrypted = False
        self.cleanup_link()

        if not self.path.parent.is_dir():
            debug("__init__", 'mkdir', self.path.parent)
            self.path.parent.mkdir(parents=True)

    def cleanup_link(self):
        # find orphan links (symlink that points 
        if self.link_path.is_symlink():
            if not self.path.exists():
                self.link_path.unlink()
                info("cleanup_link", "remove", f"orphan link found: {self.link_path}")
            #elif not self.link_path.resolve() == self.path:
            #    info("cleanup_link", "remove", f"link doesn't point to data: {self.link_path}")
            #    self.link_path.unlink()
            elif not self.link_path.resolve().exists():
                info("cleanup_link", "remove", f"link doesn't point to existing data: {self.link_path}")
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
            raise MDLinkError(f"Dotfile is already linked: {self.name}")

        link = self.link_path

        # NOTE: calls a function outside of class
        if (df := search_conflicting_dotfiles(self.link_path.absolute())):
            raise MDConflictError(f"Path conflicts with '{df.name}' in channel '{df.channel.name}'")

        if not link.parent.is_dir():
            link.parent.mkdir(parents=True)

        if not target:
            target = self.path

        if link.is_symlink():
            link.unlink()

        if link.exists() and force:
            self.remove_path(link)
            info("link", "removed", "Path exists, using --force to overwrite: {link}")

        if link.is_symlink():
            raise MDLinkError(f"Dotfile already linked: {link}")

        if link.exists():
            raise MDLinkError(f"Path exists at link location: {link}")

        link.symlink_to(target)
        debug("link", 'linked', f'{link} -> {target.name}')
        return True
    
    def unlink(self):
        if not self.check_symlink():
            raise MDLinkError(f"Dotfile is not linked: {self.name}")

        self.link_path.unlink()
        debug("unlink", 'unlinked', self.link_path)
        return True

    def init(self, src, link=True):
        """ Move source path to dotfile location """
        shutil.move(src, self.path)
        debug("init", 'moved', f'{src} -> {self.path}')

        if link:
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
            raise MDEncryptionError(f"Dotfile is already encrypted: {self.name}")

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
        

class DotEncryptedBaseClass(DotBaseClass):
    """ Baseclass for all encrypted files/directories """
    def __init__(self, path, channel, key):
        try: # parse CRYPT file: ~/.dotfiles/common/testdir#IzjOuV4h#20220121162145#D#CRYPT
            name, self.hash, ts,  _, _ = path.name.split('#')
            self.path = channel.parent / DECRYPTED_DIR / channel.name / path.relative_to(channel).parent / name
            self.encrypted_path = path
            self.name = self.path.relative_to(channel.parent / DECRYPTED_DIR / channel.name)
            self.timestamp = datetime.datetime.strptime(ts, TIMESTAMP_FORMAT)
            self.link_path = Path.home() / self.name
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
                # TODO needs unittest
                raise MDParseError(f"Failed to parse path: {path}")

        self.channel = channel
        self.link_path = Path.home() / self.name
        self.is_encrypted = True
        self._key = key

        # cleanup orphan links (symlink that point to non existing data
        self.cleanup_link()

        # ensure decrypted dir exists
        if not self.path.parent.is_dir():
            debug("__init__", 'mkdir', self.path.parent)
            self.path.parent.mkdir(parents=True)

        # ensure encrypted dir exists
        if self.encrypted_path and not self.encrypted_path.parent.is_dir():
            debug("__init__", 'mkdir', self.encrypted_path.parent)
            self.encrypted_path.parent.mkdir(parents=True)

    def get_conflicts(self):
        """ Find conflicts that belong to this dotfile/dir """
        conflicts = []
        for p in self.encrypted_path.parent.iterdir():
            if not p.name.endswith(CONFLICT_EXT):
                continue
            try:
                name, _, _,  _, _, _ = p.name.split('#')
                if name == self.name.name:
                    conflicts.append(Conflict(p, p.relative_to(self.channel)))
            except ValueError:
                pass
        return conflicts

    def get_conflict(self, path):
        for c in self.get_conflicts():
            if c.name == path:
                return c

    def decrypt_conflict(self, conflict, dest):
        self.decrypt(src=conflict.path, dest=dest)

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
                raise MDPathExistsError(f"Encrypted file exists in channel: {self.encrypted_path}")

        fernet = Fernet(key)
        encrypted = fernet.encrypt(src.read_bytes())

        # cleanyp tmp file
        if src.is_dir():
            src.unlink()

        self.encrypted_path.write_bytes(encrypted)
        debug("encrypt", 'encrypted', f'{src.name} -> {self.encrypted_path}')

    def decrypt(self, dest=None, src=None):
        """ Do some decryption here and write to dest path """
        if dest == None:
            dest = self.path

        if src == None:
            src = self.encrypted_path

        if dest.exists():
            dest.unlink()

        try:
            fernet = Fernet(self._key)
            decrypted = fernet.decrypt(src.read_bytes())
        except cryptography.fernet.InvalidToken:
            # TODO needs unittest
            raise MDEncryptionError(f"Failed to decrypt {src}, invalid key.")

        dest.write_bytes(decrypted)
        debug("decrypt", 'decrypted', f'{src.name} -> {dest}')

    def link(self, force=False):
        self.decrypt()
        DotBaseClass.link(self, force=force)

    def update(self):
        """ Update encrypted file if decrypted file/dir has changed from encrypted file """
        if not self.check_symlink():
            logger.error(f"Dotfile not linked {self.name}")
            return
        if not self.is_changed():
            return
        info("update", 'changed', self.path)

        old_encrypted_path = self.encrypted_path
        self.encrypt(self.path, self._key, force=True)
        self.unlink()
        old_encrypted_path.unlink()
        self.link()

        info("update", 'updated', f'{self.name} -> {self.encrypted_path.name}')

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
        if not DotBaseClass.unlink(self):
            return
        self.remove_path(self.path)
        debug("unlink", 'removed', f'decrypted path: {self.path.name}')

    def init(self, src, link=True):
        """ Move source path to dotfile location """
        self.encrypt(src, self._key)
        self.remove_path(src)
        debug("init", 'init', f'removed original path: {src}')

        if link:
            self.link()

    def to_decrypted(self):
        """ Convert encrypted dotfile to decrypted dotfile """
        if not self.is_encrypted:
            raise MDEncryptionError(f"Dotfile is already encrypted: {self.name}")

        if (was_linked := self.check_symlink()):
            self.unlink()

        path = self.channel / self.name
        self.decrypt(path)
        self.encrypted_path.unlink()

        if was_linked:
            df = DotBaseClass(path, self.channel)
            df.link()


class DotFileEncrypted(DotEncryptedBaseClass):
    """ Represents encrypted file """
    def __init__(self, *args):
        super().__init__(*args)

    def is_file(self):
        return True

    def is_dir(self):
        return False


class DotDirEncrypted(DotEncryptedBaseClass):
    """ Represents encrypted dir """
    def __init__(self, *args):
        super().__init__(*args)

    def is_file(self):
        return False

    def is_dir(self):
        return True

    def decrypt(self, dest=None, src=None):
        if dest == None:
            dest = self.path

        tmp_dir = Path(tempfile.mkdtemp())
        tmp_file = Path(tempfile.mktemp())

        DotEncryptedBaseClass.decrypt(self, src=src, dest=tmp_file)

        with tarfile.open(tmp_file, 'r') as tar:
            tar.extractall(tmp_dir)

        if dest.exists():
            shutil.rmtree(dest, ignore_errors=False, onerror=None)

        # cant use pathlib's replace because files need to be on same filesystem
        shutil.move((tmp_dir / self.name.name), dest)
        debug("decrypt", "moved", f"{tmp_dir/self.name.name} -> {dest}")

        tmp_file.unlink()


class Channel():
    """ Represents a channel, holds encrypted and unencrypted dotfiles. """
    def __init__(self, path, state):
        self._key = state.encryption.key
        self._path = path
        self.name = path.name
        self.dotfiles = self.search_dotfiles(self._path)
        self._colors = state.colors

    def format_df(self, prefix, name, color):
        return prefix +  colorize(name, color)

    def add_tree_nodes(self, df, node: TreeNode):
        """ Create TreeNode structure, will be listed by list() """
        # get or create all parent nodes
        path = df.link_path.relative_to(Path.home())
        for p in reversed(path.parents[:-1]):
            node = node.get_child(colorize(p.name, state.colors.tree_dirs))

        # add dotfile/dir node
        color = self._colors.linked if df.check_symlink() else self._colors.unlinked
        name = f"{df.name.name}/" if df.is_dir() else df.name.name
        prefix = colorize('CRYPT ', state.colors.encrypted) if df.is_encrypted else ''
        child = node.get_child(self.format_df(prefix, name, color))

        if df.is_encrypted:
            for conflict in df.get_conflicts():
                node.add_child(conflict.parse())

    def list(self, display=True):
        root = TreeNode(colorize(f"channel: {self.name}", state.colors.channel_name))

        dotfiles  =  [d for d in self.dotfiles if d.is_dir() and not d.is_encrypted]
        dotfiles += [f for f in self.dotfiles if f.is_file() and not f.is_encrypted]
        dotfiles += [d for d in self.dotfiles if d.is_dir() and d.is_encrypted]
        dotfiles += [f for f in self.dotfiles if f.is_file() and f.is_encrypted]

        for df in dotfiles:
            self.add_tree_nodes(df, root)

        if not dotfiles:
            root.add_child(colorize("Empty", "bred"))

        if display:
            root.display(tree_color=state.colors.tree)

        return root

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
            info("unlink_all", "unlink_all", "Nothing to unlink")
            return

        for dotfile in dotfiles:
            dotfile.unlink()
            info("unlink_all", "unlinked", dotfile.name)

    def init(self, path: Path, encrypted: bool=False, link: bool=True) -> DotBaseClass:
        """ Start using a dotfile
            Copy dotfile to channel directory and create symlink. """

        try:
            src = self._path / path.absolute().relative_to(Path.home())
        except ValueError:
            raise MDPathLocationError(f"Path is not in {Path.home()}: {path}")

        if self.is_child_of(path, [self._path.parent]):
            raise MDPathLocationError(f"Path should not be inside dotfiles dir: {path}")

        if (df := search_conflicting_dotfiles(path.absolute())):
            raise MDConflictError(f"Path conflicts with '{df.name}' in channel '{df.channel.name}'")

        if encrypted:
            if path.is_file():
                dotfile = DotFileEncrypted(src, self._path, self._key)
            elif path.is_dir():
                dotfile = DotDirEncrypted(src, self._path, self._key)
            else:
                raise MDPathNotFoundError(f"Path is not a file or directory: {path}")
        else:
            if path.is_file() or path.is_dir():
                dotfile = DotBaseClass(src, self._path)
            else:
                raise MDPathNotFoundError(f"Path is not a file or directory: {path}")

        # raise error if dotfile already exists
        if self.dotfile_exists(dotfile.name):
            raise MDConflictError(f"Dotfile already managed: {dotfile.name}")

        if not (path.is_file() or path.is_dir()):
            raise MDPathNotFoundError(f"Source path is not a file or directory: {path}")

        dotfile.init(path, link=link)

        return dotfile

    def is_conflict(self, path: Path):
        """ Check if path conflicts with other dotfile in this channel.
            Returns dotfile if:
                - dotfile is linked
                - path is in a parent path of another dotfile
                - path is in a child path of another dotfile
        """
        for df in self.dotfiles:
            try:
                df.link_path.relative_to(path)
                if df.check_symlink():
                    return df
            except ValueError:
                pass

            try:
                path.relative_to(df.link_path)
                if df.check_symlink():
                    return df
            except ValueError:
                pass

    def scan_dir(self, path):
        """ Recursive find paths to dotfiles/dirs.
            Dotdirs contain the SCAN_DIR_FILE
            Dotfiles are endpoints in channel dir that are not within a dotdir
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
        """ Search channel for dotfile/dirs """
        items = []
        for path in self.scan_dir(directory):
            if path.name.endswith(CONFLICT_EXT):
                continue
            elif path.name.endswith(ENCRYPTED_DIR_EXT):
                items.append(DotDirEncrypted(path, self._path, self._key))
            elif path.name.endswith(ENCRYPTED_FILE_EXT):
                items.append(DotFileEncrypted(path, self._path, self._key))
            else:
                items.append(DotBaseClass(path, self._path))
        return sorted(items, key=lambda item: item.name)

    def get_dotfile(self, name):
        """ Get dotfile object by filename """
        for df in self.dotfiles:
            if str(df.name) == str(name):
                return df
        raise MDDotNotFoundError(f"Dotfile not found: {name}")

    def get_encrypted_dotfile(self, name):
        """ Get an encrypted dotfile object by filename """
        for df in self.dotfiles:
            if df.is_encrypted and str(df.name) == str(name):
                return df
        raise MDDotNotFoundError(f"Encrypted dotfile not found: {name}")

    def dotfile_exists(self, name: str) -> bool:
        try:
            return self.get_dotfile(name)
        except MDDotNotFoundError:
            pass

    def is_child_of(self, child: Path, parents: list) -> bool:
        """ Check if one of the paths is a parent of child path """
        for parent in parents:
            try:
                child.relative_to(parent)
                return parent
            except ValueError:
                pass


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
            raise MDChannelNotFoundError(f"Channel {name} not found")

        if not confirm(f"Channel {name} doesn't exist, would you like to create it?", assume_yes=assume_yes):
            return
        try:
            path.mkdir(parents=True)
            info("get_channel", "created", name)
        except PermissionError as e:
            raise MDPermissionError("Insufficient permissions to create channel: {name}")

    for channel in get_channels(state):
        if channel.name == name:
            return channel

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

def search_conflicting_dotfiles(path: Path):
    """ Search other channels for conflicted paths.
        WARNING: uses a function not in this class.
                 Need to fix this later 
    """
    for channel in get_channels(state):
        if (df := channel.is_conflict(path)):
            return df


