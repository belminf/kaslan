from kaslan.commands import get_vmware


def cli_setup(subparsers, config):

    # Compute parser
    parser = subparsers.add_parser('compute', help='Manage VM memory and CPU')
    parser.set_defaults(func=func)

    # Arguments
    parser_args = parser.add_argument_group('compute arguments')
    parser_args.add_argument('vm_name', help='name of VM')

    # Memory options
    parser_memory_opts = parser.add_argument_group('memory options')
    parser_memory_opts.add_argument('--add-memory', dest='memory_add', metavar='GB', type=float, help='add memory (GB)')
    parser_memory_opts.add_argument('-m', dest='memory_set', metavar='GB', type=float, help='set memory (GB)')

    # CPU options
    parser_cpu_opts = parser.add_argument_group('CPU options')
    parser_cpu_opts.add_argument('--add-cpu', dest='cpus_add', metavar='COUNT', type=int, help='add CPUs')
    parser_cpu_opts.add_argument('-c', dest='cpus_set', metavar='COUNT', type=int, help='set CPU count')


def func(args, config):

    # Normalize and get VMware
    vm_name = args.vm_name.lower()
    vmware = get_vmware(args, config)

    # Get current compute
    memory_mb, cpus = vmware.get_compute(vm_name)

    # Get the new memory count
    want_memory_mb = memory_mb
    if args.memory_add:
        want_memory_mb += args.memory_add * 1024
    elif args.memory_set:
        want_memory_mb = args.memory_set * 1024

    # Get the new CPU count
    want_cpus = cpus
    if args.cpus_add:
        want_cpus += args.cpus_add
    elif args.cpus_set:
        want_cpus = args.cpus_set

    # Change compute if we have to
    if (memory_mb != want_memory_mb) or (want_cpus != cpus):
        try:
            vmware.set_compute(vm_name, want_memory_mb, want_cpus)
        except Exception as err:
            print err
            print ''
            print 'Hint: Hot plug may be disabled or limited (see: http://kb.vmware.com/kb/2008405)'
            return

    # Always print status
    print('CPUs: {}'.format(want_cpus))
    print('Memory: {:.1f}GB'.format(want_memory_mb / 1024))
