- [x] don't show git dir as channel
- [ ] make blacklist configurable
- [x] when linking or unlinking all, give a list of files before proceeding
- [x] when linking or unlinking all, filter file list
- [x] when internet is gone, gitpush will just skip. when internet reconnects, the push is not triggered again
- [x] when a linked encrypted file is updated when using watch, update decrypted file
- [x] when answered no when creating common channel, program crashes`

- [x] when a decrypted file is edited it needs to sync with the encrypted file
      or changes get lost
      When linking/init encrypted file, a warning needs to display about non running daemons

- [x] encryption only works for files now


- [x] use shorter base64 hashes
- [x] call StatusList LastSyncIndex
- [x] filter out CONFLICT files
- [x] add inspect function to inspect conflicted encrypted files
- [x] use channel/decrypted for decrypted files/dirs
- [ ] when internet is back after a cut, wait a random amount of time.
      this way we don't get conflicts when all devices start pushing at the same time
- [x] add info messages on normal operations, link, unlink etc
- [x] link/unlink all exists when files are already linked
      when answering question a list of unlinked/linked files should display
- [x] when linking, if a link already exists but doesn't point to correct file
      md starts complaining
- [x] give nice list of conflicted files when listing
- [x] maybe move all constants to global state object
- [x] use columnize in list view
- [x] cleanup all tmp files/dirs in diff.py
- [x] make default channel configurable
- [x] it should be possible to use update() without git functionality so the user can use eg nextcloud for syncing
      -g for git sync and -s for sync without git
- [x] add warning to backup key when new key is created


- [x] add encrypt option to --link switch so we can encrypt an already initialized file
      ask the user to remove file from git cache
- [x] add unencrypt option

- [x] if there are two encrypted paths with same filename, sync will alway say the first file is new
      ├─ [EF] testfile.txt                     CyW2RHgK 2022-01-22 22:25:01
      └─ [EF] tmp/misc/testdir/testfile.txt    GaJbGojG 2022-01-30 17:16:26
- [x] conflict files should have a path

- [x] make dotfile classes a bit more logical

- [ ] the parent is already managed by microdot error should only warn when the dotfile is linked
      so init() should check and link() should check

- [x] when init file, parent dirs are checked but child dirs should also be checked for conflicts
