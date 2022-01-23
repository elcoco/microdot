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
            self.list(merge_file)

            if do_confirm and not confirm(f"Would you like to apply changes to: {dest}?", canceled_msg="Merge canceled"):
                return

            return merge_file



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

    def execute_merge_file(self, file, do_confirm=True):
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
                merge.merge(do_confirm=do_confirm)

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
                 "# After merge the current side will be copied back to the system."]

        dcmp = dircmp(self.current, self.conflict)

        only_current   = self.get_only_current(dcmp)
        only_conflict  = self.get_only_conflict(dcmp)
        common_changed = self.get_common_changed(dcmp)

        for i,f in enumerate(only_current):
            if i == 0: lines.append(f"\n# Exist only on 'current' side.")
            lines.append(f"rm {f}")

        for i,f in enumerate(only_conflict):
            if i == 0: lines.append(f"\n# Exist only on 'conflict' side.")
            p_current = self.current / Path(f).relative_to(self.conflict)
            lines.append(f"mv {f} -> {p_current.absolute()}")

        for i,f in enumerate(common_changed):
            if i == 0: lines.append(f"\n# Exist on both sides but with different content.")
            lines.append(f"merge {f[0]} | {f[1]}")

        merge_file.write_text("\n".join(lines))
        self.edit(merge_file)
        return merge_file

    def merge(self, do_confirm=True):
        dcmp = dircmp(self.current, self.conflict)

        merge_file = self.generate_merge_file()
        self.list(merge_file)

        if confirm("Execute these changes?", canceled_msg="Merge canceled"):
            self.execute_merge_file(merge_file, do_confirm=do_confirm)
        else:
            merge_file.unlink()
            info("merge", "merge", "Merge canceled")
            return

        merge_file.unlink()
        return self.current


def cleanup(items):
    """ Cleanup list of files/dirs """
    for item in items:
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=False, onerror=None)
        else:
            item.unlink()
        debug("cleanup", "removed", item)

def handle_file_conflict(df_current, df_conflict, do_confirm=True):
    """ Go through the full process of handling a file conflict """

    # decrypt current and conflict file to tmp files
    tmp_current  = Path(tempfile.mktemp(prefix=f'current_{df_current.name}_'))
    tmp_conflict = Path(tempfile.mktemp(prefix=f'conflict_{df_current.name}_'))
    df_current.decrypt(dest=tmp_current)
    df_conflict.decrypt(dest=tmp_conflict)

    # perform merge
    merge = MergeFile(tmp_current, tmp_conflict)

    if not (merge_file := merge.merge(dest=df_current.path, do_confirm=do_confirm)):
        info("merge", "merge", "Merge canceled")
        cleanup([tmp_current, tmp_conflict])
        return

    merge.list(merge_file)

    if do_confirm and not confirm(f"Would you like to apply changes to: {df_current.name}?", canceled_msg="Merge canceled"):
        cleanup([tmp_current, tmp_conflict])
        return

    shutil.move(merge_file, df_current.path)
    df_current.update()
    cleanup([tmp_current, tmp_conflict])

def handle_dir_conflict(df_current, df_conflict, do_confirm=True):
    # decrypt current and conflict dirs to tmp dirs
    tmp_current  = Path(tempfile.mkdtemp(prefix=f'current_{df_current.name}_'))
    tmp_conflict = Path(tempfile.mkdtemp(prefix=f'conflict_{df_current.name}_'))
    df_current.decrypt(dest=tmp_current / df_current.name)
    df_conflict.decrypt(dest=tmp_conflict / df_current.name)

    merge = MergeDir(tmp_current, tmp_conflict)
    if not merge.merge(do_confirm=do_confirm):
        cleanup([tmp_current, tmp_conflict])
        info("merge", "merge", "Merge canceled")
        return

    if do_confirm and not confirm(f"Would you like to move all changes to: {df_current.name}?", canceled_msg="Merge canceled"):
        cleanup([tmp_current, tmp_conflict])
        info("merge", "merge", "Merge canceled")
        return

    if (was_linked := df_current.check_symlink()):
        df_current.unlink()

    old_encrypted_path = df_current.encrypted_path

    df_current.encrypt(tmp_current / df_current.name)

    # remove old encrypted file
    old_encrypted_path.unlink()

    if was_linked:
        df_current.link()

    cleanup([tmp_current, tmp_conflict])


def handle_conflict(df_current, df_conflict):
    # check if there are differences between decrypted and last encrypted versions of dotfile.
    # update if necessary.
    if df_current.is_changed():
        df_current.update()

    if df_current.is_file():
        handle_file_conflict(df_current, df_conflict)
    else:
        handle_dir_conflict(df_current, df_conflict)

