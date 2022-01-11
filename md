#!/usr/bin/env python3

# TODO don't show git dir as channel

import os, sys
import logging
import argparse
from pathlib import Path
import shutil

try:
    import yaml
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)

logger = logging.getLogger("microdot")
logger.setLevel(logging.DEBUG)


class ConfigException(Exception): pass


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


class Config(dict):
    def __init__(self, path=False):
        self._config_path = path
        self._config = {}

        if not path:
            configdir = os.path.expanduser('~') + '/.config/' + os.path.basename(sys.argv[0]).split(".")[0]
            self._config_path = configdir + '/' + os.path.basename(sys.argv[0]).split(".")[0] + '.yaml'

    def __str__(self):
        return str(self._config)

    def __bool__(self):
        # is called when object is tested with: if <object> == True
        if len(self._config) > 0:
            return True
        else:
            return False

    def __getitem__(self, key):
        try:
            return self._config[key]
        except KeyError as e:
            raise KeyError(f"Key doesn't exist, key={key}")

    def __setitem__(self, key, value):
        try:
            self._config[key] = value
        except KeyError as e:
            logger.warning(f"Failed to set key, Key doesn't exist, key={key}")

    def set_path(self, path):
        self._config_path = path

    def set_config_data(self, data):
        self._config = data

    def keys(self):
        # override dict keys method
        return self._config.keys()

    def dict_deep_merge(self, d1, d2):
        """ deep merge two dicts """
        dm = d1.copy()
        for k,v in d2.items():
            if k in dm.keys() and type(v) == dict:
                dm[k] = self.dict_deep_merge(dm[k], d2[k])
            else:
                dm[k] = v
        return dm

    def test_file(self, path):
        """ Test if file exists """
        try:
            with open(path) as f:
                return True
        except IOError as e:
            return False

    def ensure_dir(self, dirname):
        if not os.path.exists(dirname):
            os.makedirs(dirname)
            logger.info(f"Created directory: {dirname}")

    def configfile_exists(self):
        return self.test_file(self._config_path)

    def load(self, path=False, merge=True):
        if not path:
            path = self._config_path

        try:
            with open(path, 'r') as configfile:
                cfg = yaml.safe_load(configfile)

                if not cfg:
                    return

                if merge:
                    self._config = self.dict_deep_merge(self._config, cfg)
                else:
                    self._config = cfg

                logger.info(f"Loaded config file, path={path}")
            return True
        except yaml.YAMLError as e:
            raise ConfigException(f"Failed to load YAML in config file: {path}\n{e}")
        except FileNotFoundError as e:
            raise ConfigException(f"Config file doesn't exist: {path}\n{e}")

    def write(self, path=False, commented=False):
        if not path:
            path = self._config_path

        self.ensure_dir(os.path.dirname(path))

        with open(path, 'w') as outfile:
            try:
                yaml.dump(self._config, outfile, default_flow_style=False)
                logger.info(f"Wrote config to: {path}")
            except yaml.YAMLError as e:
                raise ConfigException(f"Failed to write YAML in config file: {path}, message={e}")

        # comment the config file that was just written by libYAML
        if commented:
            lines = []

            with open(self._config_path, 'r') as f:
                lines = f.readlines()

            lines = [f"#{x}" for x in lines]

            with open(self._config_path, 'w') as f:
                f.writelines(lines)


class Utils():
    def colorize(self, string, color):
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

        return colors[color] + string + colors["reset"]

    def confirm(self, msg, assume_yes=False):
        if assume_yes:
            return True
        if input(msg + ' [y/N] ').lower() == 'y':
            return True


class Dotfile():
    def __init__(self, path, channel):
        self._channel = channel
        self.path = path
        self.name = str(path.absolute()).lstrip(str(channel.absolute()))
        self.link_path = Path(Path.home()) / self.name

    def check_symlink(self):
        # check if link links to src
        if not self.link_path.is_symlink():
            return
        return self.link_path.resolve() == self.path

    def is_dir(self):
        return self.path.is_dir()

    def is_file(self):
        return self.path.is_file()

    def link(self, force=False):
        link = self.link_path

        if link.exists() and force:
            logger.info(f"Link path exists, using --force to overwrite: {link}")
            if link.is_file():
                os.remove(link)
            elif link.is_symlink():
                link.unlink()
            elif link.is_dir():
                shutil.rmtree(link)
            else:
                logger.error(f"Failed to remove path: {link}")
                return

        if link.is_symlink():
            logger.error(f"Dotfile already linked: {link}")
            return

        if link.exists():
            logger.error(f"Link exists: {link}")
            return

        link.symlink_to(self.path)
        logger.info(f"Linked: {link} -> {self.path}")
    
    def unlink(self):
        if not self.check_symlink():
            logger.error(f"Dotfile is not linked: {self.name}")
            return

        self.link_path.unlink()
        print(f"Unlinked: {self.link_path}")


class Channel(Utils):
    def __init__(self, path, config):
        self._path = path
        self.name = path.name
        self._dotfiles = self.search_dotfiles(self._path, config['core']['check_dirs'])

        self._color_channel_name = config["colors"]["channel_name"]
        self._color_linked       = config["colors"]["linked"]
        self._color_unlinked     = config["colors"]["unlinked"]


    def search_dotfiles(self, item, search_dirs):
        # recursive find of files and dirs in channel when file/dir is in search_dirs
        items = [Dotfile(f, self._path) for f in item.iterdir() if f.is_file()]

        for d in [d for d in item.iterdir() if d.is_dir()]:
            if d.name in search_dirs:
                items += self.search_dotfiles(d, search_dirs)
            else:
                items.append(Dotfile(d, self._path))
        return sorted(items, key=lambda item: item.name)

    def list(self):
        """ Pretty print all dotfiles """
        print(self.colorize(f"\nchannel: {self.name}", self._color_channel_name))

        items =  [d for d in self._dotfiles if d.is_dir()]
        items += [f for f in self._dotfiles if f.is_file()]

        for item in items:
            color = self._color_linked if item.check_symlink() else self._color_unlinked

            if item.is_dir():
                print(self.colorize(f"[D] {item.name}", color))
            else:
                print(self.colorize(f"[F] {item.name}", color))

    def get_dotfile(self, name):
        for df in self._dotfiles:
            if df.name == name:
                return df

    def link_all(self, force=False, assume_yes=False):
        if self.confirm(f"Link all dotfiles in channel {self.name}?", assume_yes):
            for dotfile in self._dotfiles:
                dotfile.link(force=force)

    def unlink_all(self, assume_yes=False):
        if self.confirm(f"Unlink all dotfiles in channel {self.name}?", assume_yes):
            for dotfile in self._dotfiles:
                dotfile.unlink()

    def init(self, path):
        """ Start using a dotfile.
            Copy dotfile to channel directory and create symlink. """
        src = Path(self._path / str(path.absolute()).lstrip(str(Path.home().absolute())))
        dotfile = Dotfile(src, self._path)

        if self.get_dotfile(dotfile.name):
            logger.error(f"Dotfile already exists in channel: {dotfile.name}")
            return

        if not (path.is_file() or path.is_dir()):
            logger.error(f"Source path is not a file or directory: {path}")
            return

        if path.is_symlink():
            logger.error(f"Source path is a symlink: {path}")
            return
        
        path.replace(dotfile.path)
        logger.info(f"Moved: {path} -> {dotfile.path}")
        dotfile.link()
        return dotfile


class App(Utils):
    def __init__(self):
        self._channels = []

    def load_config_defaults(self, config):
        config['core'] = {}
        config['core']['dotfiles_dir'] = Path.home() / 'dev/dotfiles'
        config['core']['check_dirs'] = ['.config']

        config['colors'] = {}
        config['colors']["channel_name"] = 'magenta'
        config['colors']["dotfiles_dir"] = 'blue'
        config['colors']["linked"]       = 'green'
        config['colors']["unlinked"]     = 'default'

    def get_channels(self, path, blacklist=[".git"]):
        return [ Channel(d, self.c) for d in Path(path).iterdir() if d.is_dir() and d.name not in blacklist ]

    def get_channel(self, dotfiles_dir, name, create=True):
        name = name if name else "common"
        path = dotfiles_dir / name

        if not path.is_dir():
            if not self.confirm(f"Channel {name} doesn't exist, would you like to create it?"):
                return
            path.mkdir()

        for channel in self.get_channels(dotfiles_dir):
            if channel.name == name:
                return channel

        # this should never display
        logger.error(f"Unexpected error, failed to find channel: {name}")

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Static site generator.')

        parser.add_argument('-c', '--channel',      help='channel', metavar='NAME', default=None)
        parser.add_argument('-l', '--link',         help='link dotfile', metavar='DOT', default=None)
        parser.add_argument('-L', '--link-all',     help='link all dotfiles in channel', action='store_true')
        parser.add_argument('-u', '--unlink',       help='unlink dotfile', metavar='DOT', default=None)
        parser.add_argument('-U', '--unlink-all',   help='unlink all dotfiles in channel', action='store_true')
        parser.add_argument('-i', '--init',         help='init dotfile', metavar='PATH', default=None)
        parser.add_argument('-d', '--dotfiles-dir', help='dotfiles directory', metavar='DIR', default=None)
        parser.add_argument('-y', '--assume-yes',   help='answer yes to questions', action='store_true')
        parser.add_argument('-f', '--force',        help='overwrite file if exists', action='store_true')

        args = parser.parse_args()

        self.assume_yes = args.assume_yes

        if args.dotfiles_dir:
            self.c['core']['dotfiles_dir'] = Path(args.dotfiles_dir)

        channel = self.get_channel(self.c['core']['dotfiles_dir'], args.channel, create=True)
        if not channel:
            return

        if args.link_all:
            channel.link_all(force=args.force, assume_yes=args.assume_yes)

        elif args.unlink_all:
            channel.unlink_all(assume_yes=args.assume_yes)

        elif args.link:
            if not (df := channel.get_dotfile(args.link)):
                logger.error(f"Dotfile not found: {args.link}")
                return
            df.link(args.force)

        elif args.unlink:
            if not (df := channel.get_dotfile(args.unlink)):
                logger.error(f"Dotfile not found: {args.unlink}")
                return
            df.unlink()

        elif args.init:
            channel.init(Path(args.init))

        else:
            for c in self.get_channels(self.c['core']['dotfiles_dir']):
                c.list()

    def run(self):
        ch = logging.StreamHandler()
        ch.setFormatter(CustomFormatter())
        logger.addHandler(ch)

        self.c = Config()
        self.load_config_defaults(self.c)
        if not self.c.configfile_exists():
            self.c.write(commented=True)

        self.c.load(merge=False)

        # create default channel if not exist
        default_channel = Path(self.c['core']['dotfiles_dir']) / 'common'
        if not default_channel.is_dir():
            try:
                default_channel.mkdir(parents=True)
                logger.info(f"Created default channel: {default_channel}")
            except PermissionError as e:
                logger.error(f"Failed to create default channel: {default_channel}")
                return

        self.parse_args()


if __name__ == "__main__":
    app = App()
    app.run()
