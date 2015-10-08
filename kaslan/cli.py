from kaslan import __description__
from kaslan.exceptions import CLIException
from kaslan.vmware import VMware
from netaddr import IPNetwork, IPAddress
from argparse import ArgumentParser
import getpass
import yaml

def main():
    config = yaml.load(file('config.yaml'))
    parser = ArgumentParser(description=__description__)
    subparsers = parser.add_subparsers()
    parser_clone = subparsers.add_parser('clone')
    parser_clone.set_defaults(func=clone)
    parser_clone_args = parser_clone.add_argument_group('cloning arguments')
    parser_clone_args.add_argument('template', help='template')
    parser_clone_args.add_argument('datastore', help='datastore')
    parser_clone_args.add_argument('ip', help='IP address')
    parser_clone_args.add_argument('vm', help='name of new VM')
    parser_clone_opts = parser_clone.add_argument_group('cloning optional overrides')
    parser_clone_opts.add_argument('--datacenter', help='datacenter', default=config['defaults']['datacenter'])
    parser_clone_opts.add_argument('--cluster', help='cluster', default=config['defaults']['cluster'])
    parser_clone_opts.add_argument('--cpus', '-c', metavar='COUNT', help='CPU count for VM', default=config['defaults']['cpus'])
    parser_clone_opts.add_argument('--memory', '-m', metavar='MB', help='memory for VM', default=config['defaults']['memory_mb'])
    parser_clone_opts.add_argument('--domain', '-d', help='domain', default=config['defaults']['domain'])
    parser_vcenter = parser_clone.add_argument_group('vCenter overrides')
    parser_vcenter.add_argument('--vcenter-user', '-u', help='vCenter user', default=getpass.getuser())
    parser_vcenter.add_argument('--vcenter-host', help='hostname of vCenter server', default=config['vcenter_host'])
    parser_vcenter.add_argument('--vcenter-port', help='port for the vCenter server', default=config['vcenter_port'])
    args = parser.parse_args()
    args.func(args, config)


def clone(args, config):
    try:
        net_settings = next((s for c, s in config['networks'].iteritems() if IPAddress(args.ip) in IPNetwork(c)))
    except StopIteration:
        raise CLIException('Network {} not configured in config.yaml'.format(args.ip))

    try:
        cluster_network = net_settings['cluster_networks'][args.cluster]
    except KeyError:
        raise CLIException('Cluster {} not configured for network {} in config.yaml'.format(args.cluster, args.ip))

    try:
        template_name = config['templates'][args.template]
    except KeyError:
        raise CLIException('Template {} is not configured in config.yaml'.format(args.template))

    vm = VMware(args.vcenter_host, args.vcenter_port, args.vcenter_user, getpass.getpass('{}@{}: '.format(args.vcenter_user, args.vcenter_host)))
    vm.clone(template_name, args.vm, args.cpus, args.memory, args.datacenter, args.cluster, args.datastore, args.ip, args.domain, net_settings['dns'], cluster_network, net_settings['subnet'], net_settings['gateway'])
