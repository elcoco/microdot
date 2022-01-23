
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


