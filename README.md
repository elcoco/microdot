# Microdot
TODO: update readme
## Introduction
Microdot is a simple dotfiles manager.

**What microdot is:**
- it can solve the problem of having multiple sets of dotfiles for multiple systems
- it places all dotfiles in one directory
- it provides tools to link and unlink dotfiles to $HOME

**What microdot isn't:**
- it doesn't do versioning, better use git for that
- syncing can be done with tools like nextcloud

## Getting started

If you run microdot for the first time, it will create:
- a config file at: ``$XDG_CONFIG_HOME/.config/microdot/microdot.yaml``
- a dotfiles directory at: ``$HOME/dotfiles``

Now you can start adding dotfiles to the dotfiles directory:
```
eco@laptop1> microdot init ~/.bashrc

Move /home/eco/.basrhc to dotfiles directory? [y/N] y
Copied file: /home/eco/.bashrc -> /home/eco/sync/dotfiles/.bashrc
Removed file: /home/eco/.bashrc
Created link: /home/eco/.bashrc -> /home/eco/sync/dotfiles/.bashrc

eco@laptop1> microdot init ~/.config/i3

Move /home/eco/.config/i3 to dotfiles directory? [y/N] y
Copied dir: /home/eco/.config/i3 -> /home/eco/sync/dotfiles/common/.config/i3
Removed dir: /home/eco/.config/i3
Created link: /home/eco/.config/i3 -> /home/eco/sync/dotfiles/common/.config/i3

etc ....
```
To view which files are inside the dotfiles dir:
```
eco@laptop1>  microdot list

Dotfiles dir: /home/eco/sync/dotfiles

channel: common
[D] .vim
[D] .config/i3
[D] .config/mopidy
[D] .config/zathura
[F] .screenrc
[F] .vimrc
```
This is all nice but if we have multiple computers that require different versions of dotfiles we run into problems.  
To keep different sets, called channels, we can provide a channel name with the ``-c <channel name>`` flag:
```
eco@laptop1> microdot init ~/.bashrc -c laptop1

Channel doesn't exist, do you want to create it? [y/N] y
Move /home/eco/.bashrc to dotfiles directory? [y/N] y
Copied file: /home/eco/.bashrc -> /home/eco/sync/dotfiles/laptop1/.bashrc
Removed file: /home/eco/.bashrc
Created link: /home/eco/.bashrc -> /home/eco/sync/dotfiles/laptop1/.bashrc
```
if you run ``microdot list`` again you can see the channel is created and the file is moved:
```
eco@laptop1>  microdot list

Dotfiles dir: /home/eco/sync/dotfiles

channel: common
[D] .vim
[D] .config/i3
[D] .config/mopidy
[D] .config/zathura
[F] .screenrc
[F] .vimrc

channel: laptop1
[F] .bashrc
```
Since channels are just subdirectories under the dotfiles directory, the directory layou would look something like this:
```
~/sync/dotfiles/
├── common
│   ├── .config
│   │   ├── mopidy
│   │   └── zathura
│   ├── .screenrc
│   ├── .vim
│   └── .vimrc
└── laptop1
    └── .bashrc

```
To stop using ``.bashrc`` from channel ``laptop1``:
```
$ microdot unlink .bashrc -c laptop1

Removed link: /home/eco/.bashrc
```

To unlink all dotfiles within channel ``laptop1``
```
# when channel is omitted, the default channel "common" is assumed.
$ microdot link -c laptop1

Created link: /home/eco/.bashrc -> /home/eco/sync/dotfiles/laptop1/.bashrc
Created link: /home/eco/.config/i3 -> /home/eco/sync/dotfiles/laptop1/.config/i3
```

## Docopt
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
