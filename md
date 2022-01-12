#!/usr/bin/env python3

# DONE don't show git dir as channel
# TODO make blacklist configurable
# TODO when linking or unlinking all, give a list of files before proceeding
# TODO when linking or unlinking all, filter file list

"""
    You can add a new encrypted file with: $ md --init file.txt -e
    This will:
        - Move the file to the channel directory
        - Encrypt the file, using the extension: .encrypted
        - Decrypt the encrypted file and place it next to the encrypted file.
        - Add the non-encrypted file to the .gitignore file to protect it from pushing to GIT.
        
    When linking an encrypted file:
        The encrypted file will be visible in the list without the .encrypted extension but with a [E] marker
        The encrypted file can be linked as normal with: $ md --link file.txt
        This will:
            - Decrypt the corresponding encrypted file and place it next to the encrypted file.
            - Add the non-encrypted file to the .gitignore file to protect it from pushing to GIT.

    When unlinking an encrypted file:
        The encrypted file will be visible in the list without the .encrypted extension but with a [E] marker
        The encrypted file can be unlinked as normal with: $ md --unlink file.txt
        This will:
            - Remove the link
            - Remove the un-encrypte file
            - Remove the file entry on the .gitignore file

    When the repository is updated, the linked encrypted files need to be decrypted by using: $ md --update
    We can automate this by managing the GIT repo for the user, but this will add more complexity.
"""

import os, sys
import logging
import argparse
from pathlib import Path
import shutil

from core.gitignore import Gitignore
from core import state
from core.channel import get_channels, get_channel, get_linked_encrypted_dotfiles
from core.exceptions import MicrodotError

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
        parser.add_argument('-e', '--encrypt',      help='encrypt file', action='store_true')
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

        # find dotfiles directory
        if args.dotfiles_dir:
            state.core.dotfiles_dir = Path(args.dotfiles_dir)
        else:
            state.core.dotfiles_dir = Path(state.core.dotfiles_dir)
        
        # get or create channel
        state.channel = get_channel(args.channel, state, assume_yes=state.do_assume_yes)

    def run(self):
        self.parse_args(state)

        if state.do_link_all:
            state.channel.link_all(force=state.do_force, assume_yes=state.do_assume_yes)

        elif state.do_unlink_all:
            state.channel.unlink_all(assume_yes=state.do_assume_yes)

        elif state.do_link:
            if not (dotfile := state.channel.get_dotfile(state.do_link)):
                logger.error(f"Dotfile not found: {state.do_link}")
                return
            try:
                dotfile.link(state.do_force)
            except MicrodotError as e:
                logger.error(e)
                return

        elif state.do_unlink:
            if not (dotfile := state.channel.get_dotfile(state.do_unlink)):
                logger.error(f"Dotfile not found: {state.do_unlink}")
                return
            try:
                dotfile.unlink()
            except MicrodotError as e:
                logger.error(e)
                return

        elif state.do_init:
            try:
                state.channel.init(Path(state.do_init), encrypted=state.do_encrypt)
            except MicrodotError as e:
                logger.error(e)
                return

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
