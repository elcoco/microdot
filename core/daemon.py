import logging
import datetime
import time
from git import Repo
import git
import threading
from dataclasses import dataclass
from enum import Enum
from subprocess import Popen
from pathlib import Path
from typing import ClassVar

from core import lock
from core.exceptions import MicrodotError

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


class GitPullThread(threading.Thread, Git):
    def __init__(self, git_path, lock, interval, error_interval, cb_on_pull):
        logger.debug("Starting GitPullThread thread")
        threading.Thread.__init__(self)
        try:
            Git.__init__(self, git_path)
        except GitException as e:
            self.error = e
            self.stop()

        self._stopped = False
        self._lock = lock
        self._interval = interval
        self._git_path = git_path
        self._t_last = datetime.datetime.utcnow()
        self._error_interval = error_interval

        # contains error message that will be raised outside of thread
        self.error = None

        self._callback = cb_on_pull

    def stop(self):
        self._stopped = True

    def non_blocking_sleep(self, interval):
        """ Don't block thread stop/joins """
        while (datetime.datetime.utcnow() - self._t_last).total_seconds() < interval:
            if self._stopped:
                break
            time.sleep(1)
        self._t_last = datetime.datetime.utcnow()

    def run(self):
        while not self._stopped:
            with self._lock:
                logger.info(f"Polling remote origin")
                if (msg := self.pull()):
                    msg.notify(error_interval=self._error_interval)

            self.non_blocking_sleep(self._interval)


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

def watch_repo(path, callback=None, pull_interval=10, push_interval=3, error_interval=30):
    # start with clean state
    if lock.is_locked():
        lock.release_lock()

    try:
        g = Git(path)
    except GitException as e:
        raise MicrodotError(e)

    # remote repository watcher, pulls on change
    pull_thread = GitPullThread(path, lock, pull_interval, error_interval, callback)
    pull_thread.start()

    try:
        while True:
            # check pull thread for errors and raise them outside of thread
            if pull_thread.error != None:
                at_exit(pull_thread)
                raise MicrodotError(pull_thread.error)

            with lock:
                if (staged := g.commit()):
                    pass

                    ## run callback on succes to update the encrypted files
                    #try:
                    #    callback([Path(p.a_path) for p in staged if Path(p.a_path).suffix == '.encrypted'])
                    #except MicrodotError as e:
                    #    Message("decrypt", "Failed to decrypt", e, urgency='critical').notify()

                if (msg := g.push()):

                    if staged:
                        msg.body = '\n'.join([parse_diff(l) for l in staged])

                    msg.notify(error_interval=error_interval)

            time.sleep(push_interval)

    except KeyboardInterrupt:
        at_exit(pull_thread)
