import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
import tempfile
import os
import shutil
from typing import Optional
from filecmp import dircmp

from core.utils import debug, info, get_hash, get_tar, confirm
from core.exceptions import MicrodotError

logger = logging.getLogger("microdot")

class MergeError(Exception):
    pass


@dataclass
class Patch():
    current: Path
    patch: Path

    def __post_init__(self):
        self.editor = os.environ.get('EDITOR','vim') 

    def list(self):
        for i,l in enumerate(self.patch.read_text().split('\n')):
            info("patch", "list", f"{str(i).rjust(3)}: {l}")

    def apply(self):
        """ Apply patch to current

            patch:
                -d DIR  --directory=DIR  Change the working directory to DIR first.
                -p NUM  --strip=NUM      Strip NUM leading components from file names.
                -s  --quiet  --silent    Work silently unless an error occurs.

            returns: True if self.current is changed
        """
        # TODO use --merge flag for git style 3 way merge
        if self.current.is_dir():
            cmd = ['patch', f'--directory={str(self.current.absolute())}', '--strip=3', f'--input={str(self.patch.absolute())}']
        else:
            cmd = ['patch', f'--directory={str(self.current.parent.absolute())}', '--strip=2', f'--input={str(self.patch.absolute())}']

        debug("patch", "apply", " ".join(cmd))
        md5 = get_hash(self.current)

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise MicrodotError(f"Failed to apply patch: {cmd}\n{result.stdout.decode()}")

        return md5 != get_hash(self.current)

    def merge(self):
        """ Merge a patch file into the current file

            when providing an empty file as a common ancestor we get a nice merge file that can be edited manually
            this writes to <current-version>
            using the -p switch writes to stdout instead of <current-version>
            git merge-file -p <current-version> <common-ancestor> <other-version>

            # use -L to give labels to files
            git merge-file -L current -L base -L conflicted -p file1.txt file.diff file2.txt
        """
        cmd = ['patch', '--merge=diff3', f'--directory={str(self.current.parent.absolute())}', '--strip=2', f'--input={str(self.patch.absolute())}']

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise MicrodotError(f"Failed to apply patch: {cmd}\n{result.stdout.decode()}")
        print(result.stdout)
        print(result.stderr)

        self.edit(self.current)


    def cleanup(self):
        # remove temp patch file
        self.patch.unlink()

        if self.current.is_dir():
            pass
        else:
            self.current.unlink()

    def vimdiff(self, conflict):
        """ Edit patch with $EDITOR
            returns: True is self.patch is changed
        """
        debug("patch", "edit", f"{self.current}")
        md5 = get_hash(self.current)

        try:
            # check=True raises CalledProcessError on non zero exit code
            cmd = ['vimdiff', str(self.current.absolute()), str(conflict.absolute())]
            result = subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(e)
            raise MicrodotError(f"Failed to execute editor: {' '.join(cmd)}")

        return md5 != get_hash(self.current)

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
    def __init__(self, current, conflict):
        self.current = current
        self.conflict = conflict

    def create(self):
        """ Run diff and generate patch.
            Returns path to tmp patch file. 

            diff:
                -u, -U NUM, --unified[=NUM]   output NUM (default 3) lines of unified context
                -r, --recursive               recursively compare any subdirectories found
                -N, --new-file                treat absent files as empty
        """
        if not self.current.exists():
            raise MicrodotError(f"File/dir doesn't exist: {self.current}")
        if not self.conflict.exists():
            raise MicrodotError(f"File/dir doesn't exist: {self.conflict}")

        # diff -ruN current/ conflict/ > file.patch
        cmd = ['diff', '--recursive', '--unified', '--new-file', str(self.current.absolute()), str(self.conflict.absolute())]

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
        return Patch(self.current, patch_path)


@dataclass
class MergeBaseClass():
    current: Path
    conflict: Path

    def __post_init__(self):
        self.editor = os.environ.get('EDITOR','vim') 

    def edit(self, path=None):
        """ Edit patch with $EDITOR
            returns: True is self.patch is changed
        """
        if not path:
            path=self.current

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

    def list(self, path=None):
        if not path:
            path = self.current
        for i,l in enumerate(path.read_text().split('\n'), start=1):
            info("patch", "list", f"{str(i).rjust(3)}: {l}")


@dataclass
class MergeFile(MergeBaseClass):
    def create_merge_file(self):
        """ Do a 3 way merge
            when providing an empty file as a common ancestor we get a nice merge file that can be edited manually
            this writes to CURRENT
            using the -p switch writes to stdout instead of CURRENT
            git merge-file -p CURRENT EMPTY_BASE CONFLICT

            # use -L to give labels to files
            git merge-file -L current -L base -L conflict -p CURRENT EMPTY_BASE CONFLICT

            git merge-file exits with exitcode<0 on error, and amount of conflicts on success

        """
        # copy current path to a tmp file
        merge_file = Path(tempfile.mktemp(prefix=f'{self.current.name}'))
        shutil.copy(self.current, merge_file)

        tmp_empty = Path(tempfile.mktemp(prefix='empty_'))
        tmp_empty.write_text('')

        cmd = ['git', 'merge-file', '-L', 'current', '-L', 'empty', '-L', 'conflict', str(merge_file.absolute()), str(tmp_empty.absolute()), str(self.conflict.absolute())]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode < 0:
            raise MicrodotError(f"Failed to merge: {' '.join(cmd)}\n{result.stdout.decode()}\n{result.stderr.decode()}")

        tmp_empty.unlink()
        return merge_file

    def merge(self, dest=None, do_confirm=True):
        if dest == None:
            dest = self.current

        merge_file = self.create_merge_file()

        if self.edit(merge_file):
            info("merge", "merge", f"{self.current}")
            self.list(merge_file)
            if do_confirm and not confirm(f"Would you like to apply changes to: {dest}?"):
                return

            return shutil.move(merge_file, dest)
        else:
            info("merge", "merge", "canceled")


@dataclass
class MergeDir(MergeBaseClass):
    def get_common_changed(self, dcmp, lst=None):
        """ Return recursive list of files/dirs that exist on both sides but have different content """
        if lst == None:
            lst = []
        for name in dcmp.diff_files:
            #print(f"diff: {name} in {dcmp.left} and {dcmp.right}")
            lst.append([f"{dcmp.left}/{name}", f"{dcmp.right}/{name}"])
        for sub_dcmp in dcmp.subdirs.values():
            self.get_common_changed(sub_dcmp, lst)
        return lst

    def get_only_current(self, dcmp, lst=None):
        """ Return recursive list of files/dirs that only exist on current side """
        if lst == None:
            lst = []
        for name in dcmp.left_only:
            lst.append(f"{dcmp.left}/{name}")
        for sub_dcmp in dcmp.subdirs.values():
            self.get_only_current(sub_dcmp, lst)
        return lst

    def get_only_conflict(self, dcmp, lst=None):
        """ Return recursive list of files/dirs that only exist on conflict side """
        if lst == None:
            lst = []
        for name in dcmp.right_only:
            lst.append(f"{dcmp.right}/{name}")
        for sub_dcmp in dcmp.subdirs.values():
            self.get_only_conflict(sub_dcmp, lst)
        return lst

    def do_remove(self, path):
        """ Remove file or directory """
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=False, onerror=None)
            info("merge", "remove_dir", path)
        else:
            path.unlink()
            info("merge", "remove_file", path)

    def check_line(self, line, indices, relative_to='/tmp'):
        """ Do a sanity check on the input.
            File must split in the specified indices.
            File must be relative to path specified by relative_to """
        ret = []
        for index in indices:
            try:
                ret.append(Path(line.split()[index]))
            except IndexError:
                raise MicrodotError(f"Failed to parse line: {line}")

        for path in ret:
            try:
                path.relative_to(relative_to)
            except ValueError:
                raise MicrodotError(f"Abort: unsafe path {path}, not relative to {relative_to}")

        return ret

    def execute_merge_file(self, file):
        """ Parse the file/dir merge file we created and execute commands """
        for i,l in enumerate(file.read_text().split('\n'), start=1):
            l = l.strip()
            if l.startswith("#"):
                continue

            elif l.startswith("rm"):
                path = self.check_line(l, [1])[0]
                self.do_remove(path)

            elif l.startswith("mv"):
                conflict, current = self.check_line(l, [1,3])
                shutil.move(conflict, current)
                info("merge", "move", f"{conflict.absolute()} -> {current.absolute()}")

            elif l.startswith("merge"):
                current, conflict = self.check_line(l, [1,3])
                merge = MergeFile(current, conflict)
                merge.merge()

            else:
                debug("merge", "parse", f"skip line: {l}")

    def generate_merge_file(self):
        """ Create a file with all changes that can be parsed and executed later """
        merge_file = Path(tempfile.mktemp(prefix='dir_merge_'))
        lines = ["# Actions in this file will be executed.",
                 "# If you don't want to execute a line, just delete it.\n#",
                 "#   current  = side that is in use currently.",
                 "#   conflict = side that is extracted from conflict file.\n#",
                 "# Unchanged files/dirs on 'current' will be copied or removed to match 'conflict'.",
                 "# Changed files will be merged manually one by one.\n#",
                 "# After merge the current side will be copied back to the system.\n"]

        dcmp = dircmp(self.current, self.conflict)

        for f in self.get_only_current(dcmp):
            lines.append(f"# Exists only on 'current' side.\nrm {f}\n")

        for f in self.get_only_conflict(dcmp):
            p_current = self.current / Path(f).relative_to(self.conflict)
            lines.append(f"# Exists only on 'conflict' side.\nmv {f} -> {p_current.absolute()}\n")

        for f in self.get_common_changed(dcmp):
            lines.append(f"# Exists on both sides, but with different content.\nmerge {f[0]} != {f[1]}\n")

        merge_file.write_text("\n".join(lines))
        self.edit(merge_file)
        return merge_file

    def merge(self):
        dcmp = dircmp(self.current, self.conflict)

        merge_file = self.generate_merge_file()
        self.list(merge_file)

        if confirm("Execute these changes?"):
            self.execute_merge_file(merge_file)

        merge_file.unlink()


def handle_conflict(df_current, df_conflict):
    # TODO start clean
    #dotfile.update()

    tmp_current     = Path(tempfile.mkdtemp(prefix=f'current_{df_current.name}_')) if df_current.is_dir() else Path(tempfile.mktemp(prefix=f'current_{df_current.name}_'))
    tmp_conflict = Path(tempfile.mkdtemp(prefix=f'conflict_{df_current.name}_')) if df_conflict.is_dir() else Path(tempfile.mktemp(prefix=f'conflict_{df_current.name}_'))

    df_current.decrypt(dest=tmp_current)
    df_conflict.decrypt(dest=tmp_conflict)

    if df_current.is_file():
        try:
            merge = MergeFile(tmp_current, tmp_conflict)
            merge.merge(dest=df_current.path)
            df_current.update()
            return True
        except MicrodotError as e:
            logger.error(e)

    else:
        try:
            merge = MergeDir(tmp_current, tmp_conflict)
            merge.merge()
            return True
        except MicrodotError as e:
            logger.error(e)

    info("patch", "patch", "canceled")




