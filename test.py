#!/usr/bin/env python3

from pathlib import Path
from core.config import Config

#def load_config_defaults(state):
#    state['core'] = {}
#    state['core']['dotfiles_dir'] = str(Path.home() / 'dev/dotfiles')
#    state['core']['check_dirs'] = ['.config']
#
#    state['encryption'] = {}
#    #state['encryption']['key'] = Fernet.generate_key()
#
#    state['colors'] = {}
#    state['colors']["channel_name"] = 'magenta'
#    state['colors']["linked"]       = 'green'
#    state['colors']["unlinked"]     = 'default'

state = Config()
#load_config_defaults(state)

state.bever = {}
state.bever['banaan'] = 'sldfsdf'
state.super().__init__(state._config)
print(state.bever.banaan)
