from kaslan.commands import get_vmware
from kaslan.exceptions import CLIException
from netaddr import IPNetwork, IPAddress
import socket
import os


def cli(subparsers, config):
    # Clone parser
    parser = subparsers.add_parser('clone', help='Clone a VM')
    parser.set_defaults(func=func)

    # Clone: arguments
    parser_args = parser.add_argument_group('cloning arguments')
    parser_args.add_argument('template', help='template')
    parser_args.add_argument('vm_name', help='name of new VM')

    # Clone: options
    parser_opts = parser.add_argument_group('cloning optional overrides')
    parser_opts.add_argument('--datacenter', dest='datacenter_name', help='datacenter', default=config['defaults']['datacenter'])
    parser_opts.add_argument('--cluster', dest='cluster_name', help='cluster', default=config['defaults']['cluster'])
    parser_opts.add_argument('--ds', dest='ds_name', help='datastore name (required if --ds_prefix not provided)')
    parser_opts.add_argument('--ds_prefix', dest='ds_prefix', help='datastore prefix (required if --ds not provided)')
    parser_opts.add_argument('--ds_prov_limit', dest='ds_prov_limit', help='datastore provision percentage limit (used with --ds_prefix)', default=config['defaults']['ds_prov_limit'])
    parser_opts.add_argument('--ds_vm_limit', dest='ds_vm_limit', help='datastore VM limit (used with --ds_prefix)', default=config['defaults']['ds_vm_limit'])
    parser_opts.add_argument('--folder', dest='folder_path', help='folder path, with / delimiter', default=config['defaults'].get('folder'))
    parser_opts.add_argument('--ip', help='IP address for VM, defaults to DNS lookup of vm_name', default=None)
    parser_opts.add_argument('--cpus', '-c', metavar='COUNT', help='CPU count for VM', type=int, default=config['defaults']['cpus'])
    parser_opts.add_argument('--memory', '-m', metavar='GB', help='memory for VM', type=long, default=config['defaults']['memory_gb'])
    parser_opts.add_argument('--domain', '-d', help='domain', default=config['defaults']['domain'])
    parser_opts.add_argument('--no-template-alias', help='allow the use of a template whose alias is not configured', action='store_true', default=False)
    parser_opts.add_argument('--force', help='ignore pre-checks like ping test', action='store_true', default=False)


def func(args, config):

    # Normalize some arguments
    args.vm_name = args.vm_name.lower()
    args.domain = args.domain.lower()

    # Check if we have a datastore
    if not any((args.ds_name, args.ds_prefix)):
        raise CLIException('Require to specify datastore using either --ds or --ds_prefix')

    # Get IP address from name if not provided
    if not args.ip:
        args.ip = repr(socket.gethostbyname('{}.{}'.format(args.vm_name, args.domain)))[1:-1]

    # Make sure IP address isn't used
    if not args.force and os.system('ping -c1 -W1 {} > /dev/null 2>&1'.format(args.ip)) == 0:
        raise CLIException('IP address {} is responding to ping, use --force to ignore ping response'.format(args.ip))

    # Get network settings
    net_settings = None
    for n, s in config['networks'].iteritems():
        if IPAddress(args.ip) not in IPNetwork(n):
            continue

        net_settings = s
        net_settings['subnet'] = str(IPNetwork(n).netmask)
        break

    # Check if settings set
    if not net_settings:
        raise CLIException('Network for {} not configured in kaslan.yaml'.format(args.ip))

    # Check if all settings are given
    if not all(k in net_settings for k in ('subnet', 'gateway', 'dns')):
        raise CLIException('Network for {} missing settings in kaslan.yaml'.format(args.ip))

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
    if not args.ds_name:
        args.ds_name = vmware.get_a_datastore(
            args.cluster_name,
            args.ds_prefix,
            args.ds_prov_limit,
            args.ds_vm_limit
        )
        print 'Using datastore {}...'.format(args.ds_name)

    # Perform the clone
    vmware.clone(
        template_name=template_name,
        **dict(vars(args).items() + net_settings.items())
    )
