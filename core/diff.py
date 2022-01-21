import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
import tempfile
import os
import shutil

from core.utils import debug, info, get_hash, get_tar, confirm
from core.exceptions import MicrodotError

logger = logging.getLogger("microdot")


@dataclass
class Patch():
    orig: Path
    patch: Path

    def __post_init__(self):
        self.editor = os.environ.get('EDITOR','vim') 

    def list(self):
        for i,l in enumerate(self.patch.read_text().split('\n')):
            info("patch", "list", f"{str(i).rjust(3)}: {l}")

    def apply(self):
        """ Apply patch to orig

            patch:
                -d DIR  --directory=DIR  Change the working directory to DIR first.
                -p NUM  --strip=NUM      Strip NUM leading components from file names.
                -s  --quiet  --silent    Work silently unless an error occurs.

            returns: True if self.orig is changed
        """
        # TODO use --merge flag for git style 3 way merge
        if self.orig.is_dir():
            cmd = ['patch', f'--directory={str(self.orig.absolute())}', '--strip=3', f'--input={str(self.patch.absolute())}']
        else:
            cmd = ['patch', f'--directory={str(self.orig.parent.absolute())}', '--strip=2', f'--input={str(self.patch.absolute())}']

        debug("patch", "apply", " ".join(cmd))
        md5 = get_hash(self.orig)

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise MicrodotError(f"Failed to apply patch: {cmd}\n{result.stdout.decode()}")

        return md5 != get_hash(self.orig)

    def merge(self):
        """ Merge a patch file into the original file """
        cmd = ['patch', '--merge=diff3', f'--directory={str(self.orig.parent.absolute())}', '--strip=2', f'--input={str(self.patch.absolute())}']

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise MicrodotError(f"Failed to apply patch: {cmd}\n{result.stdout.decode()}")
        print(result.stdout)
        print(result.stderr)

        self.edit(self.orig)


    def cleanup(self):
        # remove temp patch file
        self.patch.unlink()

        if self.orig.is_dir():
            pass
        else:
            self.orig.unlink()

    def vimdiff(self, new):
        """ Edit patch with $EDITOR
            returns: True is self.patch is changed
        """
        debug("patch", "edit", f"{self.orig}")
        md5 = get_hash(self.orig)

        try:
            # check=True raises CalledProcessError on non zero exit code
            cmd = ['vimdiff', str(self.orig.absolute()), str(new.absolute())]
            result = subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(e)
            raise MicrodotError(f"Failed to execute editor: {' '.join(cmd)}")

        return md5 != get_hash(self.orig)

    def edit(self, path=None):
        """ Edit patch with $EDITOR
            returns: True is self.patch is changed
        """
        if not path:
            path=self.patch

        debug("patch", "edit", f"{path}")
        md5 = get_hash(path)

        try:
            # check=True raises CalledProcessError on non zero exit code
            cmd = [self.editor, str(path.absolute())]
            result = subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(e)
            raise MicrodotError(f"Failed to execute editor: {' '.join(cmd)}")

        return md5 != get_hash(path)


class Diff():
    def __init__(self, orig, new):
        self.orig = orig
        self.new = new

    def create(self):
        """ Run diff and generate patch.
            Returns path to tmp patch file. 

            diff:
                -u, -U NUM, --unified[=NUM]   output NUM (default 3) lines of unified context
                -r, --recursive               recursively compare any subdirectories found
                -N, --new-file                treat absent files as empty
        """
        if not self.orig.exists():
            raise MicrodotError(f"File/dir doesn't exist: {self.orig}")
        if not self.new.exists():
            raise MicrodotError(f"File/dir doesn't exist: {self.new}")

        # diff -ruN orig/ new/ > file.patch
        cmd = ['diff', '--recursive', '--unified', '--new-file', str(self.orig.absolute()), str(self.new.absolute())]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 1:
            debug("diff", "create", "is different")
        elif result.returncode == 0:
            debug("diff", "create", "is same")
            return
        else:
            raise MicrodotError(f"Error while running diff command: {' '.join(cmd)}\n{result.stderr.decode()}")

        patch_path = Path(tempfile.mktemp())
        patch_path.write_bytes(result.stdout)
        return Patch(self.orig, patch_path)


def handle_conflict(df_orig, df_conflict):
    debug("diff", "orig path", df_orig.path)
    debug("diff", "conf path", df_conflict.path)

    # TODO start clean
    #dotfile.update()

    tmp_orig     = Path(tempfile.mkdtemp(prefix='original_')) if df_orig.is_dir() else Path(tempfile.mktemp(prefix='original_'))
    tmp_conflict = Path(tempfile.mkdtemp(prefix='conflict_')) if df_conflict.is_dir() else Path(tempfile.mktemp(prefix='conflict_'))

    df_orig.decrypt(dest=tmp_orig)
    df_conflict.decrypt(dest=tmp_conflict)



    d = Diff(tmp_orig, tmp_conflict)
    patch = d.create()
    print("orig", d.orig)
    print("new ", d.new)
    print("patch", patch.patch)

    if not patch:
        return

    if df_orig.is_file():
        if patch.vimdiff(tmp_conflict):
            shutil.move(tmp_orig, df_orig.path)
            df_orig.update()
            info("patch", "patched", tmp_orig)
        else:
            info("patch", "patched", "canceled")
        return

    while True:
        patch.edit()
        patch.list()

        if not confirm(f"Apply patch to {patch.orig}?"):
            return

        try:
            patch.apply()
            break
        except MicrodotError as e:
            logger.error(e)
            if not confirm("Failed to apply patch, would you like to edit the patch again?"):
                return



    print("orig", d.orig)
