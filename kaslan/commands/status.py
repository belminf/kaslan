from kaslan.commands import get_vmware


def cli_setup(subparsers, config):

    # Status parser
    parser = subparsers.add_parser('status', help='Get VM information')
    parser.set_defaults(func=func)

    # Status: arguments
    parser_args = parser.add_argument_group('status arguments')
    parser_args.add_argument('vm_name', help='name of VM')

    # Status: options
    parser_opts = parser.add_argument_group('status options')
    parser_opts.add_argument('--add', '-a', dest='status_add', metavar='COUNT', type=int, help='add status')


def func(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Get VMware
    vmware = get_vmware(args, config)

    # Get status
    vmware.get_status(args.vm_name)
