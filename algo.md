source: https://unterwaditzer.net/2016/sync-algorithm.html

Maintain a local status list in a file

    .config/microdot/status.list



when a file is changed
    - the filename and hash is added to this list

        # format: NAME ID
        file.txt file.txt#MD5#encrypted
        testdir  testdir#MD5#dir#encrypted
        ...

when doing an update check collect information:

    A    = hash of unencrypted item
    B    = hash of encrypted item
    S    = hash from status file
    NAME = unencrypted filename
    ID   = encrypted filename

check for deletion/creation:

    FILE exists in:

    A - !B - !S     FILE created on A
                    copy A->B, insert A->S

    !A - B - !S     FILE created on B
                    copy B->A, insSrt B->S

    A - !B - S      FILE deleted on B
                    delete A and S

    !A - B - S      FILE deleted on A
                    delete B

    A - B - !S      if ID for A and B is same:
                        add A/B to S
                    else
                        invoke conflict resolution

    !A - !B - S     it doesn't exist in reallity
                    delete S

    ID changed in:
    A !in S && B in S   A changed
                        copy A->B

    A in S && B !in S   B changed
                        copy B->A

    A !in S && B !in S  A and B changed
                        invoke confilict resolution!

check for modifications:

                    


