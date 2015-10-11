from kaslan import __description__
from kaslan.exceptions import CLIException
from kaslan.vmware import VMware
from netaddr import IPNetwork, IPAddress
from argparse import ArgumentParser
import getpass
import yaml
import socket


def main():

    # Load configuration
    config = yaml.load(file('config.yaml'))

    # Create main parser
    parser = ArgumentParser(description=__description__)
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
    parser_clone_opts.add_argument('--datacenter', dest='datacenter_name',  help='datacenter', default=config['defaults']['datacenter'])
    parser_clone_opts.add_argument('--cluster', dest='cluster_name', help='cluster', default=config['defaults']['cluster'])
    parser_clone_opts.add_argument('--folder', dest='folder_path',  help='folder path, with / delimiter', default=config['defaults'].get('folder'))
    parser_clone_opts.add_argument('--ip', help='IP address for VM, defaults to DNS lookup of vm_name', default=None)
    parser_clone_opts.add_argument('--cpus', '-c', metavar='COUNT', help='CPU count for VM', default=config['defaults']['cpus'])
    parser_clone_opts.add_argument('--memory', '-m', metavar='MB', help='memory for VM', default=config['defaults']['memory_mb'])
    parser_clone_opts.add_argument('--domain', '-d', help='domain', default=config['defaults']['domain'])

    # Clone: vcenter?
    parser_vcenter = parser_clone.add_argument_group('vCenter overrides')
    parser_vcenter.add_argument('--vcenter-user', '-u', help='vCenter user', default=getpass.getuser())
    parser_vcenter.add_argument('--vcenter-host', help='hostname of vCenter server', default=config['vcenter_host'])
    parser_vcenter.add_argument('--vcenter-port', help='port for the vCenter server', default=config['vcenter_port'])

    # Parse arguments
    args = parser.parse_args()
    args.func(args, config)


def clone(args, config):

    # Normalize some arguments
    args.vm_name = args.vm_name.lower()
    args.domain = args.domain.lower()

    # Get IP address from name if not provided
    if not args.ip:
        args.ip = repr(socket.gethostbyname('{}.{}'.format(args.vm_name,args.domain)))[1:-1]

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
        host=args.vcenter_host,
        port=args.vcenter_port,
        user=args.vcenter_user,
        password=getpass.getpass('{}@{}: '.format(args.vcenter_user, args.vcenter_host)))

    # Perform the clone
    vm.clone(
        template_name=template_name,
        **dict(vars(args).items() + net_settings.items() + cluster_net_settings.items())
    )
