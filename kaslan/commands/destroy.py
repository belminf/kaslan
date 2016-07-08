from kaslan.commands import get_vmware


def cli_setup(subparsers, config):

    # Destroy parser
    parser = subparsers.add_parser('destroy', help='Delete a VM')
    parser.set_defaults(func=func)

    # Destroy: arguments
    parser_args = parser.add_argument_group('destroy arguments')
    parser_args.add_argument('vm_name', help='name of VM')


def func(args, config):

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
