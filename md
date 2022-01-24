#!/usr/bin/env python3

import logging
import argparse
from pathlib import Path

from core.gitignore import Gitignore
from core import state, lock
from core.channel import get_channels, get_channel
from core.exceptions import MicrodotError
from core.sync import Sync
from core.utils import info, debug
from core.merge import handle_conflict

logger = logging.getLogger("microdot")


class App():
    def parse_args(self, state):
        #parser = argparse.ArgumentParser(prog='microdot', description='Microdot :: Manage dotfiles in style',
        parser = argparse.ArgumentParser(prog='microdot', usage='%(prog)s [OPTIONS]', description='Gotta manage them dotfiles',
                formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=42))

        parser.add_argument('-c', '--channel',        help='channel', metavar='NAME', default=state.core.default_channel)
        parser.add_argument('-l', '--link',           help='link dotfile', metavar='DOT', default=None)
        parser.add_argument('-L', '--link-all',       help='link all dotfiles in channel', action='store_true')
        parser.add_argument('-u', '--unlink',         help='unlink dotfile', metavar='DOT', default=None)
        parser.add_argument('-U', '--unlink-all',     help='unlink all dotfiles in channel', action='store_true')
        parser.add_argument('-i', '--init',           help='init dotfile', metavar='PATH', default=None)
        parser.add_argument('-e', '--encrypt',        help='use together with --init to also encrypt file', action='store_true')
        parser.add_argument('-E', '--encrypt-dotfile',help='encrypt file already initiated dotfile', metavar='DOT', default=None)
        parser.add_argument('-C', '--solve-conflict', help='solve conflict by merging', metavar=('CONFLICT'), default=None)

        parser.add_argument('-s', '--sync',           help='sync/update decrypted with encrypted dotfiles', action='store_true')
        parser.add_argument('-g', '--use_git',        help='use together with --sync to also sync repo with git', action='store_true')
        parser.add_argument('-w', '--watch',          help='start git watch daemon', action='store_true')
        parser.add_argument('-d', '--dotfiles-dir',   help='dotfiles directory', metavar='DIR', default=None)
        parser.add_argument('-y', '--assume-yes',     help='answer yes to questions', action='store_true')
        parser.add_argument('-f', '--force',          help='overwrite file if exists', action='store_true')
        parser.add_argument('-D', '--debug',          help='enable debug', action='store_true')

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
        state.do_sync         = args.sync
        state.do_use_git     = args.use_git
        state.do_solve        = args.solve_conflict
        state.do_encrypt_df   = args.encrypt_dotfile

        if args.debug:
            logger.setLevel(logging.DEBUG)

        # find dotfiles directory
        if args.dotfiles_dir:
            state.core.dotfiles_dir = Path(args.dotfiles_dir)
        else:
            state.core.dotfiles_dir = Path(state.core.dotfiles_dir)
        
        # get or create channel
        state.channel = get_channel(args.channel, state, create=True, assume_yes=True)

    def run(self):
        self.parse_args(state)

        # make sure no decrypted files are committed to git
        gitignore = Gitignore(state.core.dotfiles_dir)
        gitignore.write()

        if state.do_link_all:
            try:
                state.channel.link_all(force=state.do_force, assume_yes=state.do_assume_yes)
            except MicrodotError as e:
                logger.error(e)

        elif state.do_unlink_all:
            try:
                state.channel.unlink_all(assume_yes=state.do_assume_yes)
            except MicrodotError as e:
                logger.error(e)

        elif state.do_link:
            if not (dotfile := state.channel.get_dotfile(state.do_link)):
                logger.error(f"Dotfile not found: {state.do_link}")
                return
            try:
                dotfile.link(state.do_force)
                info("main", "linked", f"{dotfile.link_path} -> {dotfile.path}")
            except MicrodotError as e:
                logger.error(e)

        elif state.do_unlink:
            if not (dotfile := state.channel.get_dotfile(state.do_unlink)):
                logger.error(f"Dotfile not found: {state.do_unlink}")
                return
            try:
                dotfile.unlink()
                info("main", "unlinked", f"{dotfile.path}")
            except MicrodotError as e:
                logger.error(e)

        elif state.do_encrypt_df:
            if not (dotfile := state.channel.get_dotfile(state.do_encrypt_df)):
                logger.error(f"Dotfile not found: {state.do_encrypt_df}")
                return
            try:
                dotfile.do_encrypt(state.encryption.key)
                info("main", "unlinked", f"{dotfile.path}")
            except MicrodotError as e:
                logger.error(e)

        elif state.do_init:
            try:
                state.channel.init(Path(state.do_init), encrypted=state.do_encrypt)
                info("main", "init", f"{state.do_init}")
            except MicrodotError as e:
                logger.error(e)

        elif state.do_sync:
            try:
                s = Sync(state.core.dotfiles_dir,
                         state.git.interval,
                         state.notifications.error_interval,
                         use_git=state.do_use_git)
                with lock:
                    s.sync()
            except MicrodotError as e:
                logger.error(e)

        elif state.do_watch:
            try:
                s = Sync(state.core.dotfiles_dir,
                         state.git.interval,
                         state.notifications.error_interval,
                         use_git=state.do_use_git)
                s.watch_repo()
            except MicrodotError as e:
                logger.error(e)

        elif state.do_solve:
            conflict_path = Path(state.do_solve)
            orig_path = conflict_path.name.split('#')[0]

            if not (orig_df := state.channel.get_dotfile(orig_path)):
                logger.error(f"Dotfile not found: {orig_path}")
                return
            if not (conflict_df := state.channel.get_conflict(conflict_path)):
                logger.error(f"Conflict not found: {conflict_path}")
                return
            try:
                handle_conflict(orig_df, conflict_df)
            except MicrodotError as e:
                logger.error(e)

        else:
            for state.channel in get_channels(state):
                state.channel.list()


if __name__ == "__main__":
    app = App()
    app.run()
