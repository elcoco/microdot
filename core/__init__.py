from pathlib import Path
import logging

from core.config import Config
from core.utils import Lock, info
from core.gitignore import Gitignore
#from core.sync import StatusList

from cryptography.fernet import Fernet

try:
    import pretty_errors
except ImportError:
    pass

class CustomFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors"""

    colors = {}
    colors['black']    = '\033[0;30m'
    colors['bblack']   = '\033[1;30m'
    colors['red']      = '\033[0;31m'
    colors['bred']     = '\033[1;31m'
    colors['green']    = '\033[0;32m'
    colors['bgreen']   = '\033[1;32m'
    colors['yellow']   = '\033[0;33m'
    colors['byellow']  = '\033[1;33m'
    colors['blue']     = '\033[0;34m'
    colors['bblue']    = '\033[1;34m'
    colors['magenta']  = '\033[0;35m'
    colors['bmagenta'] = '\033[1;35m'
    colors['cyan']     = '\033[0;36m'
    colors['bcyan']    = '\033[1;36m'
    colors['white']    = '\033[0;37m'
    colors['bwhite']   = '\033[1;37m'
    colors['reset']    = '\033[0m'
    colors['default']    = '\033[0m'

    format = "%(message)s"

    FORMATS = {
        logging.DEBUG: colors['default'] + format + colors['reset'],
        logging.INFO: colors['default'] + format + colors['reset'],
        logging.WARNING: colors['red'] + format + colors['reset'],
        logging.ERROR: colors['bred'] + format + colors['reset'],
        logging.CRITICAL: colors['bred'] + format + colors['reset']
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


# init lockfile
lock = Lock('/tmp/microdot.lock')

# init logging
logger = logging.getLogger("microdot")
ch = logging.StreamHandler()
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)
logger.setLevel(logging.INFO)

# init configfile and state
state = Config(path=Path.home() / '.config/microdot/microdot.conf')
state.core                   = {}
state.core.dotfiles_dir      = str(Path.home() / '.dotfiles')
state.core.channel_blacklist = ['.git']
state.core.default_channel   = 'common'
state.encryption             = {}
state.encryption.key         = Fernet.generate_key()
state.colors                 = {}
state.colors.channel_name    = 'bblue'
state.colors.linked          = 'green'
state.colors.unlinked        = 'default'
state.colors.conflict        = 'bred'
state.colors.encrypted       = 'bmagenta'
state.colors.tree            = 'bblue'
state.colors.tree_dirs       = 'bwhite'
state.git                    = {}
state.git.interval           = 30
state.notifications          = {}
state.notifications.error_interval = 600

if not state.configfile_exists():
    state.write(commented=False)
    info("init", "new_key", "New key created in config file, don't forget to backup!")

state.load(merge=False)

# init program state
state.channel       = None
state.do_link       = None
state.do_unlink     = None
state.do_link_all   = None
state.do_unlink_all = None
state.do_init       = None
state.do_solve      = None

state.do_to_encrypted = None
state.do_to_decrypted = None

state.do_watch      = False
state.do_encrypt    = False
state.do_assume_yes = False
state.do_force      = False
state.do_sync       = False
state.do_use_git    = False


# CONSTANTS should not be changed!!
CONFLICT_EXT          = "#CONFLICT"
ENCRYPTED_DIR_EXT     = "#D#CRYPT"
ENCRYPTED_FILE_EXT    = "#F#CRYPT"
CONFLICT_DIR_EXT      = ENCRYPTED_DIR_EXT + CONFLICT_EXT
CONFLICT_FILE_EXT     = ENCRYPTED_FILE_EXT + CONFLICT_EXT
ENCRYPTED_DIR_FORMAT  = "{name}#{md5}#{ts}" + ENCRYPTED_DIR_EXT
ENCRYPTED_FILE_FORMAT = "{name}#{md5}#{ts}" + ENCRYPTED_FILE_EXT

# format used in encrypted filenames
TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"

# dirname relative to dotfiles dir to store decrypted files/dirs in
DECRYPTED_DIR = 'decrypted'

# skip these dirs when searching for channels and dotfiles
SCAN_DIR_BLACKLIST     = [DECRYPTED_DIR]
SCAN_CHANNEL_BLACKLIST = [DECRYPTED_DIR]

GIT_COMMIT_MSG = 'update'

# indicate a scan dir
SCAN_DIR_FILE = '.microdot'

