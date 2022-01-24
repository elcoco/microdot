source: https://unterwaditzer.net/2016/sync-algorithm.html

Maintain a local status list in a file

    .config/microdot/status.list


## Introduction
We want to sync encrypted files so we are trying to sync binary data.
Therefore we can't use git's merge.
To make sure git won't create any conflicts we create a new file everytime
the data changes.
The filename is based on filecontent:

    filename#MD5#DTYPE#ENCRYPTED

After each git push/pull we have to solve doubles
    


We keep a list with all the filenames, this functions as a history file with
only one entry per filename

    # format: ID
    file.txt#MD5#FILE#ENCRYPTED
    testdir#MD5#DIR#ENCRYPTED
    testfile.txt#a30f5a585efa971fc5b3eae62620251a#FILE#ENCRYPTED
    ...




## pre sync

    before evaluating, set initial state:
        - check if unencrypted dir is updated
            if hash(unencrypted_dir) != hash(encrypted_file)
                - encrypt file|dir -> create new encrypted file
                - remove old encrypted file
                - DONT'T update status file

        - pull changes from git
             
            
A    = hash of local item
B    = hash of remote item
S    = hash from status file
ID   = filename#md5#FILE|DIR#ENCRYPTED

For evaluation it doesn't matter which file is remote or local they will be
evaluated the same.
Since the filename changes when the content changes, A and B should always have
a different name.

    
    

## case: both A and B exist:

    A|B in status list:

    A - !B          B is newer
                        - remove A
                        - remove A in S
                        - insert B in S
    !A - B          A is newer
                        - remove B
                        - remove B in S
                        - insert A in S
    !A - !B         A and B are new
                        - conflict resolution

    A - B           Should not happen, BUG

## case: only A exists

    A in status list:

    A               do nothing
    !A              File A is new
                        - insert A in S

## case: files A and B don't exist but status list does
    shouldn't happen
    remove entry in status list

## post sync
    if B is new:
        - update unencrypted item

    unless there is a conflict, only one encrypted file should exist
