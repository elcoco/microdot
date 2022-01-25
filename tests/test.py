#!/usr/bin/env python3

import sys
import unittest
import logging
import tempfile
from pathlib import Path
import shutil

sys.path.append('../microdot')

from core.channel import get_channel
from core import state
from core.utils import info
from core.exceptions import MicrodotError

logger = logging.getLogger("microdot")

logger.setLevel(logging.DEBUG)


class TestInit(unittest.TestCase):
    def setUp(self):
        state.core.dotfiles_dir = Path(tempfile.mkdtemp(prefix=f'dotfiles_'))
        state.channel = get_channel('common', state, create=True, assume_yes=True)

        self.testdir = self.create_dir(Path.home() / '.config/testdir')

        self.testfile = Path.home() / '.config/dotfile.txt'
        self.testfile.write_text("bevers zijn awesome")

        self.addCleanup(self.cleanup, state.core.dotfiles_dir)
        self.addCleanup(self.cleanup, self.testdir)
        self.addCleanup(self.cleanup, self.testfile)

    def cleanup(self, item):
        """ Cleanup list of files/dirs """
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item, ignore_errors=False, onerror=None)
        else:
            #logger.error(f"Don't know how to cleanup path: {item}")
            return
        info("cleanup", "removed", item)

    def create_dir(self, path):
        path.mkdir()
        subdir = (path / 'subdir')
        subdir.mkdir()
        file1 = (path / 'file1.txt').write_text("bevers")
        sub_file1 = (subdir / 'file1.txt').write_text("bevers")
        return path

    def test_get_non_existing_things(self):
        # check that channel is created when requested
        state.channel = get_channel('non_existing', state, create=True, assume_yes=True)
        self.assertTrue((state.core.dotfiles_dir / 'non_existing').is_dir())

        # try to get non existing dotfile
        self.assertTrue(state.channel.get_dotfile("non_existing") == None)

        # try to get non existing encrypted dotfile
        self.assertTrue(state.channel.get_encrypted_dotfile("non_existing") == None)

        # try to init non existing files
        with self.assertRaises(MicrodotError):
            state.channel.init(Path("non_existing"), encrypted=False)

        with self.assertRaises(MicrodotError):
            state.channel.init(Path("non_existing"), encrypted=True)

    def test_init_link_unlink_unencrypted_file(self):
        # action
        df = state.channel.init(self.testfile, encrypted=False)

        # assert
        self.assertTrue(df.path.is_file())
        self.assertTrue(self.testfile.resolve() == df.path)
        self.assertTrue(self.testfile.is_symlink())

        #action
        df.unlink()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df.unlink()

        # assert
        self.assertTrue(df.path.is_file())
        self.assertFalse(self.testfile.is_symlink())

        #action
        df.link()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df.link()

        # assert
        self.assertTrue(df.path.is_file())
        self.assertTrue(self.testfile.resolve() == df.path)
        self.assertTrue(self.testfile.is_symlink())

    def test_init_link_unlink_unencrypted_dir(self):
        # action
        df = state.channel.init(self.testdir, encrypted=False)

        # assert
        self.assertTrue(df.path.is_dir())
        self.assertTrue(self.testdir.resolve() == df.path)
        self.assertTrue(self.testdir.is_symlink())

        #action
        df.unlink()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df.unlink()

        # assert
        self.assertTrue(df.path.is_dir())
        self.assertFalse(self.testdir.is_symlink())

        #action
        df.link()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df.link()

        # assert
        self.assertTrue(df.path.is_dir())
        self.assertTrue(self.testdir.resolve() == df.path)
        self.assertTrue(self.testdir.is_symlink())

    def test_init_link_unlink_encrypted_file(self):
        # action
        df = state.channel.init(self.testfile, encrypted=True)

        # assert
        self.assertTrue(df.path.is_file())
        self.assertTrue(self.testfile.is_symlink())
        self.assertTrue(df.encrypted_path.is_file())
        self.assertTrue(self.testfile.resolve() == df.path)

        #action
        df.unlink()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df.unlink()

        # assert
        self.assertFalse(df.path.exists())
        self.assertFalse(self.testfile.is_symlink())
        self.assertTrue(df.encrypted_path.is_file())

        #action
        df.link()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df.link()

        # assert
        self.assertTrue(df.path.is_file())
        self.assertTrue(self.testfile.is_symlink())
        self.assertTrue(df.encrypted_path.is_file())
        self.assertTrue(self.testfile.resolve() == df.path)

    def test_init_link_unlink_encrypted_dir(self):
        # action
        df = state.channel.init(self.testdir, encrypted=True)

        # assert
        self.assertTrue(df.path.is_dir())
        self.assertTrue(self.testdir.is_symlink())
        self.assertTrue(df.encrypted_path.is_file())
        self.assertTrue(self.testdir.resolve() == df.path)

        #action
        df.unlink()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df.unlink()

        # assert
        self.assertFalse(df.path.exists())
        self.assertFalse(self.testdir.is_symlink())
        self.assertTrue(df.encrypted_path.is_file())

        df.link()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df.link()

        # assert
        self.assertTrue(df.path.is_dir())
        self.assertTrue(self.testdir.is_symlink())
        self.assertTrue(df.encrypted_path.is_file())
        self.assertTrue(self.testdir.resolve() == df.path)

    def test_init_update_encrypted_file(self):
        # assume
        decrypted_file = Path(tempfile.mktemp(prefix=f'decrypted_'))
        content = "update"

        self.addCleanup(self.cleanup, decrypted_file)

        # action
        df = state.channel.init(self.testfile, encrypted=True)
        self.testfile.write_text(content)
        old_encrypted_path = df.encrypted_path

        df.update()
        df.decrypt(decrypted_file)

        # assert
        # is file name changed after update
        self.assertFalse(old_encrypted_path == df.encrypted_path)

        # check if updated text in file is present in encrypted file
        self.assertTrue(decrypted_file.read_text() == content)

        self.assertTrue(df.path.is_file())
        self.assertTrue(self.testfile.is_symlink())
        self.assertTrue(df.encrypted_path.is_file())
        self.assertTrue(self.testfile.resolve() == df.path)

    def test_init_update_encrypted_dir(self):
        # assume
        f = self.testdir / 'newfile.txt'
        decrypted_dir = Path(tempfile.mkdtemp(prefix=f'decrypted_'))
        content = "update"

        self.addCleanup(self.cleanup, decrypted_dir)

        # action
        df = state.channel.init(self.testdir, encrypted=True)
        f.write_text(content)
        old_encrypted_path = df.encrypted_path

        df.update()
        df.decrypt(decrypted_dir)

        new_file = decrypted_dir / f.name

        # assert
        # is file name changed after update
        self.assertFalse(old_encrypted_path == df.encrypted_path)

        # check if updated text in file is present in encrypted file
        self.assertTrue(new_file.read_text() == content)

        # is new file present
        self.assertTrue(f.is_file())

        self.assertTrue(df.path.is_dir())
        self.assertTrue(self.testdir.is_symlink())
        self.assertTrue(df.encrypted_path.is_file())
        self.assertTrue(self.testdir.resolve() == df.path)

    def test_init_to_encrypted_to_decrypted_file(self):
        # action
        df = state.channel.init(self.testfile, encrypted=False)

        # assert
        self.assertTrue(df.path.is_file())
        self.assertTrue(self.testfile.resolve() == df.path)
        self.assertTrue(self.testfile.is_symlink())

        # action
        df.to_encrypted(state.encryption.key)

        # re-init channels/dotfiles
        state.channel = get_channel('common', state, create=True, assume_yes=True)
        edf = state.channel.get_dotfile(df.name)

        # try to encrypt again, should not be possible
        with self.assertRaises(MicrodotError):
            edf.to_encrypted(state.encryption.key)

        # assert
        self.assertFalse(edf == None)
        self.assertTrue(edf.is_encrypted)
        self.assertTrue(edf.name == df.name)

        # action
        edf.to_decrypted()

        # re-init channels/dotfiles
        state.channel = get_channel('common', state, create=True, assume_yes=True)
        ddf = state.channel.get_dotfile(df.name)

        # assert
        self.assertFalse(ddf == None)
        self.assertFalse(ddf.is_encrypted)
        self.assertTrue(ddf.name == df.name)
        self.assertTrue(ddf.name == edf.name)

    def test_init_to_encrypted_to_decrypted_dir(self):
        # action
        df = state.channel.init(self.testdir, encrypted=False)

        # assert
        self.assertTrue(df.path.is_dir())
        self.assertTrue(self.testdir.resolve() == df.path)
        self.assertTrue(self.testdir.is_symlink())

        # action
        df.to_encrypted(state.encryption.key)

        # re-init channels/dotfiles
        state.channel = get_channel('common', state, create=True, assume_yes=True)
        edf = state.channel.get_dotfile(df.name)

        # try to encrypt again, should not be possible
        with self.assertRaises(MicrodotError):
            edf.to_encrypted(state.encryption.key)

        # assert
        self.assertFalse(edf == None)
        self.assertTrue(edf.is_encrypted)
        self.assertTrue(edf.name == df.name)

        # action
        edf.to_decrypted()

        # re-init channels/dotfiles
        state.channel = get_channel('common', state, create=True, assume_yes=True)
        ddf = state.channel.get_dotfile(df.name)

        # assert
        self.assertFalse(ddf == None)
        self.assertFalse(ddf.is_encrypted)
        self.assertTrue(ddf.name == df.name)
        self.assertTrue(ddf.name == edf.name)



if __name__ == '__main__':
    unittest.main()
