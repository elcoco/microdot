import logging
from pathlib import Path
import shutil
import hashlib
import tarfile
import tempfile
from itertools import groupby

from core.exceptions import MicrodotError
from core import gitignore
from core import state

from core.utils import confirm, colorize

try:
    from cryptography.fernet import Fernet
    import cryptography
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

logger = logging.getLogger("microdot")

ENCRYPTED_DIR_FORMAT  = "{name}#{md5}#DIR#ENCRYPTED"
ENCRYPTED_FILE_FORMAT  = "{name}#{md5}#FILE#ENCRYPTED"
TMP_FILE_PATH = '/tmp/microdot.tmp.tar'


"""
    You can add a new encrypted file with: $ md --init file.txt -e
    This will:
        - Move the file to the channel directory
        - Encrypt the file, using the extension: .encrypted
        - Decrypt the encrypted file and place it next to the encrypted file.
        - Add the non-encrypted file to the .gitignore file to protect it from pushing to GIT.
        
    When linking an encrypted file:
        The encrypted file will be visible in the list without the .encrypted extension but with a [E] marker
        The encrypted file can be linked as normal with: $ md --link file.txt
        This will:
            - Decrypt the corresponding encrypted file and place it next to the encrypted file.
            - Add the non-encrypted file to the .gitignore file to protect it from pushing to GIT.

    When unlinking an encrypted file:
        The encrypted file will be visible in the list without the .encrypted extension but with a [E] marker
        The encrypted file can be unlinked as normal with: $ md --unlink file.txt
        This will:
            - Remove the link
            - Remove the un-encrypte file
            - Remove the file entry on the .gitignore file

    When the repository is updated, the linked encrypted files need to be decrypted by using: $ md --update
    We can automate this by managing the GIT repo for the user, but this will add more complexity.
"""

class DotFile():
    def __init__(self, path, channel):
        self.channel = channel
        self.path = path
        self.name = path.relative_to(channel)
        self.link_path = Path.home() / self.name
        self.is_encrypted = False

    def check_symlink(self):
        # check if link links to src
        if not self.link_path.is_symlink():
            return
        return self.link_path.resolve() == self.path

    def is_dir(self):
        return self.path.is_dir()

    def is_file(self):
        return self.path.is_file()

    def link(self, force=False):
        link = self.link_path

        if link.exists() and force:
            logger.info(f"Link path exists, using --force to overwrite: {link}")
            if link.is_file():
                os.remove(link)
            elif link.is_symlink():
                link.unlink()
            elif link.is_dir():
                shutil.rmtree(link)
            else:
                raise MicrodotError(f"Failed to remove path: {link}")

        if link.is_symlink():
            raise MicrodotError(f"Dotfile already linked: {link}")

        if link.exists():
            raise MicrodotError(f"Link exists: {link}")

        link.symlink_to(self.path)
        logger.info(f"Linked: {link} -> {self.path}")
        return True
    
    def unlink(self):
        if not self.check_symlink():
            logger.error(f"Dotfile is not linked: {self.name}")
            return

        self.link_path.unlink()
        print(f"Unlink: unlinked: {self.link_path}")
        return True

    def init(self, src):
        """ Move source path to dotfile location """
        src.replace(self.path)
        logger.info(f"Moved: {src} -> {self.path}")
        self.link()


class DotFileEncryptedBaseClass(DotFile):
    """ Baseclass for all encrypted files/directories """
    def __init__(self, path, channel, key):
        # parse filename
        try:
            name, self.hash, _, _ = path.name.split('#')
            self.path = (path.parent / name)
            self.encrypted_path = path
        except ValueError:
            logger.info(f"instantiated by init(), allow incomplete data: {path}")
            self.hash = None
            self.encrypted_path = None
            self.path = path

        self.channel = channel
        self.name = self.path.relative_to(channel)
        self.link_path = Path.home() / self.name
        self.is_encrypted = True
        self._key = key

    def encrypt(self, src, key, force=False):
        """ Do some encryption here and write to dest path """
        if self.encrypted_path.exists():
            if force:
                shutil.rmtree(self.encrypted_path, ignore_errors=False, onerror=None)
            else:
                raise MicrodotError(f"Encrypted file exists in channel: {self.encrypted_path}")

        fernet = Fernet(key)
        encrypted = fernet.encrypt(src.read_bytes())

        self.encrypted_path.write_bytes(encrypted)
        print(f"Encrypt: encrypted: {src} -> {self.encrypted_path}")

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
        logger.info(f"Decrypt: decrypted {self.encrypted_path} -> {dest}")

    def link(self, force=False):
        if self.link_path.is_symlink():
            raise MicrodotError(f"Dotfile already linked: {self.link_path}")
        self.decrypt()
        DotFile.link(self, force=force)

    def get_tar(self, src):
        """ Compress path into tar archive and save in tmp file """
        # source is a directory, first create tar archive
        tmp_file = Path(tempfile.mktemp())

        logger.info("Get_tar: encrypting directory")
        with tarfile.open(tmp_file, 'w') as f:
            f.add(src, arcname=src.name)
        return tmp_file

    def get_hash(self, path):
        """ Get hash of file name and contents """
        m = hashlib.md5()
        m.update(path.name.encode())

        if path.is_dir():
            for p in path.rglob("*"):
                m.update(p.read_bytes())
                m.update(p.name.encode())
            return m.hexdigest()

        m.update(path.read_bytes())
        return m.hexdigest()

    def is_changed(self):
        """ Checks current md5 against last md5 """
        
        #if self.hash != self.get_hash(self.path):
        #    logger.info(50*'-')
        #    logger.info(f"Is_changed: path:     {self.path}")
        #    logger.info(f"Is_changed: old hash: {self.hash}")
        #    logger.info(f"Is_changed: new hash: {self.get_hash(self.path)}")
        #    logger.info(50*'-')
        return self.hash != self.get_hash(self.path)


class DotFileEncrypted(DotFileEncryptedBaseClass):
    def __init__(self, *args):
        super().__init__(*args)

    def is_file(self):
        return True

    def is_dir(self):
        return False

    def init(self, src):
        """ Move source path to dotfile location """
        md5 = self.get_hash(src)
        self.encrypted_path = self.path.parent / ENCRYPTED_FILE_FORMAT.format(name=self.name, md5=md5)

        self.encrypt(src, self._key)
        src.unlink()
        logger.info(f"Init: removed original file: {src}")
        self.link()

    def unlink(self):
        if not DotFile.unlink(self):
            return
        logger.info(f"Unlink: removing decrypted file: {self.path}")
        self.path.unlink()

    def update(self):
        """ If decrypted directory has changed, update encrypted file """
        if not self.is_changed():
            return
        logger.info(f"Detected change in: {self.path}")

        old_encrypted_path = self.encrypted_path

        md5 = self.get_hash(self.path)
        self.encrypted_path = self.path.parent / ENCRYPTED_FILE_FORMAT.format(name=self.name, md5=md5)
        self.encrypt(self.path, self._key, force=True)
        logger.info(f"Update: updated: {self.name} -> {self.encrypted_path}")

        self.unlink()
        old_encrypted_path.unlink()
        self.link()

        logger.info(f"Update: updated: {self.name} -> {self.encrypted_path}")


class DotDirEncrypted(DotFileEncryptedBaseClass):
    def __init__(self, *args):
        super().__init__(*args)

    def is_file(self):
        return False

    def is_dir(self):
        return True

    def update(self):
        """ If decrypted directory has changed, update encrypted file """
        if not self.is_changed():
            return

        logger.info(f"Detected change in: {self.path}")

        # we need to remove this path later
        old_encrypted_path = self.encrypted_path

        md5 = self.get_hash(self.path)
        self.encrypted_path = self.path.parent / ENCRYPTED_DIR_FORMAT.format(name=self.name, md5=md5)

        logger.debug(f"Update: using path: {self.path}")
        tmp_file = self.get_tar(self.path)
        self.encrypt(tmp_file, self._key, force=True)
        tmp_file.unlink()

        self.unlink()
        old_encrypted_path.unlink()
        self.link()

        logger.info(f"Update: updated: {self.name} -> {self.encrypted_path}")

    def decrypt(self):
        tmp_dir = Path(tempfile.mkdtemp())
        tmp_file = Path(tempfile.mktemp())

        DotFileEncryptedBaseClass.decrypt(self, tmp_file)

        logger.debug(f"Decrypt: extracting: {tmp_file} -> {tmp_dir}")
        with tarfile.open(tmp_file, 'r') as tar:
            tar.extractall(tmp_dir)

        if self.path.exists():
            logger.debug(f"Decrypt: removing dir: {self.path}")
            shutil.rmtree(self.path, ignore_errors=False, onerror=None)

        # cant use pathlib's replace because files need to be on same filesystem
        logger.debug(f"Decrypt: moving: {tmp_dir / self.name} -> {self.path}")
        print(f"Decrypt: {tmp_dir/self.name}, exist: {(tmp_dir/self.name).is_dir()}")
        shutil.move((tmp_dir / self.name), self.path)

        logger.debug(f"Decrypt: removing tmp file: {tmp_file}")
        tmp_file.unlink()

    def init(self, src):
        """ Move source path to dotfile location """
        md5 = self.get_hash(src)
        self.encrypted_path = self.path.parent / ENCRYPTED_DIR_FORMAT.format(name=self.name, md5=md5)

        logger.debug(f"Init: using path: {src}")

        tmp_file = self.get_tar(src)
        self.encrypt(tmp_file, self._key)
        tmp_file.unlink()

        shutil.rmtree(src, ignore_errors=False, onerror=None)
        logger.info(f"Init: removed original directory: {src}")
        self.link()

    def unlink(self):
        if not DotFile.unlink(self):
            return
        logger.info(f"Unlink: removing decrypted dir: {self.path}")
        shutil.rmtree(self.path, ignore_errors=False, onerror=None)
        

class Channel():
    def __init__(self, path, state):
        self._key = state.encryption.key
        self._path = path
        self.name = path.name
        self.dotfiles = self.search_dotfiles(self._path, state.core.check_dirs)
        self.dotfiles = self.filter_decrypted(self.dotfiles)

        self._colors = state.colors

    def create_obj(self, path):
        """ Create a brand new DotFile object """
        
        if path.name.endswith("#DIR#ENCRYPTED"):
            return DotDirEncrypted(path, self._path, self._key)
        elif path.name.endswith("#FILE#ENCRYPTED"):
            return DotFileEncrypted(path, self._path, self._key)
        return DotFile(path, self._path)

    def filter_decrypted(self, dotfiles):
        """ Check if there are decrypted paths in the list """
        ret = [df for df in dotfiles if df.is_encrypted]
        encr_paths = [df.path for df in dotfiles if df.is_encrypted]

        for df in dotfiles:
            if df.path not in encr_paths:
                ret.append(df)
        return ret

    def search_dotfiles(self, item, search_dirs):
        # TODO fileter out unencrypted versions of encrypted files
        # recursive find of files and dirs in channel when file/dir is in search_dirs
        items = [self.create_obj(f) for f in item.iterdir() if f.is_file()]

        for d in [d for d in item.iterdir() if d.is_dir()]:
            if d.name in search_dirs:
                items += self.search_dotfiles(d, search_dirs)
            else:
                items.append(self.create_obj(d))
        return sorted(items, key=lambda item: item.name)

    def list(self):
        """ Pretty print all dotfiles """
        print(colorize(f"\nchannel: {self.name}", self._colors.channel_name))

        items =  [d for d in self.dotfiles if d.is_dir()]
        items += [f for f in self.dotfiles if f.is_file()]

        if len(items) == 0:
            print(colorize(f"No dotfiles yet!", 'red'))
            return

        for item in items:
            color = self._colors.linked if item.check_symlink() else self._colors.unlinked

            if item.is_encrypted:
                print(colorize(f"[E] {item.name}", color))
            elif item.is_dir():
                print(colorize(f"[D] {item.name}", color))
            else:
                print(colorize(f"[F] {item.name}", color))

    def get_dotfile(self, name):
        for df in self.dotfiles:
            if str(df.name) == str(name):
                return df

    def link_all(self, force=False, assume_yes=False):
        if confirm(f"Link all dotfiles in channel {self.name}?", assume_yes):
            for dotfile in self.dotfiles:
                dotfile.link(force=force)

    def unlink_all(self, assume_yes=False):
        if confirm(f"Unlink all dotfiles in channel {self.name}?", assume_yes):
            for dotfile in self.dotfiles:
                dotfile.unlink()

    def init(self, path, encrypted=False):
        """ Start using a dotfile.
            Copy dotfile to channel directory and create symlink. """

        src = self._path / path.absolute().relative_to(Path.home())

        if encrypted:
            if path.is_file():
                dotfile = DotFileEncrypted(src, self._path, self._key)
            elif path.is_dir():
                dotfile = DotDirEncrypted(src, self._path, self._key)
            else:
                raise MicrodotError(f"Don't know what to do with this path: {path}")
        else:
            dotfile = DotFile(src, self._path)

        #dotfile = self.create_obj(src)

        if self.get_dotfile(dotfile.name):
            logger.error(f"Dotfile already exists in channel: {dotfile.name}")
            return

        if not (path.is_file() or path.is_dir()):
            logger.error(f"Source path is not a file or directory: {path}")
            return

        if path.is_symlink():
            logger.error(f"Source path is a symlink: {path}")
            return

        dotfile.init(path)
        #path.replace(dotfile.path)
        #dotfile.link()
        return dotfile


def get_channels(state):
    """ Find all channels in dotfiles dir and create Channel objects """
    path      = state.core.dotfiles_dir
    blacklist = state.core.channel_blacklist
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
            logger.info(f"Created channel: {name}")
        except PermissionError as e:
            logger.error(f"Failed to create channel: {name}")
            raise MicrodotError("Failed to create channel: {name}")

    for channel in get_channels(state):
        if channel.name == name:
            return channel

    raise MicrodotError(f"This should be unreachable, failed to find channel: {name}")

def get_linked_encrypted_dotfiles(state, linked=True):
    linked = []
    for channel in get_channels(state):
        for dotfile in channel.dotfiles:
            if dotfile.is_encrypted and dotfile.check_symlink():
                linked.append(dotfile)
    return linked

def get_encrypted_dotfiles():
    """ Return encrypted dotfiles, doubles are grouped by filename """

    groups = []
    keyfunc = lambda x: x.name

    for channel in get_channels(state):
        data = [x for x in channel.dotfiles if x.is_encrypted]
        data = sorted(data, key=keyfunc)
        for k, g in groupby(data, keyfunc):
            groups.append(list(g))

    return groups

def update_encrypted_from_decrypted():
    for df in get_linked_encrypted_dotfiles(state):
        df.update()

def update_decrypted_from_encrypted(paths):
    """ Redecrypt all encrypted dotfiles on update """
    # TODO This is the only place in the code where state is not explicitly passed
    #      It isn't pretty but this funciton is used as a callback, so yeah... needs fixin!
    for p in paths:
        channel = get_channel(p.parts[0], state, create=False)
        df_path = p.relative_to(channel.name). with_suffix('')
        dotfile = channel.get_dotfile(df_path)
        dotfile.decrypt()
