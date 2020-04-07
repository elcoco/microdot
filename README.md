# Microdot

### Introduction
Microdot is a simple dotfiles manager.

What microdot does:
- organize multiple sets of dotfiles for multiple systems into channels.
- keep all dotfiles in one dir
- provide tools to link and unlink the files

What microdot doesn't:
- syncing can be done with tools like nextcloud
- for versioning, use git

### Usage
Channels are just subdirectories inside the dotfiles directory.

A directory layout with 3 channels (common, laptop1, laptop2) would
look something like this

```
~/sync/dotfiles/
├── common
│   ├── .config
│   │   ├── mopidy
│   │   └── zathura
│   ├── .screenrc
│   ├── .vim
│   ├── .vimrc
│   └── .Xresources
├── laptop1
│   ├── .bashrc
│   └── .config
│       └── i3
└── laptop2
    ├── .bashrc
    └── .config
        └── i3
```
To list available dotfiles in all channels:
```
$ microdot list

Dotfiles dir: /home/eco/sync/dotfiles

channel: common
[D] .vim
[D] .config/mopidy
[D] .config/zathura
[F] .Xresources
[F] .screenrc
[F] .vimrc

channel: laptop1
[D] .config/i3
[F] .bashrc

channel: laptop2
[D] .config/i3
[F] .bashrc
```

To use a dotfile from channel "laptop1", a symlink needs to be created in the appropriate location in the filesystem.

```
$ microdot link .bashrc -c laptop1

Created link: /home/eco/.bashrc -> /home/eco/sync/dotfiles/laptop1/.bashrc
```

To link all dotfiles within a channel
```
# when channel is omitted, the default channel "common" is assumed.
$ microdot link -c laptop1

Created link: /home/eco/.bashrc -> /home/eco/sync/dotfiles/laptop1/.bashrc
Created link: /home/eco/.config/i3 -> /home/eco/sync/dotfiles/laptop1/.config/i3
```

To add a dotfile to channel laptop1
```
$ microdot init ~/.xinitrc -c laptop1

Move /home/eco/.xinitrc to dotfiles directory? [y/N] y
Copied file: /home/eco/.xinitrc -> /home/eco/sync/dotfiles/laptop1/.xinitrc
Removed file: /home/eco/.xinitrc
Created link: /home/eco/.xinitrc -> /home/eco/sync/dotfiles/laptop1/.xinitrc
```

### Docopt
```
Microdot :: A management tool for dotfiles

Usage:
    microdot [options] list
    microdot [options] init <name>
    microdot [options] link [<name>]
    microdot [options] unlink [<name>]
    microdot [options] newchannel <name>

Options:
    -c, --channel <channel>      specify channel [default: common]
    -h, --help                   help

Introduction:
    To solve the problem of having different collections of dotfiles
    for different machines, the dotfiles are organized into channels.
    If no channel is specified, the default channel "common" is assumed.

    At first start a config file is written to:
        $XDG_CONFIG_HOME/microdot/microdot.yaml

Examples:
    Show a list of all available dotfiles in the dotfiles directory
    $ microdot list

    Move a dotfile to the dotfiles directory and create a symlink
    $ microdot init ~/.config/ranger -c workstation

    Symlink a dotfile in the dotfiles directory to a path relative to $HOME
    $ microdot link .bashrc

    Symlink all dotfiles within the channel "workstation" to a path relative
    to $HOME
    $ microdot link -c workstation

    Unlink a dotfile. This will remove the symlink but keep the data in the
    dotfiles directory
    $ microdot unlink .config/ranger -c workstation

    Stop watching all dotfiles in channel workstation
    $ microdot unlink -c workstation
```
