import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
import tempfile
import os

from core.utils import debug, info, get_hash
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
            logger.error("Error while running diff command")
            raise MicrodotError("Error while running diff command")

        tmp_file = Path(tempfile.mktemp())
        tmp_file.write_bytes(result.stdout)
        return Patch(self.orig, self.new, tmp_file)
