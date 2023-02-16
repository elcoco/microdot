import logging
import datetime
import time
from dataclasses import dataclass
from subprocess import Popen
from pathlib import Path
from typing import ClassVar

from core import lock
from core import CONFLICT_EXT, GIT_COMMIT_MSG
from core.exceptions import MicrodotError, MDGitRepoError
from core.channel import update_encrypted_from_decrypted, get_encrypted_dotfiles
from core.logic import SyncAlgorithm
from core.utils import debug, info, get_hash

import git
from git import Repo

logger = logging.getLogger("microdot")


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
            # TODO needs unittest
            raise MDGitRepoError(f"Invalid Git repository: {path}")

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
            commit = self._repo.index.commit(GIT_COMMIT_MSG)
            debug('git', 'commit', f'{len(diff)} changes: {commit}')

            for l in [self.parse_diff(l) for l in staged]:
                info('git', 'commit', l)

            return [self.parse_diff(l) for l in staged]

    def has_pending_commits(self):
        branch  = self._repo.active_branch
        commits = list(self._repo.iter_commits(f"{branch}@{{u}}..{branch}"))
        return commits

    def push(self):
        origin  = self._repo.remote(name='origin')

        if not (commits := self.has_pending_commits()):
            return

        try:
            pinfo = origin.push()[0]
        except git.exc.GitCommandError as e:
            logger.error(e)
            return Message("push", "Failed to push changes", e.stderr.strip(), urgency="critical")

        if pinfo.flags & pinfo.ERROR:
            if pinfo.flags & pinfo.REJECTED:
                msg = "Push is rejected"
            elif pinfo.flags & pinfo.REMOTE_REJECTED:
                msg = "Push is remote rejected"
            elif pinfo.flags & pinfo.REMOTE_FAILURE:
                msg = "Push failed remote"
            else:
                msg = "Push failed"
            logger.error(msg)
            return Message("push", msg, urgency="critical")

        info('git', 'push', f'{len(commits)} commit(s): {pinfo.summary.strip()}')
        return Message("push", f"Pushed {len(commits)} commit(s)")

    def pull(self):
        debug("git", "pull", "pulling remote data")
        prev_head = self._repo.head.commit
        origin = self._repo.remote(name='origin')

        try:
            pulled = origin.pull()

            if prev_head != self._repo.head.commit:
                msg =  Message("pull", f"Pulled changes")
                for d in self._repo.index.diff(prev_head):
                    msg.body += f"{self.parse_diff(d)}\n"
                    info('git', 'pull', self.parse_diff(d))
                return msg

        except git.exc.GitCommandError as e:
            logger.error("Failed to pull changes")
            logger.error(e.stderr.strip())
            return Message("pull", "Failed to pull changes", e.stderr.strip(), urgency="critical")


class Sync(SyncAlgorithm):
    def __init__(self, path, interval=3, error_msg_interval=30, use_git=True):
        super().__init__()

        self.dotfiles_dir = path

        self.use_git = use_git
        if use_git:
            self.init_git()

        if lock.is_locked():
            lock.release_lock()

        self.interval = interval
        self.error_msg_interval = error_msg_interval

    def init_git(self):
        try:
            self.g = Git(self.dotfiles_dir)
        except MDGitRepoError as e:
            raise MicrodotError(e)

    def pre_sync(self):
        # start in a fully synchronised state, unencrypted_data==encrypted_data
        update_encrypted_from_decrypted()

        if (msg := self.g.pull()):
            msg.notify(error_interval=self.error_msg_interval)

    def get_conflict_name(self, path):
        return f"{path}{CONFLICT_EXT}"

    def sync(self):
        if not self.use_git:
            update_encrypted_from_decrypted()
            return

        self.pre_sync()

        for dotfile in get_encrypted_dotfiles(grouped=True):
            a = dotfile[0]
            b = dotfile[1] if len(dotfile) > 1 else None
            a_path = dotfile[0].encrypted_path
            b_path = dotfile[1].encrypted_path if len(dotfile) > 1 else None

            if self.a_is_new(a_path, b_path):
                if a.check_symlink():
                    a.decrypt()

            elif self.b_is_new(a_path, b_path):
                if b.check_symlink():
                    b.decrypt()

            elif self.is_in_sync(a_path, b_path):
                pass

            elif (df := self.is_in_conflict(a_path, b_path)):
                d_hash = get_hash(a.path)

                if d_hash == a.hash:
                    info('sync', 'conflict', f"Choosing A: {a.encrypted_path.name}")
                    rename_path = b_path.parent / self.get_conflict_name(b_path.name)
                    b_path.rename(rename_path)
                    self.add(a_path)
                    info("sync", "rename", rename_path.name)

                elif d_hash == b.hash:
                    info('sync', 'conflict', f"Choosing B: {b.encrypted_path.name}")
                    rename_path = a_path.parent / self.get_conflict_name(a_path.name)
                    a_path.rename(rename_path)
                    self.add(b_path)
                    info("sync", "rename", rename_path.name)

                else:
                    logger.error("Failed to find a resolution")
            else:
                logger.error(f"SYNC: unexpected error: {a.name} - {b.name}")

        # DONE: after file is deleted by remote, the decrypted file is left on the system
        #       and will start syncin as a normal file so we need to check the status list
        #       for entries that don't have corresponding data on filesystem and remove
        #       this decrypted data if found

        dotfiles = get_encrypted_dotfiles()
        self.check_removed(dotfiles)

        self.post_sync()

    def post_sync(self):
        # TODO unpushed commits won't show up in notification because it only
        #      shows the current commit

        #if not (staged := self.g.commit()):
        #    return
        staged = self.g.commit()

        if (msg := self.g.push()):
            if staged:
                msg.body = '\n'.join(staged)
            msg.notify(error_interval=self.error_msg_interval)

    def watch_repo(self):
        try:
            while True:
                with lock:
                    self.sync()

                time.sleep(self.interval)

        except KeyboardInterrupt:
            pass
