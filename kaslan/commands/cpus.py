from kaslan.commands import get_vmware


def cli_setup(subparsers, config):

    # CPUs parser
    parser = subparsers.add_parser('cpus', help='Manage VM CPU')
    parser.set_defaults(func=func)

    # CPUs: arguments
    parser_args = parser.add_argument_group('cpus arguments')
    parser_args.add_argument('vm_name', help='name of VM')

    # CPUs: options
    parser_opts = parser.add_argument_group('cpus options')
    parser_opts.add_argument('--add', '-a', dest='cpus_add', metavar='COUNT', type=int, help='add cpus')


def func(args, config):

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
