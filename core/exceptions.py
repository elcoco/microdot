class MicrodotException(Exception):
    pass

class MicrodotError(MicrodotException):
    pass

class MDConflictError(MicrodotException):
    pass

class MDLinkError(MicrodotException):
    pass

class MDEncryptionError(MicrodotException):
    pass

class MDDotNotFoundError(MicrodotException):
    pass

class MDChannelNotFoundError(MicrodotException):
    pass

class MDPermissionError(MicrodotException):
    pass

class MDParseError(MicrodotException):
    pass


class MDPathNotFoundError(MicrodotException):
    pass

class MDPathExistsError(MicrodotException):
    pass

class MDPathLocationError(MicrodotException):
    """ Path is in wrong location, eg: not in homedir etc. """
    pass



# GIT ###############
class MDGitRepoError(MicrodotException):
    pass

class MDMergeError(MicrodotException):
    pass
