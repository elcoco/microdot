import logging
import datetime
import time
import git
import threading
from dataclasses import dataclass
from enum import Enum
from subprocess import Popen
from pathlib import Path
from typing import ClassVar

from core import lock
from git import Repo
from core.exceptions import MicrodotError
from core.channel import update_encrypted_from_decrypted, update_decrypted_from_encrypted, get_encrypted_dotfiles
from core.logic import SyncAlgorithm

logger = logging.getLogger("microdot")


class GitException(Exception):
    pass

# TODO error notifications
# DONE separate logic and execution of sync Sync() <> Watch()
# DONE come up with better name for Watch()
# TODO better info/debug messages

@dataclass
class Message():
    """ Message can be returned by Git() """
    sender: str
    summary: str
    body: str = ""
    urgency: str = "normal"
    messages: ClassVar[list] = []
    time: int = 20000

    def __post_init__(self):
        self.dt = datetime.datetime.utcnow()

    def is_error(self):
        return self.urgency == "critical"

    def check_skip(self, seconds):
        """ Skip message under some conditions """
        if not self.is_error():
            return False

        for m in reversed(self.messages):
            if self.sender == m.sender:
                break
        else:
            return False

        if not m.is_error():
            return False

        if (self.dt - m.dt).total_seconds() < seconds:
            return True

    def notify(self, error_interval=None):
        if error_interval and self.check_skip(error_interval):
            return

        self.messages.append(self)

        Popen(["notify-send",
               "--app-name=microdot",
               f"--expire-time={self.time}",
               f"--urgency={self.urgency}",
               self.summary,
               self.body])


class Git():
    """ Git provides all methods to manage a git repository (commit, push, pull etc...)"""
    def __init__(self, path):
        try:
            self._repo = Repo(path)
        except git.exc.InvalidGitRepositoryError as e:
            raise GitException("Invalid Git repository")

    def list_paths(self, root_tree, path=Path(".")):
        for blob in root_tree.blobs:
            yield path / blob.name
        for tree in root_tree.trees:
            yield from self.list_paths(tree, path / tree.name)

    def commit(self):
        # add all untracked files and all changes
        self._repo.git.add(all=True)

        staged = self._repo.index.diff("HEAD")

        if (diff := self._repo.index.diff("HEAD")):
            commit = self._repo.index.commit("test commit")
            logger.info(f"Committing {len(diff)} changes: {commit}")
            return staged

    def has_pending_commits(self):
        branch  = self._repo.active_branch
        commits = list(self._repo.iter_commits(f"{branch}@{{u}}..{branch}"))
        return commits

    def push(self):
        origin  = self._repo.remote(name='origin')

        if not (commits := self.has_pending_commits()):
            return

        logger.info(f"Pushing {len(commits)} commit(s)")
        try:
            info = origin.push()[0]
        except git.exc.GitCommandError as e:
            logger.error(e)
            return Message("push", "Failed to push changes", e.stderr.strip(), urgency="critical")

        if info.flags & info.ERROR:
            if info.flags & info.REJECTED:
                msg = "Push is rejected"
            elif info.flags & info.REMOTE_REJECTED:
                msg = "Push is remote rejected"
            elif info.flags & info.REMOTE_FAILURE:
                msg = "Push failed remote"
            else:
                msg = "Push failed"
            logger.error(msg)
            return Message("push", msg, urgency="critical")

        logger.info(f"Push done: {info.summary.strip()}")
        return Message("push", f"Pushed {len(commits)} commit(s)")

    def pull(self):
        prev_head = self._repo.head.commit
        origin = self._repo.remote(name='origin')
        try:
            pulled = origin.pull()

            if prev_head != self._repo.head.commit:
                logger.info(f"Pulled changes, {pulled}")
                return Message("pull", f"Pulled changes, {pulled}")

        except git.exc.GitCommandError as e:
            logger.error("Failed to pull changes")
            logger.error(e.stderr.strip())
            return Message("pull", "Failed to pull changes", e.stderr.strip(), urgency="critical")


class Sync(SyncAlgorithm):
    def __init__(self, path, interval=3, error_msg_interval=30):
        super().__init__()

        try:
            self.g = Git(path)
        except GitException as e:
            raise MicrodotError(e)

        if lock.is_locked():
            lock.release_lock()

        self.interval = interval
        self.error_msg_interval = error_msg_interval

    def parse_diff(self, item):
        """ Parse diff object and construct a message """
        match item.change_type:
            case 'A':
                msg = f"deleted: {item.a_path}"
            case 'D':
                msg = f"new: {item.a_path}"
            case 'M':
                msg = f"modified: {item.a_path}"
            case 'R':
                msg = f"renamed: {item.a_path} -> {item.b_path}"
            case _:
                msg = "type {item.change_type}: {item.a_path}"
        return msg

    def pre_sync(self):
        # start in a fully synchronised state, unencrypted_data==encrypted_data
        update_encrypted_from_decrypted()

        logger.info(f"Pulling remote data")
        if (msg := self.g.pull()):
            msg.notify(error_interval=self.error_msg_interval)

    def sync(self):
        self.pre_sync()

        print(50*'*')

        for dotfile in get_encrypted_dotfiles():

            a = dotfile[0]
            b = dotfile[1] if len(dotfile) > 1 else None
            a_path = dotfile[0].encrypted_path
            b_path = dotfile[1].encrypted_path if len(dotfile) > 1 else None

            logger.debug(f"Checking {len(dotfile)} dotfile(s): {dotfile[0].name}")

            if self.a_is_new(a_path, b_path):
                if a.check_symlink():
                    a.decrypt()

            elif self.b_is_new(a_path, b_path):
                if b.check_symlink():
                    b.decrypt()

            elif self.is_in_sync(a_path, b_path):
                logger.debug("SYNC: in sync")

            elif self.a_is_newer(a_path, b_path):
                a.encrypted_path.unlink()
                if a.check_symlink():
                    b.decrypt()

            elif self.b_is_newer(a_path, b_path):
                b.encrypted_path.unlink()
                if a.check_symlink():
                    a.decrypt()

            elif (df := self.is_in_conflict(a_path, b_path)):
                df.rename(df.parent / (df.name + '#CONFLICT'))

            else:
                logger.error(f"SYNC: unexpected error: {a.name} - {b.name}")

        # DONE: after file is deleted by remote, the decrypted file is left on the system
        #       and will start syncin as a normal file so we need to check the status list
        #       for entries that don't have corresponding data on filesystem and remove
        #       this decrypted data if found

        # flatten list
        dotfiles = get_encrypted_dotfiles()
        dotfiles = sum(dotfiles, [])
        self.check_removed(dotfiles)
        print(50*'*')
        self.post_sync()

    def post_sync(self):
        logger.info(f"Pushing to remote origin")
        if (staged := self.g.commit()):
            pass

        if (msg := self.g.push()):
            if staged:
                msg.body = '\n'.join([self.parse_diff(l) for l in staged])

            msg.notify(error_interval=self.error_msg_interval)

    def watch_repo(self):
        # start with clean state
        push_interval = 5

        try:
            while True:
                with lock:
                    self.sync()

                time.sleep(self.interval)

        except KeyboardInterrupt:
            pass
