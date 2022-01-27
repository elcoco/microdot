# Microdot :: a simple dotfiles manager

## Features:
- **Channels:** Files are organized in channels. You can keep channels with sets of dotfiles for separate computers. Or keep common sets of dotfiles that are shared between computers.  
- **Encryption:** Files can be encrypted individually. An optional daemon can watch the unencrypted dotfile for changes and automatically keep the encrypted file up to date.
- **Git sync:** The daemon can sync to a git repo.
- **Conflict resolution:** If a sync conflict occurs between encrypted files, microdot enables you to merge the files manually.

## Usage:
Start using (initiate) a dotfile:

    md --init ~/.config/dotfile.txt

Same, but use encryption this time:

    md --encrypt --init ~/.config/dotfile.txt

Link and unlink an initialized dotfile:

    # when initialized you only have to specify the path relative to the home directory
    # eg:
    md --link .config/dotfile.txt
    md --unlink .config/dotfile.txt

Link and unlink all dotfiles in a channel:

    # not specifying a channel defaults to the "common" channel
    md --link-all
    md --unlink-all

    # link all dotfile in the my_hostname channel
    md --link-all --channel my_hostname
    md --unlink-all --channel my_hostname

Encrypt/decrypt an already initialized dotfile

    md --to-encrypted  .config/dotfile.txt
    md --to-decrypted  .config/dotfile.txt

## Encryption
On first run a config file containing the encryption key is created at: ```$XDG_CONFIG_HOME/microdot/microdot.conf```.  
When linking an initiated dotfile, behind the scenes the dotfile is:  

- decrypted  
- moved to the "decrypted" directory inside the dotfiles directory.    
- a link is created from the original dotfile location to the decrypted location  

Microdot contains a daemon to keep the decrypted and encrypted versions of the dotfile in sync.
When a change is made in the decrypted version the daemon will re-encrypt the file.  

    # do a sync if changes are detected
    $ microdot --sync

    # start watch daemon and sync everytime a change is made to an encrypted dotfile
    $ microdot --watch

Microdot can additionally sync with an external git repo.  
Git can only solve conflicts for text files. Because encrypted files are binary, git is not able to solve these conflicts.  
Microdot adds a sync layer on top of git to identify new versions and choose which version is the newest.  
To run the sync daemon:

    $ md --watch --use-git

In case of a conflict a conflict file is created in the dotfiles directory.  
When this happens, the conflict can be solved manually by running:

    $ md --solve-conflict dotfile.txt#j3DzJZAw#20220121181210#F#CRYPT#CONFLICT

## Sync algorithm
TODO: describe the sync algorithm

