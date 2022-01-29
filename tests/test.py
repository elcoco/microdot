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
from core.sync import Sync

logger = logging.getLogger("microdot")

#logger.setLevel(logging.DEBUG)

# TODO try to init a file in a managed dotfiles dir

class TestBase(unittest.TestCase):
    def setUp(self):
        state.core.dotfiles_dir = Path(tempfile.mkdtemp(prefix=f'dotfiles_'))
        state.channel = get_channel('common', state, create=True, assume_yes=True)

        self.testdir1 = self.create_dir(Path.home() / '.config/testdir1')
        self.testdir2 = self.create_dir(Path.home() / '.config/testdir2')

        self.testfile1 = Path.home() / '.config/dotfile1.txt'
        self.testfile1.write_text("bevers zijn awesome")

        self.testfile2 = Path.home() / '.config/dotfile2.txt'
        self.testfile2.write_text("bevers zijn zeer awesome")

        self.addCleanup(self.cleanup, state.core.dotfiles_dir)
        self.addCleanup(self.cleanup, self.testdir1)
        self.addCleanup(self.cleanup, self.testdir2)
        self.addCleanup(self.cleanup, self.testfile1)
        self.addCleanup(self.cleanup, self.testfile2)

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


class TestSync(TestBase):
    def test_sync_without_git(self):
        # assume
        f = self.testdir1 / 'newfile.txt'
        decrypted_dir = Path(tempfile.mkdtemp(prefix=f'decrypted_'))
        content = "update"

        self.addCleanup(self.cleanup, decrypted_dir)

        # action
        df = state.channel.init(self.testdir1, encrypted=True)

        old_encrypted_path = df.encrypted_path
        f.write_text(content)

        s = Sync(state.core.dotfiles_dir,
                 state.git.interval,
                 state.notifications.error_interval,
                 use_git=False)
        # TODO finnish this

    #def test_update_encrypted_dir(self):
    #    print(">>> Testing sync")
    #    # assume
    #    f = self.testdir1 / 'newfile.txt'
    #    decrypted_dir = Path(tempfile.mkdtemp(prefix=f'decrypted_'))
    #    content = "update"

    #    self.addCleanup(self.cleanup, decrypted_dir)

    #    # init original version
    #    df_A = state.channel.init(self.testdir1, encrypted=True)

    #    f.write_text(content)
    #    old_encrypted_path = df_A.encrypted_path

    #    s = Sync(state.core.dotfiles_dir,
    #             state.git.interval,
    #             state.notifications.error_interval,
    #             use_git=state.do_use_git)
    #    s.sync()

    #    return
    #    df.decrypt(decrypted_dir)

    #    new_file = decrypted_dir / f.name

    #    # assert
    #    # is file name changed after update
    #    self.assertFalse(old_encrypted_path == df.encrypted_path)

    #    # check if updated text in file is present in encrypted file
    #    self.assertTrue(new_file.read_text() == content)

    #    # is new file present
    #    self.assertTrue(f.is_file())

    #    self.assertTrue(df.path.is_dir())
    #    self.assertTrue(self.testdir1.is_symlink())
    #    self.assertTrue(df.encrypted_path.is_file())
    #    self.assertTrue(self.testdir1.resolve() == df.path)

    def test_local_is_newer(self):
        pass


class TestLinkUnlink(TestBase):
    def test_link_unlink(self):
        # action do init
        df_d1 = state.channel.init(self.testdir1, encrypted=True)
        df_d2 = state.channel.init(self.testdir2, encrypted=False)
        df_f1 = state.channel.init(self.testfile1, encrypted=True)
        df_f2 = state.channel.init(self.testfile2, encrypted=False)

        # assert initiated
        self.assertTrue(df_d1.path.is_dir())
        self.assertTrue(self.testdir1.is_symlink())
        self.assertTrue(df_d1.encrypted_path.is_file())
        self.assertTrue(self.testdir1.resolve() == df_d1.path)

        self.assertTrue(df_d2.path.is_dir())
        self.assertTrue(self.testdir2.is_symlink())
        self.assertTrue(self.testdir2.resolve() == df_d2.path)

        self.assertTrue(df_f1.path.is_file())
        self.assertTrue(self.testfile1.is_symlink())
        self.assertTrue(df_f1.encrypted_path.is_file())
        self.assertTrue(self.testfile1.resolve() == df_f1.path)

        self.assertTrue(df_f2.path.is_file())
        self.assertTrue(self.testfile2.is_symlink())
        self.assertTrue(self.testfile2.resolve() == df_f2.path)

        # do unlink
        df_d1.unlink()
        df_d2.unlink()
        df_f1.unlink()
        df_f2.unlink()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df_d1.unlink()
            df_d2.unlink()
            df_f1.unlink()
            df_f2.unlink()

        # assert unlinked state
        self.assertFalse(df_d1.path.exists())
        self.assertFalse(self.testdir1.is_symlink())
        self.assertTrue(df_d1.encrypted_path.is_file())

        self.assertTrue(df_d2.path.exists())
        self.assertFalse(self.testdir2.is_symlink())

        self.assertFalse(df_f1.path.exists())
        self.assertFalse(self.testfile1.is_symlink())
        self.assertTrue(df_f1.encrypted_path.is_file())

        self.assertTrue(df_f2.path.exists())
        self.assertFalse(self.testfile2.is_symlink())

        # do link
        df_d1.link()
        df_d2.link()
        df_f1.link()
        df_f2.link()

        # linking twice should raise an error
        with self.assertRaises(MicrodotError):
            df_d1.link()
            df_d2.link()
            df_f1.link()
            df_f2.link()

        # assert linked state
        self.assertTrue(df_d1.path.is_dir())
        self.assertTrue(self.testdir1.is_symlink())
        self.assertTrue(df_d1.encrypted_path.is_file())
        self.assertTrue(self.testdir1.resolve() == df_d1.path)

        self.assertTrue(df_d2.path.is_dir())
        self.assertTrue(self.testdir2.is_symlink())
        self.assertTrue(self.testdir2.resolve() == df_d2.path)

        self.assertTrue(df_f1.path.is_file())
        self.assertTrue(self.testfile1.is_symlink())
        self.assertTrue(df_f1.encrypted_path.is_file())
        self.assertTrue(self.testfile1.resolve() == df_f1.path)

        self.assertTrue(df_f2.path.is_file())
        self.assertTrue(self.testfile2.is_symlink())
        self.assertTrue(self.testfile2.resolve() == df_f2.path)


class TestShitInput(TestBase):
    def test_impossible_input(self):
        df = state.channel.init(self.testfile1, encrypted=False)
        df.unlink()

        # re-init channels/dotfiles
        state.channel = get_channel('common', state, create=True, assume_yes=True)

        # try to init an already existing file
        self.testfile1.write_text("second attempt")
        with self.assertRaises(MicrodotError):
            state.channel.init(self.testfile1, encrypted=False)

        # try to init a link
        l = Path.home() / 'xxxtestlink'
        l.symlink_to(self.testfile1)
        self.addCleanup(self.cleanup, l)

        with self.assertRaises(MicrodotError):
            state.channel.init(l, encrypted=False)

    def test_init_sanity_check(self):
        p = Path('/tmp/testfile.txt')
        p.write_text('test')
        self.addCleanup(self.cleanup, p)

        # path not in homedir
        with self.assertRaises(MicrodotError):
            df = state.channel.init(p, encrypted=False)

        p2 = state.core.dotfiles_dir / 'xxxxxx.txt'
        p2.write_text('test')
        self.addCleanup(self.cleanup, p2)

        # try to init a path inside an already managed dotfiles dir
        with self.assertRaises(MicrodotError):
            df = state.channel.init(p2, encrypted=False)


    def test_non_existing_things(self):
        with self.subTest():
            # check that non existing channel is created when requested
            state.channel = get_channel('non_existing', state, create=True, assume_yes=True)
            self.assertTrue((state.core.dotfiles_dir / 'non_existing').is_dir())

        with self.subTest():
            # try to get non existing dotfile
            with self.assertRaises(MicrodotError):
                state.channel.get_dotfile("non_existing")

        with self.subTest():
            # try to get non existing encrypted dotfile
            with self.assertRaises(MicrodotError):
                state.channel.get_encrypted_dotfile("non_existing")

        with self.subTest():
            # try to init non existing files
            with self.assertRaises(MicrodotError):
                state.channel.init(Path("non_existing"), encrypted=False)

        with self.subTest():
            # try to init non existing encrypted files
            with self.assertRaises(MicrodotError):
                state.channel.init(Path("non_existing"), encrypted=True)


class TestEncryptDecrypt(TestBase):
    def test_to_encrypted_to_decrypted_file(self):
        # action
        df = state.channel.init(self.testfile1, encrypted=False)

        # assert
        self.assertTrue(df.path.is_file())
        self.assertTrue(self.testfile1.resolve() == df.path)
        self.assertTrue(self.testfile1.is_symlink())

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

    def test_to_encrypted_to_decrypted_dir(self):
        # action
        df = state.channel.init(self.testdir1, encrypted=False)

        # assert
        self.assertTrue(df.path.is_dir())
        self.assertTrue(self.testdir1.resolve() == df.path)
        self.assertTrue(self.testdir1.is_symlink())

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


class TestInit(TestBase):
    def test_init_update_encrypted_file(self):
        # assume
        decrypted_file = Path(tempfile.mktemp(prefix=f'decrypted_'))
        content = "update"

        self.addCleanup(self.cleanup, decrypted_file)

        # action
        df = state.channel.init(self.testfile1, encrypted=True)
        self.testfile1.write_text(content)
        old_encrypted_path = df.encrypted_path

        df.update()
        df.decrypt(decrypted_file)

        # assert
        # is file name changed after update
        self.assertFalse(old_encrypted_path == df.encrypted_path)

        # check if updated text in file is present in encrypted file
        self.assertTrue(decrypted_file.read_text() == content)

        self.assertTrue(df.path.is_file())
        self.assertTrue(self.testfile1.is_symlink())
        self.assertTrue(df.encrypted_path.is_file())
        self.assertTrue(self.testfile1.resolve() == df.path)


if __name__ == '__main__':
    unittest.main()
