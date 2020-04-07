# Microdot

### Introduction


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

