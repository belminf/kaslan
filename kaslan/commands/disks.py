from kaslan.commands import get_vmware


def cli_setup(subparsers, config):

    # Disks parser
    parser = subparsers.add_parser('disks', help='Manage VM disks')
    parser.set_defaults(func=func)

    # Disks: arguments
    parser_args = parser.add_argument_group('disks arguments')
    parser_args.add_argument('vm_name', help='name of VM')

    # Disks: options
    parser_opts = parser.add_argument_group('disks options')
    parser_opts.add_argument('--add', '-a', dest='disks_add', metavar='COUNT', type=int, help='add disks')


def func(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Get VMware
    vmware = get_vmware(args, config)

    # Get disks
    vmware.get_disks(args.vm_name)
