from kaslan.commands import get_vmware


def cli_setup(subparsers, config):

    # Memory parser
    parser = subparsers.add_parser('memory', help='Manage VM memory')
    parser.set_defaults(func=func)

    # Memory: arguments
    parser_args = parser.add_argument_group('memory arguments')
    parser_args.add_argument('vm_name', help='name of VM')

    # Memory: options
    parser_opts = parser.add_argument_group('memory options')
    parser_opts.add_argument('--add', '-a', dest='memory_add', metavar='GB', type=float, help='add memory (GB)')


def func(args, config):

    # Normalize
    args.vm_name = args.vm_name.lower()

    # Get VMware
    vmware = get_vmware(args, config)

    # Get memory
    if args.memory_add:
        vmware.add_memory(args.vm_name, args.memory_add)
    else:
        vmware.get_memory(args.vm_name)
