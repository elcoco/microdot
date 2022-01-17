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

from core import lock, status_list
from git import Repo
from core.exceptions import MicrodotError
from core.channel import update_encrypted_from_decrypted, update_decrypted_from_encrypted, get_encrypted_dotfiles

logger = logging.getLogger("microdot")


class GitException(Exception):
    pass


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

def at_exit(thread):
    logger.debug("Stopping GitPullThread")
    thread.stop()
    thread.join()

def parse_diff(item):
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

def sync(path, error_msg_interval):
    # start in a fully synchronised state, unencrypted_data==encrypted_data
    update_encrypted_from_decrypted()

    #for df in get_linked_encrypted_dotfiles(state):
    ##    df.update()
    #for dotfile in get_encrypted_dotfiles(linked=True):
    #    a = dotfile[0]
    #    b = dotfile[1] if len(dotfile) > 1 else None
    #    if status_list.is_in_conflict(a, b):
    #        logger.debug("Skipping conflict")
    #        continue
    #    a.update()

    try:
        g = Git(path)
    except GitException as e:
        raise MicrodotError(e)

    logger.info(f"Pulling remote origin")
    if (msg := g.pull()):
        msg.notify(error_interval=error_msg_interval)

    print(50*'*')

    for dotfile in get_encrypted_dotfiles():
        logger.debug(f"Checking {len(dotfile)} dotfile(s): {dotfile[0].name}")
        a = dotfile[0]
        b = dotfile[1] if len(dotfile) > 1 else None

        try:
            a_name = a.encrypted_path.name
            b_name = b.encrypted_path.name
        except AttributeError:
            pass

        status_list.read_list()

        if status_list.a_is_new(a, b):
            logger.debug(f"SYNC: A is new: {a_name}")
        elif status_list.b_is_new(a, b):
            logger.debug(f"SYNC: B is new: {a_name}")
        elif status_list.is_in_sync(a, b):
            logger.debug("SYNC: We are in sync")
        elif status_list.a_is_newer(a, b):
            logger.debug(f"SYNC: B is newer: {a_name} > {b_name}")
        elif status_list.b_is_newer(a, b):
            logger.debug(f"SYNC: A is newer: {a_name} < {b_name}")
        elif status_list.is_in_conflict(a, b):
            logger.error(f"SYNC: conflict: {a_name} <> {b_name}")
            # choose local and rename other
            # find local by comparing hash(unencrypted data) with hashed(encrypted_path)
            d_hash = a.get_hash(a.path)
            # TODO attach hostname and date for easy identification
            if d_hash == a.hash:
                logger.info(f"Choosing A: {a.encrypted_path.name}")
                b.encrypted_path.rename(b.encrypted_path.parent / (b.encrypted_path.name + '#CONFLICT'))
            elif d_hash == b.hash:
                logger.info(f"Choosing B: {b.encrypted_path.name}")
                a.encrypted_path.rename(a.encrypted_path.parent / (a.encrypted_path.name + '#CONFLICT'))
            else:
                logger.error("Failed to find a resolution")

        else:
            logger.error(f"SYNC: unexpected error: {a_name} - {b_name}")

        status_list.write()
        #status_list.solve(a, b)

    # DONE: after file is deleted by remote, the decrypted file is left on the system
    #      and will start syncin as a normal file so we need to check the status list
    #      for entries with missing files and remove decrypted data if found
    #dotfiles = get_encrypted_dotfiles()
    status_list.check_removed(get_encrypted_dotfiles())
    print(50*'*')

    # TODO in case of conflict, the next update one of the files is considered new


    logger.info(f"Pushing to remote origin")
    if (staged := g.commit()):
        pass

    if (msg := g.push()):
        if staged:
            msg.body = '\n'.join([parse_diff(l) for l in staged])

        msg.notify(error_interval=error_msg_interval)

    # TODO: end in a fully synchronised state, unencrypted_data==encrypted_data


def watch_repo(path, pull_interval=10, push_interval=3, error_interval=30):
    # start with clean state
    push_interval = 5
    if lock.is_locked():
        lock.release_lock()

    try:
        while True:
            with lock:
                sync(path, error_interval)

            time.sleep(push_interval)

    except KeyboardInterrupt:
        pass
