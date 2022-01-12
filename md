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

from core import gitignore, state
from core.channel import get_channels, get_channel, get_encrypted_dotfiles
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

        s = state['state']
        s['do_link_all']   = args.link_all
        s['do_unlink_all'] = args.unlink_all
        s['do_link']       = args.link
        s['do_unlink']     = args.unlink
        s['do_init']       = args.init

        s['do_encrypt']    = args.encrypt
        s['do_assume_yes'] = args.assume_yes
        s['do_force']      = args.force

        # find dotfiles directory
        if args.dotfiles_dir:
            state['core']['dotfiles_dir'] = Path(args.dotfiles_dir)
        else:
            state['core']['dotfiles_dir'] = Path(state['core']['dotfiles_dir'])
        
        # get or create channel
        s['channel'] = get_channel(args.channel, state, assume_yes=s['do_assume_yes'])

        # TODO: error if channel doesn't exist


    def run(self):
        self.parse_args(state)

        gitignore.set_dotfiles_dir(state['core']['dotfiles_dir'])

        s = state['state']
        channel = s['channel']

        if s['do_link_all']:
            channel.link_all(force=s['do_force'], assume_yes=s['do_assume_yes'])

        elif s['do_unlink_all']:
            channel.unlink_all(assume_yes=s['do_assume_yes'])

        elif s['do_link']:
            if not (dotfile := channel.get_dotfile(s['do_link'])):
                logger.error(f"Dotfile not found: {s['do_link']}")
                return

            try:
                dotfile.link(s['do_force'])
            except MicrodotError as e:
                logger.error(e)

        elif s['do_unlink']:
            if not (dotfile := channel.get_dotfile(s['do_unlink'])):
                logger.error(f"Dotfile not found: {s['do_unlink']}")
                return

            try:
                dotfile.unlink()
            except MicrodotError as e:
                logger.error(e)

        elif s['do_init']:
            try:
                channel.init(Path(s['do_init']), encrypted=s['do_encrypt'])
            except MicrodotError as e:
                logger.error(e)

        else:
            for channel in get_channels(state):
                channel.list()

        for dotfile in get_encrypted_dotfiles(state):
            gitignore.add(dotfile.channel.name / dotfile.name)

        gitignore.write()
        gitignore.list()



if __name__ == "__main__":
    app = App()
    app.run()
