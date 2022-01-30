#!/usr/bin/env python3

import sys
import logging
import argparse
from pathlib import Path

from core.gitignore import Gitignore
from core import state, lock
from core.channel import get_channels, get_channel
from core.exceptions import MicrodotError
from core.sync import Sync
from core.utils import info, debug, die
from core.merge import handle_conflict

logger = logging.getLogger("microdot")


class App():
    def parse_args(self, state):
        #parser = argparse.ArgumentParser(prog='microdot', description='Microdot :: Manage dotfiles in style',
        parser = argparse.ArgumentParser(prog='microdot', usage='%(prog)s [OPTIONS]', description='Gotta manage them dotfiles',
                formatter_class=lambda prog: argparse.HelpFormatter(prog,max_help_position=42))

        parser.add_argument('-l', '--link',           help='link dotfile', metavar='DOTFILE', default=None)
        parser.add_argument('-L', '--link-all',       help='link all dotfiles in channel', action='store_true')
        parser.add_argument('-u', '--unlink',         help='unlink dotfile', metavar='DOTFILE', default=None)
        parser.add_argument('-U', '--unlink-all',     help='unlink all dotfiles in channel', action='store_true')
        parser.add_argument('-i', '--init',           help='start using dotfile with microdot', metavar='PATH', default=None)
        parser.add_argument('-x', '--to-decrypted',   help='decrypt an already encrypted file', metavar='DOTFILE', default=None)
        parser.add_argument('-E', '--to-encrypted',   help='encrypt an already initiated dotfile', metavar='DOTFILE', default=None)

        parser.add_argument('-s', '--sync',           help='sync/update decrypted with encrypted dotfiles', action='store_true')
        parser.add_argument('-w', '--watch',          help='same as --sync but as a daemon', action='store_true')

        parser.add_argument('-C', '--solve-conflict', help='solve conflict by manual merging', metavar='CONFLICT', default=None)

        parser.add_argument('-g', '--use-git',        help='use together with --sync|--watch to sync repo with git', action='store_true')
        parser.add_argument('-e', '--encrypt',        help='use together with --init to encrypt file', action='store_true')
        parser.add_argument('-c', '--channel',        help='specify the channel to use', metavar='NAME', default=state.core.default_channel)
        parser.add_argument('-d', '--dotfiles-dir',   help='specify the dotfiles directory', metavar='DIR', default=None)
        parser.add_argument('-y', '--assume-yes',     help='assume yes to questions', action='store_true')
        parser.add_argument('-f', '--force',          help='force overwrite files/dirs', action='store_true')
        parser.add_argument('-D', '--debug',          help='enable debugging', action='store_true')

        # for use in command completion script, suppress visibility in help output
        parser.add_argument('--get-opts',             help=argparse.SUPPRESS, action="store_true")

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
        state.do_use_git      = args.use_git
        state.do_solve        = args.solve_conflict

        state.do_to_encrypted   = args.to_encrypted
        state.do_to_decrypted   = args.to_decrypted

        # used for ZSH command line completion. output arguments and exit
        if args.get_opts:
            print(" ".join(("--{}".format(opt.replace("_", "-")) for opt in vars(args))))
            sys.exit(0)

        if args.encrypt and not args.init:
            raise MicrodotError("Use --encrypt together with --init")

        if args.use_git and not (args.sync or args.watch):
            raise MicrodotError("Use --use_git together with --sync or --watch")

        if args.debug:
            logger.setLevel(logging.DEBUG)

        # find dotfiles directory
        if args.dotfiles_dir:
            state.core.dotfiles_dir = Path(args.dotfiles_dir)
        else:
            state.core.dotfiles_dir = Path(state.core.dotfiles_dir)
        
        # get or create channel
        state.channel = get_channel(args.channel, state, create=True, assume_yes=True)

    def setup(self):
        try:
            self.parse_args(state)
        except MicrodotError as e:
            die(e)

        # make sure no decrypted files are committed to git
        gitignore = Gitignore(state.core.dotfiles_dir)
        gitignore.write()

    def run(self):
        self.setup()

        if state.do_link_all:
            try:
                state.channel.link_all(force=state.do_force)
            except MicrodotError as e:
                die(e)

        elif state.do_unlink_all:
            try:
                state.channel.unlink_all()
            except MicrodotError as e:
                die(e)

        elif state.do_link:
            try:
                dotfile = state.channel.get_dotfile(state.do_link)
                dotfile.link(state.do_force)
                info("main", "linked", f"{dotfile.link_path} -> {dotfile.path}")
            except MicrodotError as e:
                die(e)

        elif state.do_unlink:
            try:
                dotfile = state.channel.get_dotfile(state.do_unlink)
                dotfile.unlink()
                info("main", "unlinked", f"{dotfile.path}")
            except MicrodotError as e:
                die(e)

        elif state.do_to_encrypted:
            try:
                dotfile = state.channel.get_dotfile(state.do_to_encrypted)
                dotfile.to_encrypted(state.encryption.key)
                info("main", "encrypted", f"{dotfile.path}")
            except MicrodotError as e:
                die(e)

        elif state.do_to_decrypted:
            try:
                dotfile = state.channel.get_dotfile(state.do_to_decrypted)
                dotfile.to_decrypted()
                info("main", "decrypted", f"{dotfile.path}")
            except MicrodotError as e:
                die(e)

        elif state.do_init:
            try:
                state.channel.init(Path(state.do_init), encrypted=state.do_encrypt)
                info("main", "init", f"{state.do_init}")
            except MicrodotError as e:
                die(e)

        elif state.do_sync:
            try:
                s = Sync(state.core.dotfiles_dir,
                         state.git.interval,
                         state.notifications.error_interval,
                         use_git=state.do_use_git)
                with lock:
                    s.sync()
            except MicrodotError as e:
                die(e)

        elif state.do_watch:
            try:
                s = Sync(state.core.dotfiles_dir,
                         state.git.interval,
                         state.notifications.error_interval,
                         use_git=state.do_use_git)
                s.watch_repo()
            except MicrodotError as e:
                die(e)

        elif state.do_solve:
            conflict_path = Path(state.do_solve)
            orig_path = conflict_path.parent/ conflict_path.name.split('#')[0]

            try:
                orig_df = state.channel.get_encrypted_dotfile(orig_path)

                if not (conflict := orig_df.has_conflict(conflict_path)):
                    die("Conflict not found")

                #conflict_df = state.channel.get_conflict(conflict_path)
                handle_conflict(orig_df, conflict)
            except MicrodotError as e:
                die(e)
        else:
            for state.channel in get_channels(state):
                state.channel.list()

        sys.exit(0)


if __name__ == "__main__":
    app = App()
    app.run()
