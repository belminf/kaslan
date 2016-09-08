from kaslan.commands import get_vmware


def cli_setup(subparsers, config):

    parser = subparsers.add_parser('datastore', help='Manage datastores')
    parser.add_argument('cluster_name', help='cluster')
    parser.add_argument('--prefix', '-p', dest='ds_prefix', help='datastore prefixes to filter', default='')
    parser.add_argument('--summary', '-s', dest='ds_sum_prefixes', help='summarize datastore prefixes', action='store_true', default=False)
    parser.set_defaults(func=func)


def func(args, config):

    # Get VMware
    vmware = get_vmware(args, config)

    if args.ds_sum_prefixes:
        vmware.summarize_cluster_datastores(args.cluster_name, args.ds_prefix)
    else:
        vmware.get_cluster_datastores(args.cluster_name, args.ds_prefix)
