from kaslan import __description__
from kaslan.exceptions import CLIException
from kaslan.vmware import VMware
from netaddr import IPNetwork, IPAddress
from argparse import ArgumentParser
import getpass
import yaml
import socket
import os


def main():

    # Load configuration
    config = yaml.load(file('config.yaml'))

    # Create main parser
    parser = ArgumentParser(description=__description__)
    parser.add_argument('-u', dest='vcenter_user', help='vCenter user', default=getpass.getuser())
    subparsers = parser.add_subparsers()

    # Clone parser
    parser_clone = subparsers.add_parser('clone')
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
    parser_clone_opts.add_argument('--cpus', '-c', metavar='COUNT', help='CPU count for VM', default=config['defaults']['cpus'])
    parser_clone_opts.add_argument('--memory', '-m', metavar='GB', help='memory for VM', default=config['defaults']['memory_gb'])
    parser_clone_opts.add_argument('--domain', '-d', help='domain', default=config['defaults']['domain'])
    parser_clone_opts.add_argument('--force', help='ignore pre-checks like ping test', action='store_true', default=False)

    # Memory parser
    parser_memory = subparsers.add_parser('memory')
    parser_memory.set_defaults(func=memory)

    # Memory: arguments
    parser_memory_args = parser_memory.add_argument_group('memory arguments')
    parser_memory_args.add_argument('vm_name', help='name of VM')

    # Memory: options
    parser_memory_opts = parser_memory.add_argument_group('memory options')
    parser_memory_opts.add_argument('--add', '-a', dest='memory_add', metavar='GB', type=int, help='add memory (GB)')

    # CPUs parser
    parser_cpus = subparsers.add_parser('cpus')
    parser_cpus.set_defaults(func=cpus)

    # CPUs: arguments
    parser_cpus_args = parser_cpus.add_argument_group('cpus arguments')
    parser_cpus_args.add_argument('vm_name', help='name of VM')

    # CPUs: options
    parser_cpus_opts = parser_cpus.add_argument_group('cpus options')
    parser_cpus_opts.add_argument('--add', '-a', dest='cpus_add', metavar='COUNT', type=int, help='add cpus')

    # Disks parser
    parser_disks = subparsers.add_parser('disks')
    parser_disks.set_defaults(func=disks)

    # Disks: arguments
    parser_disks_args = parser_disks.add_argument_group('disks arguments')
    parser_disks_args.add_argument('vm_name', help='name of VM')

    # Disks: options
    parser_disks_opts = parser_disks.add_argument_group('disks options')
    parser_disks_opts.add_argument('--add', '-a', dest='disks_add', metavar='COUNT', type=int, help='add disks')

    # Parse arguments
    args = parser.parse_args()
    args.func(args, config)


def disks(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Create API object
    vmware = VMware(
        host=config['vcenter_host'],
        port=config['vcenter_port'],
        user=getpass.getuser(),
        password=getpass.getpass('{}@{}: '.format(getpass.getuser(), config['vcenter_host']))
    )

    # Get disks
    vmware.get_disks(args.vm_name)


def memory(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Create API object
    vmware = VMware(
        host=config['vcenter_host'],
        port=config['vcenter_port'],
        user=getpass.getuser(),
        password=getpass.getpass('{}@{}: '.format(getpass.getuser(), config['vcenter_host']))
    )

    # Get memory
    if args.memory_add:
        vmware.add_memory(args.vm_name, args.memory_add)
    else:
        vmware.get_memory(args.vm_name)


def cpus(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Create API object
    vmware = VMware(
        host=config['vcenter_host'],
        port=config['vcenter_port'],
        user=getpass.getuser(),
        password=getpass.getpass('{}@{}: '.format(getpass.getuser(), config['vcenter_host']))
    )

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
        raise CLIException('Network {} not configured in config.yaml'.format(args.ip))

    # Get network in the cluster
    try:
        cluster_net_settings = net_settings['cluster_networks'][args.cluster_name]
    except KeyError:
        raise CLIException('Cluster {} not configured for network {} in config.yaml'.format(args.cluster, args.ip))

    # Get template name from alias
    try:
        template_name = config['templates'][args.template]
    except KeyError:
        raise CLIException('Template {} is not configured in config.yaml'.format(args.template))

    # Create API object
    vm = VMware(
        host=config['vcenter_host'],
        port=config['vcenter_port'],
        user=args.vcenter_user,
        password=getpass.getpass('{}@{}: '.format(args.vcenter_user, config['vcenter_host'])))

    # Perform the clone
    vm.clone(
        template_name=template_name,
        **dict(vars(args).items() + net_settings.items() + cluster_net_settings.items())
    )
