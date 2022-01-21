import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
import tempfile
import os

from core.utils import debug, info, get_hash, get_tar, confirm
from core.exceptions import MicrodotError

logger = logging.getLogger("microdot")


@dataclass
class Patch():
    orig: Path
    new: Path
    patch: Path

    def __post_init__(self):
        self.editor = os.environ.get('EDITOR','vim') 

    def list(self):
        for l in self.patch.read_text().split('\n'):
            info("patch", "list", l)

    def apply(self):
        """ Apply patch to orig

            patch:
                -p NUM  --strip=NUM    Strip NUM leading components from file names.
                -s  --quiet  --silent  Work silently unless an error occurs.

            returns: True if self.orig is changed
        """
        cmd = ['patch', '--silent', '--strip=0', str(self.orig.absolute()), str(self.patch.absolute())]
        debug("patch", "apply", " ".join(cmd))
        md5 = get_hash(self.orig)

        try:
            # check=True raises CalledProcessError on non zero exit code
            result = subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            raise MicrodotError(f"Failed to execute patch: {cmd}")

        return md5 != get_hash(self.patch)

    def cleanup(self):
        # remove temp patch file
        self.patch.unlink()

        if self.orig.is_dir():
            pass
        else:
            self.orig.unlink()

        if self.new.is_dir():
            pass
        else:
            self.new.unlink()

    def edit(self):
        """ Edit patch with $EDITOR
            returns: True is self.patch is changed
        """
        debug("patch", "edit", f"{self.patch}")
        md5 = get_hash(self.patch)

        try:
            # check=True raises CalledProcessError on non zero exit code
            cmd = [self.editor, str(self.patch.absolute())]
            result = subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(e)
            raise MicrodotError(f"Failed to execute editor: {cmd}")

        return md5 != get_hash(self.patch)


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

        tmp_file = Path(tempfile.mktemp())
        tmp_file.write_bytes(result.stdout)
        return Patch(self.orig, self.new, tmp_file)


def handle_conflict(df_orig, df_conflict):
    debug("diff", "orig path", df_orig.path)
    debug("diff", "conf path", df_conflict.path)

    # TODO start clean
    #dotfile.update()

    tmp_orig     = Path(tempfile.mkdtemp()) if df_orig.is_dir() else Path(tempfile.mktemp())
    tmp_conflict = Path(tempfile.mkdtemp()) if df_conflict.is_dir() else Path(tempfile.mktemp())

    df_orig.decrypt(dest=tmp_orig)
    df_conflict.decrypt(dest=tmp_conflict)


    d = Diff(tmp_orig, tmp_conflict)
    patch = d.create()

    if not patch:
        return

    while True:
        patch.edit()
        patch.list()

        if not confirm(f"Apply patch to {patch.orig}?"):
            return

        try:
            patch.apply()
            for l in patch.orig.read_text().split('\n'):
                print(l)
            break
        except MicrodotError as e:
            logger.error(e)
            if not confirm("Failed to apply patch, would you like to edit the patch again?"):
                return



