import logging
import datetime
import time
from git import Repo
import git
import threading

from core import lock
from core.exceptions import MicrodotError

# inotify
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, PatternMatchingEventHandler

logger = logging.getLogger("microdot")


class GitException(Exception):
    pass

class Git():
    def __init__(self):
        self._head = None

    def git_init(self, path):
        try:
            self._repo = Repo(path)
        except git.exc.InvalidGitRepositoryError as e:
            raise GitException("Invalid Git repository")

    def commit(self):
        # add all untracked files and all changes
        self._repo.git.add(all=True)

        if (staged := self._repo.index.diff("HEAD")):
            commit = self._repo.index.commit("test commit")
            logger.info(f"Committing {len(staged)} changes: {commit}")
            return commit

    def push(self):
        origin = self._repo.remote(name='origin')

        try:
            pushed = origin.push()
            if len(pushed):
                logger.info(f"Pushed changes, {pushed} :: {len(pushed)}")
                return pushed
            else:
                logger.error("Failed to push changes")

        except git.exc.GitCommandError as e:
            logger.error("Failed to push changes.")
            logger.error(e)

    def pull(self):
        prev_head = self._repo.head.commit
        origin = self._repo.remote(name='origin')
        try:
            pulled = origin.pull()

            if prev_head != self._repo.head.commit:
                logger.info(f"Pulled changes, {pulled}")

        except git.exc.GitCommandError as e:
            logger.error("Failed to pull changes.")
            logger.error(e)


class GitPushEventHandler(FileSystemEventHandler, Git):
    def __init__(self, git_path):
        super().__init__()
        logger.debug("Starting GitPushEventHandler")

        # To not get double events, we pause during processing and check time inbetween events
        self.t_last = datetime.datetime.now()
        self.paused = False

        try:
            self.git_init(git_path)
        except GitException as e:
            self.error = e
            self.paused = True


        self._git_path = git_path

        # holds exception in case of error
        self.error = None

        # this will trigger an initial push
        self.pending_push = True

    def on_modified(self, event):
        if '.git' in event.src_path:
            return

        if self.paused:
            # TODO if a change is made while paused, the changes go unpushed
            return

        if (datetime.datetime.now() - self.t_last) > datetime.timedelta(seconds=1):
            self.paused = True

            with lock:
                logger.info(f"Event detected in {self._git_path}")

                if self.commit():
                    self.pending_push = not self.push()

            self.paused = False
            self.t_last = datetime.datetime.now()


class GitPullThread(threading.Thread, Git):
    def __init__(self, git_path, lock, interval):
        super().__init__()

        try:
            self.git_init(git_path)
        except GitException as e:
            self.error = e
            self.stop()

        self.stopped = False
        self._lock = lock
        self._interval = interval
        self._git_path = git_path
        self.error = None

    def stop(self):
        self.stopped = True

    def run(self):
        logger.debug("Starting GitPullThread thread")

        while not self.stopped:
            with self._lock:
                logger.info(f"Polling remote origin")
                self.pull()

            time.sleep(self._interval)


def at_exit(threads):
    logger.debug("Stopping GitPushEventHandler")
    logger.debug("Stopping GitPullThread")
    for thread in threads:
        thread.stop()
        thread.join()

def watch_repo(path, pull_interval=10):
    if lock.is_locked():
        lock.release_lock()

    # local filesystem watcher, pushes on change
    event_handler = GitPushEventHandler(path)
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    # remote repository watcher, pulls on change
    pull_thread = GitPullThread(path, lock, pull_interval)
    pull_thread.start()

    try:
        while True:
            if event_handler.error != None:
                at_exit([observer, pull_thread])
                raise MicrodotError(event_handler.error)
            if pull_thread.error != None:
                at_exit([observer, pull_thread])
                raise MicrodotError(pull_thread.error)
            if event_handler.pending_push:
                logger.info("Retrying pending push")
                event_handler.commit()
                event_handler.pending_push = not event_handler.push()

            time.sleep(1)
    except KeyboardInterrupt:
        at_exit([observer, pull_thread])
