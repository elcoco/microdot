#!/usr/bin/env python3

# DONE don't show git dir as channel
# TODO make blacklist configurable
# TODO when linking or unlinking all, give a list of files before proceeding
# TODO when linking or unlinking all, filter file list
# TODO add option to stop daemon
# DONE when internet is gone, gitpush will just skip. when internet reconnects, the push is not triggered again
# TODO when a linked encrypted file is updated when using watch, update decrypted file
# TODO when answered no when creating common channel, program crashes`

# TODO when a decrypted file is edited it needs to sync with the encrypted file
#      or changes get lost
#      When linking/init encrypted file, a warning needs to display about non running daemons

# TODO encryption only works for files now

# TODO add encrypt option to --link switch so we can encrypt an already initialized file
#      ask the user to remove file from git cache

# TODO one way to solve dir encryption problem is to zip dir and then encrypt (tarfile std lib)

import logging
import argparse
from pathlib import Path

from core.gitignore import Gitignore
from core import state
from core.channel import get_channels, get_channel, get_linked_encrypted_dotfiles
from core.exceptions import MicrodotError
from core.daemon import watch_repo, sync

logger = logging.getLogger("microdot")


class App():
    def parse_args(self, state):
        parser = argparse.ArgumentParser(description='Static site generator.')

        parser.add_argument('-c', '--channel',      help='channel', metavar='NAME', default='common')
        parser.add_argument('-l', '--link',         help='link dotfile', metavar='DOT', default=None)
        parser.add_argument('-L', '--link-all',     help='link all dotfiles in channel', action='store_true')
        parser.add_argument('-u', '--unlink',       help='unlink dotfile', metavar='DOT', default=None)
        parser.add_argument('-U', '--unlink-all',   help='unlink all dotfiles in channel', action='store_true')
        parser.add_argument('-i', '--init',         help='init dotfile', metavar='PATH', default=None)
        parser.add_argument('-s', '--sync',         help='sync repo', action='store_true')
        parser.add_argument('-e', '--encrypt',      help='encrypt file', action='store_true')
        parser.add_argument('-w', '--watch',        help='start git watch daemon', action='store_true')
        parser.add_argument('-d', '--dotfiles-dir', help='dotfiles directory', metavar='DIR', default=None)
        parser.add_argument('-y', '--assume-yes',   help='answer yes to questions', action='store_true')
        parser.add_argument('-f', '--force',        help='overwrite file if exists', action='store_true')

        args = parser.parse_args()

        state.do_link_all     = args.link_all
        state.do_unlink_all   = args.unlink_all
        state.do_link         = args.link
        state.do_unlink       = args.unlink
        state.do_init         = args.init
        state.do_encrypt      = args.encrypt
        state.do_assume_yes   = args.assume_yes
        state.do_force        = args.force
        state.do_watch        = args.watch
        state.do_sync       = args.sync

        # find dotfiles directory
        if args.dotfiles_dir:
            state.core.dotfiles_dir = Path(args.dotfiles_dir)
        else:
            state.core.dotfiles_dir = Path(state.core.dotfiles_dir)
        
        # get or create channel
        state.channel = get_channel(args.channel, state, create=True, assume_yes=state.do_assume_yes)

    def run(self):
        self.parse_args(state)

        if state.do_link_all:
            state.channel.link_all(force=state.do_force, assume_yes=state.do_assume_yes)

        elif state.do_unlink_all:
            state.channel.unlink_all(assume_yes=state.do_assume_yes)

        elif state.do_link:
            if not (dotfile := state.channel.get_dotfile(state.do_link)):
                logger.error(f"Dotfile not found: {state.do_link}")
            try:
                dotfile.link(state.do_force)
            except MicrodotError as e:
                logger.error(e)

        elif state.do_unlink:
            if not (dotfile := state.channel.get_dotfile(state.do_unlink)):
                logger.error(f"Dotfile not found: {state.do_unlink}")
            try:
                dotfile.unlink()
            except MicrodotError as e:
                logger.error(e)

        elif state.do_init:
            try:
                state.channel.init(Path(state.do_init), encrypted=state.do_encrypt)
            except MicrodotError as e:
                logger.error(e)

        elif state.do_sync:
            sync(state.core.dotfiles_dir, state.notifications.error_interval)

        elif state.do_watch:
            try:
                watch_repo(state.core.dotfiles_dir,
                           pull_interval  = state.git.pull_interval,
                           push_interval  = state.git.push_interval,
                           error_interval = state.notifications.error_interval)
            except MicrodotError as e:
                logger.error(e)

        else:
            for state.channel in get_channels(state):
                state.channel.list()
            return

        # Add linked encrypted files to the gitignore file
        gitignore = Gitignore(state.core.dotfiles_dir)
        for dotfile in get_linked_encrypted_dotfiles(state):
            gitignore.add(dotfile.channel.name / dotfile.name)

        gitignore.write()


if __name__ == "__main__":
    app = App()
    app.run()
