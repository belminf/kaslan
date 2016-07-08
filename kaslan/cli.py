from kaslan import __description__
from kaslan.exceptions import CLIException
from kaslan.commands import clone, datastore, memory, cpus, disks, status, destroy
from argparse import ArgumentParser
from os.path import expanduser
import getpass
import yaml
import fileinput


def get_config(path_list):
    for f in path_list:
        try:
            return yaml.load(file(f))
        except IOError:
            continue

    # ASSERT: Couldn't find a good path

    raise CLIException('Could not find a valid configuration file.')


def main():

    # Load configuration
    config = get_config((
        './kaslan.yaml',
        expanduser('~/.kaslan.yaml'),
        '/etc/kaslan.yaml',
    ))

    # Create main parser
    parser = ArgumentParser(description=__description__)
    parser.add_argument('-u', dest='vcenter_user', help='Override vCenter user', default=getpass.getuser())
    parser.add_argument('--host', dest='vcenter_host', help='Override vCenter host', default=config['vcenter_host'])
    parser.add_argument('--port', dest='vcenter_port', help='Override vCenter port', default=config['vcenter_port'])
    subparsers = parser.add_subparsers(dest='cmd')

    # Stdin oarser
    parser_stdin = subparsers.add_parser('input', help='Process commands from input')
    parser_stdin.add_argument('filenames', help='files to use instead of stdin', nargs='*')

    # Command parsers
    for cmd in (datastore, clone, memory, cpus, disks, status, destroy):
        cmd.cli_setup(subparsers, config)

    # Parse arguments
    args = parser.parse_args()
    if args.cmd == 'input':
        for line in fileinput.input(args.filenames):
            args = parser.parse_args(line.split())
            args.func(args, config)
    else:
        args.func(args, config)
    print ''
