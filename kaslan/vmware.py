import atexit
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
from pyvmomi_tools.cli import cursor

class VMware(object):

    def __init__(self, server, port, user, password):
        try:
            self.session = SmartConnect(host=server, user=user, pwd=password, port=int(port))
        except IOError as e:
            raise VMwareException('Unable to create vCenter session {}:{}@{}'.format(server, port, user))

        atexit.register(Disconnect, self.session)
        self.content = self.session.RetrieveContent()

    def get_object(self, types, name):
        type_list = types if isinstance(types, list) else [types]
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, type_list, True)
        try:
            return next((c for c in container.view if c.name == name))
        except StopIteration:
            return None

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
        subnet,
        gateway,
        **kwargs
    ):
        # Find objects
        datacenter = self.get_object(vim.Datacenter, datacenter_name)
        cluster = self.get_object(vim.ClusterComputeResource, cluster_name)
        datastore = self.get_object(vim.Datastore, datastore_name)
        template_vm = self.get_object(vim.VirtualMachine, template_name)
        network = self.get_object(vim.Network, network_name)

        # Default objects
        resource_pool = cluster.resourcePool
        destfolder = datacenter.vmFolder

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
        nic.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
        nic.device.backing.network = network
        nic.device.backing.deviceName = network_name
        nic.device.backing.useAutoDetect = False
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
        global_ip = vim.vm.customization.global_ipSettings()
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
        customspec.global_ipSettings = global_ip
        customspec.identity = ident

        # Clone specs
        clonespec = vim.vm.CloneSpec()
        clonespec.location = relospec
        clonespec.config = vmconf
        clonespec.customization = customspec
        clonespec.powerOn = True
        clonespec.template = False

        # Create task
        task = template_vm.Clone(folder=destfolder, name=vm_name, spec=clonespec)
        task.wait()
