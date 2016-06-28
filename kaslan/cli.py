from kaslan import __description__
from kaslan.exceptions import CLIException
from kaslan.vmware import VMware
from netaddr import IPNetwork, IPAddress
from argparse import ArgumentParser
from os.path import expanduser
import getpass
import yaml
import socket
import os
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

    # Clone parser
    parser_clone = subparsers.add_parser('clone', help='Clone a VM')
    parser_clone.set_defaults(func=clone)

    # Clone: arguments
    parser_clone_args = parser_clone.add_argument_group('cloning arguments')
    parser_clone_args.add_argument('template', help='template')
    parser_clone_args.add_argument('datastore_name', help='datastore')
    parser_clone_args.add_argument('vm_name', help='name of new VM')

    # Clone: options
    parser_clone_opts = parser_clone.add_argument_group('cloning optional overrides')
    parser_clone_opts.add_argument('--datacenter', dest='datacenter_name', help='datacenter', default=config['defaults']['datacenter'])
    parser_clone_opts.add_argument('--cluster', dest='cluster_name', help='cluster', default=config['defaults']['cluster'])
    parser_clone_opts.add_argument('--folder', dest='folder_path', help='folder path, with / delimiter', default=config['defaults'].get('folder'))
    parser_clone_opts.add_argument('--ip', help='IP address for VM, defaults to DNS lookup of vm_name', default=None)
    parser_clone_opts.add_argument('--cpus', '-c', metavar='COUNT', help='CPU count for VM', type=int, default=config['defaults']['cpus'])
    parser_clone_opts.add_argument('--memory', '-m', metavar='GB', help='memory for VM', type=long, default=config['defaults']['memory_gb'])
    parser_clone_opts.add_argument('--domain', '-d', help='domain', default=config['defaults']['domain'])
    parser_clone_opts.add_argument('--no-template-alias', help='allow the use of a template whose alias is not configured', action='store_true', default=False)
    parser_clone_opts.add_argument('--force', help='ignore pre-checks like ping test', action='store_true', default=False)

    # Memory parser
    parser_memory = subparsers.add_parser('memory', help='Manage VM memory')
    parser_memory.set_defaults(func=memory)

    # Memory: arguments
    parser_memory_args = parser_memory.add_argument_group('memory arguments')
    parser_memory_args.add_argument('vm_name', help='name of VM')

    # Memory: options
    parser_memory_opts = parser_memory.add_argument_group('memory options')
    parser_memory_opts.add_argument('--add', '-a', dest='memory_add', metavar='GB', type=float, help='add memory (GB)')

    # CPUs parser
    parser_cpus = subparsers.add_parser('cpus', help='Manage VM CPU')
    parser_cpus.set_defaults(func=cpus)

    # CPUs: arguments
    parser_cpus_args = parser_cpus.add_argument_group('cpus arguments')
    parser_cpus_args.add_argument('vm_name', help='name of VM')

    # CPUs: options
    parser_cpus_opts = parser_cpus.add_argument_group('cpus options')
    parser_cpus_opts.add_argument('--add', '-a', dest='cpus_add', metavar='COUNT', type=int, help='add cpus')

    # Disks parser
    parser_disks = subparsers.add_parser('disks', help='Manage VM disks')
    parser_disks.set_defaults(func=disks)

    # Disks: arguments
    parser_disks_args = parser_disks.add_argument_group('disks arguments')
    parser_disks_args.add_argument('vm_name', help='name of VM')

    # Disks: options
    parser_disks_opts = parser_disks.add_argument_group('disks options')
    parser_disks_opts.add_argument('--add', '-a', dest='disks_add', metavar='COUNT', type=int, help='add disks')

    # Status parser
    parser_status = subparsers.add_parser('status', help='Get VM information')
    parser_status.set_defaults(func=status)

    # Status: arguments
    parser_status_args = parser_status.add_argument_group('status arguments')
    parser_status_args.add_argument('vm_name', help='name of VM')

    # Status: options
    parser_status_opts = parser_status.add_argument_group('status options')
    parser_status_opts.add_argument('--add', '-a', dest='status_add', metavar='COUNT', type=int, help='add status')

    # Destroy parser
    parser_destroy = subparsers.add_parser('destroy', help='Delete a VM')
    parser_destroy.set_defaults(func=destroy)

    # Destroy: arguments
    parser_destroy_args = parser_destroy.add_argument_group('destroy arguments')
    parser_destroy_args.add_argument('vm_name', help='name of VM')

    # Parse arguments
    args = parser.parse_args()
    if args.cmd == 'input':
        for line in fileinput.input(args.filenames):
            args = parser.parse_args(line.split())
            args.func(args, config)
    else:
        args.func(args, config)
    print ''


# Global variable of VMware object
_vmware = None


def get_vmware(args, config):
    global _vmware
    if not _vmware:
        _vmware = VMware(
            host=args.vcenter_host,
            port=args.vcenter_port,
            user=args.vcenter_user,
            password=getpass.getpass('{}@{}: '.format(args.vcenter_user, args.vcenter_host))
        )
    print ''
    return _vmware


def destroy(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Confirm
    if raw_input('\nConfirm deletion by re-typing VM name: ') != args.vm_name:
        print 'Confirmation failed, canceled'
        return

    # ASSERT: Confirmed

    # Get VMware
    vmware = get_vmware(args, config)

    # Destroy VM
    vmware.destroy(args.vm_name)


def status(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Get VMware
    vmware = get_vmware(args, config)

    # Get status
    vmware.get_status(args.vm_name)


def disks(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Get VMware
    vmware = get_vmware(args, config)

    # Get disks
    vmware.get_disks(args.vm_name)


def memory(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Get VMware
    vmware = get_vmware(args, config)

    # Get memory
    if args.memory_add:
        vmware.add_memory(args.vm_name, args.memory_add)
    else:
        vmware.get_memory(args.vm_name)


def cpus(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Get VMware
    vmware = get_vmware(args, config)

    # Add CPUs
    if args.cpus_add:
        vmware.add_cpus(args.vm_name, args.cpus_add)

    # Get CPU count
    else:
        vmware.get_cpus(args.vm_name)


def clone(args, config):

    # Normalize some arguments
    args.vm_name = args.vm_name.lower()
    args.domain = args.domain.lower()

    # Get IP address from name if not provided
    if not args.ip:
        args.ip = repr(socket.gethostbyname('{}.{}'.format(args.vm_name, args.domain)))[1:-1]

    # Make sure IP address isn't used
    if not args.force and os.system('ping -c1 {} > /dev/null 2>&1'.format(args.ip)) == 0:
        raise CLIException('IP address {} is responding to ping, canceling'.format(args.ip))

    # Get network settings
    try:
        net_settings = next((s for c, s in config['networks'].iteritems() if IPAddress(args.ip) in IPNetwork(c)))
    except StopIteration:
        raise CLIException('Network {} not configured in kaslan.yaml'.format(args.ip))

    # Get template name from alias
    if not args.no_template_alias:
        try:
            template_name = config['templates'][args.template]
        except KeyError:
            CLIException('Template {} is not configured in kaslan.yaml, use --no-template-alias to force'.format(args.template))
    else:
        template_name = args.template

    # Get VMware
    vmware = get_vmware(args, config)

    # Perform the clone
    vmware.clone(
        template_name=template_name,
        **dict(vars(args).items() + net_settings.items())
    )
