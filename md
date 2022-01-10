#!/usr/bin/env python3

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

    def search_channel(self, item, search_dirs):
        # recursive find of files and dirs in channel when file/dir is in search_dirs
        items = [f for f in item.iterdir() if f.is_file()]

        for d in [d for d in item.iterdir() if d.is_dir()]:
            if d.name in search_dirs:
                items += self.search_channel(d, search_dirs)
            else:
                items.append(d)
        return sorted(items, key=lambda item: item.name)

    def check_symlink(self, src, link):
        # check if link links to src
        if not link.is_symlink():
            return

        return link.resolve() == src


class App(Utils):
    def load_config_defaults(self, config):
        config['core'] = {}
        config['core']['dotfiles_dir'] = Path.home() / 'dev/dotfiles'
        config['core']['check_dirs'] = ['.config']

        config['colors'] = {}
        config['colors']["channel_name"] = 'magenta'
        config['colors']["dotfiles_dir"] = 'blue'
        config['colors']["linked"]       = 'green'
        config['colors']["unlinked"]     = 'default'

    def confirm(self, msg):
        if self.assume_yes:
            return True
        if input(msg + ' [y/N] ').lower() == 'y':
            return True

    def list(self):
        """ list those damn dotfiles """
        color_dotfiles_dir = self.c["colors"]["dotfiles_dir"]
        color_channel_name = self.c["colors"]["channel_name"]
        color_linked       = self.c["colors"]["linked"]
        color_unlinked     = self.c["colors"]["unlinked"]

        channels = [ f for f in Path(self.c['core']['dotfiles_dir']).iterdir() if f.is_dir() ]

        for channel in channels:
            print(self.colorize(f"\nchannel: {channel.name}", color_channel_name))

            items_unsorted = self.search_channel(channel, self.c['core']['check_dirs'])
            items = [ d for d in items_unsorted if d.is_dir() ]
            items += [ f for f in items_unsorted if f.is_file() ]

            for item in items:
                lnk = Path(Path.home()) / item.relative_to(channel)
                color = color_linked if self.check_symlink(item, lnk) else color_unlinked

                if item.is_dir():
                    print(self.colorize(f"[D] {item.relative_to(channel)}", color))
                else:
                    print(self.colorize(f"[F] {item.relative_to(channel)}", color))

    def link(self, name, channel):
        src = Path(self.c['core']['dotfiles_dir']) / channel / name
        lnk = Path(Path.home()) / name

        if not src.exists():
            logger.error(f"Source doesn't exist: {src}")
            return

        if lnk.exists() and self.use_force:
            logger.info(f"Link path exists, using --force to overwrite: {lnk}")
            if lnk.is_file():
                os.remove(lnk)
            elif lnk.is_symlink():
                lnk.unlink()
            elif lnk.is_dir():
                shutil.rmtree(lnk)
            else:
                logger.error(f"Failed to remove path: {lnk}")
                return

        if lnk.is_symlink():
            logger.error(f"File already linked: {lnk}")
            return

        if lnk.exists():
            logger.error(f"Destination path exists: {lnk}")
            return

        lnk.symlink_to(src)
        logger.info(f"Linked: {lnk} -> {src}")

    def link_all(self, channel):
        if not self.confirm(f"Link all dotfiles in channel {channel}?"):
            return

        channel = Path(self.c['core']['dotfiles_dir']) / channel

        for src in self.search_channel(channel, self.c['core']['check_dirs']):
            self.link(src.relative_to(channel), channel)

    def init(self, name, channel):
        lnk = Path(name)
        path = Path(name)
        src = Path(self.c['core']['dotfiles_dir']) / channel / str(path.absolute()).lstrip(str(Path.home().absolute()))

        if not (path.is_file() or path.is_dir()):
            logger.error(f"Path is not a file or directory: {path}")
            return

        if path.is_symlink():
            logger.error(f"Path is a symlink: {path}")
            return

        if src.exists():
            logger.error(f"Dotfile already exists with same name: {path}")
            return

        path.replace(src)
        lnk.symlink_to(src)
        logger.info(f"Moved: {path} -> {src}")
        logger.info(f"Linked: {lnk} -> {src}")

    def unlink(self, name, channel):
        dst = Path(Path.home()) / name

        if not dst.exists():
            logger.error(f"Path doesn't exist: {dst}")
            return

        if not dst.is_symlink():
            logger.error(f"Path is not a symlink: {dst}")
            return

        dst.unlink()
        print(f"Unlinked path: {dst}")

    def unlink_all(self, channel):
        if not self.confirm(f"Unlink all dotfiles in channel {channel}?"):
            return

        channel = Path(self.c['core']['dotfiles_dir']) / channel

        for src in self.search_channel(channel, self.c['core']['check_dirs']):
            self.unlink(src.relative_to(channel), channel)

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Static site generator.')

        parser.add_argument('-c', '--channel',      help='channel', metavar='CHANNEL', default=None)
        parser.add_argument('-l', '--link',         help='link dotfile', action='store_true')
        parser.add_argument('-u', '--unlink',       help='unlink dotfile', action='store_true')
        parser.add_argument('-i', '--init',         help='init dotfile', action='store_true')
        parser.add_argument('-d', '--dotfiles-dir', help='dotfiles directory', metavar='DIR', default=None)
        parser.add_argument('-y', '--assume-yes',   help='answer yes to questions', action='store_true')
        parser.add_argument('-f', '--force',        help='overwrite file if exists', action='store_true')

        parser.add_argument('name', nargs='?', metavar='PATH', default=None)

        args = parser.parse_args()
        name = args.name

        self.assume_yes = args.assume_yes
        self.use_force = args.force

        do_link = args.link
        do_unlink = args.unlink
        do_init = args.init

        if args.dotfiles_dir:
            self.c['core']['dotfiles_dir'] = args.dotfiles_dir

        if not args.channel:
            channel = Path(self.c['core']['dotfiles_dir']) / "common"
        else:
            channel = Path(self.c['core']['dotfiles_dir']) / args.channel

        if not channel.is_dir():
            if not self.confirm("Channel doesn't exist, would you like to create it?"):
                return
            channel.mkdir()

        if do_link:
            if name:
                self.link(name, channel)
            else:
                self.link_all(channel)

        elif do_init:
            self.init(name, channel)

        elif do_unlink:
            if name:
                self.unlink(name, channel)
            else:
                self.unlink_all(channel)
        else:
            self.list()

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
