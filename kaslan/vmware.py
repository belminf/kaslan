import atexit
import sys
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from pyvmomi_tools.cli import cursor
from kaslan.exceptions import VMwareException

class VMware(object):

    def __init__(self, host, port, user, password):
        try:
            self.session = SmartConnect(host=host, user=user, pwd=password, port=int(port))
        except IOError as e:
            raise VMwareException('Unable to create vCenter session {}:{}@{}'.format(host, port, user))

        atexit.register(Disconnect, self.session)
        self.content = self.session.RetrieveContent()

    def get_object(self, types, name, root=None):
        if not root:
            root = self.content.rootFolder
        type_list = types if isinstance(types, list) else [types]
        container = self.content.viewManager.CreateContainerView(root, type_list, True)
        try:
            return next((c for c in container.view if c.name == name))
        except StopIteration:
            raise VMwareException('Unable to find {} ({})'.format(name, types))

    def get_folder(self, path):
        current_folder = None
        for f in path.split('/'):
            current_folder = self.get_object(vim.Folder, f, root=current_folder)
        return current_folder
    
    def clone(
        self,
        template_name,
        vm_name,
        cpus,
        memory,
        datacenter_name,
        cluster_name,
        datastore_name,
        ip,
        domain,
        dns,
        network_name,
        portgroup,
        subnet,
        gateway,
        folder_path=None,
        *args,
        **kwargs
    ):
        # Find objects
        datacenter = self.get_object(vim.Datacenter, datacenter_name)
        cluster = self.get_object(vim.ClusterComputeResource, cluster_name)
        datastore = self.get_object(vim.Datastore, datastore_name)
        template_vm = self.get_object(vim.VirtualMachine, template_name)

        # DVS portgroup do things a tad different
        if not portgroup:
            network = self.get_object(vim.Network, network_name)
        else:
            network = self.get_object(vim.dvs.DistributedVirtualPortgroup, network_name)

        # Get folder, defaults to datacenter
        if folder_path:
            folder = self.get_folder(folder_path)
        else:
            folder = datacenter.vmFolder

        # Default objects
        resource_pool = cluster.resourcePool

        # Relocation specs
        relospec = vim.vm.RelocateSpec()
        relospec.datastore = datastore
        relospec.pool = resource_pool

        # Modify NIC card
        nic = vim.vm.device.VirtualDeviceSpec()
        nic.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        nic.device = vim.vm.device.VirtualVmxnet3()
        nic.device.wakeOnLanEnabled = True
        nic.device.addressType = 'assigned'
        nic.device.key = 4000
        nic.device.deviceInfo = vim.Description()
        nic.device.deviceInfo.label = 'Network Adapter 1'
        nic.device.deviceInfo.summary = network_name
        if not portgroup:
            nic.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            nic.device.backing.network = network
            nic.device.backing.deviceName = network_name
            nic.device.backing.useAutoDetect = False
        else:
            portgroup_connection = vim.dvs.PortConnection()
            portgroup_connection.portgroupKey = network.key
            portgroup_connection.switchUuid = network.config.distributedVirtualSwitch.uuid
            nic.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
            nic.device.backing.port = portgroup_connection
        nic.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        nic.device.connectable.startConnected = True
        nic.device.connectable.allowGuestControl = True

        # Configuration specs
        vmconf = vim.vm.ConfigSpec()
        vmconf.numCPUs = cpus
        vmconf.memoryMB = memory
        vmconf.cpuHotAddEnabled = True
        vmconf.memoryHotAddEnabled = True
        vmconf.deviceChange = [nic]

        # NIC mapping
        nic_map = vim.vm.customization.AdapterMapping()
        nic_map.adapter = vim.vm.customization.IPSettings()
        nic_map.adapter.ip = vim.vm.customization.FixedIp()
        nic_map.adapter.ip.ipAddress = ip
        nic_map.adapter.subnetMask = subnet
        nic_map.adapter.gateway = gateway
        nic_map.adapter.dnsDomain = domain
        
        # Global networking
        global_ip = vim.vm.customization.GlobalIPSettings()
        global_ip.dnsServerList = dns
        global_ip.dnsSuffixList = domain

        # Identity settings
        ident = vim.vm.customization.LinuxPrep()
        ident.domain = domain
        ident.hostName = vim.vm.customization.FixedName()
        ident.hostName.name = vm_name

        # Customization specs
        customspec = vim.vm.customization.Specification()
        customspec.nicSettingMap = [nic_map]
        customspec.globalIPSettings = global_ip
        customspec.identity = ident

        # Clone specs
        clonespec = vim.vm.CloneSpec()
        clonespec.location = relospec
        clonespec.config = vmconf
        clonespec.customization = customspec
        clonespec.powerOn = True
        clonespec.template = False

        # Create task
        task = template_vm.Clone(folder=folder, name=vm_name, spec=clonespec)
        try:
            task.wait(
                queued=lambda t: sys.stdout.write("Queued...\n"),
                running=lambda t: sys.stdout.write("Running...\n"),
                success=lambda t: sys.stdout.write("\nVM '{}' cloned in folder '{}'.\n".format(vm_name, folder_path)),
                error=lambda t: sys.stdout.write('\nError!\n')
            )
        except Exception as e:
            print e.msg

