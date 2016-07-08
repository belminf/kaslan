from kaslan.vmware import VMware
import getpass

# Global variable of VMware object
_vmware = None


def get_vmware(args, config):
    global _vmware
    if not _vmware:
        _vmware = VMware(
            host=args.vcenter_host,
            port=args.vcenter_port,
            user=args.vcenter_user,
            password=getpass.getpass('{}@{}: '.format(args.vcenter_user, args.vcenter_host))
        )
    print ''
    return _vmware
