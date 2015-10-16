import atexit
import sys

from pyVim.connect import SmartConnect, Disconnect, GetSi
from pyVmomi import vim, vmodl
from kaslan.exceptions import VMwareException

# Turn off SSL warning
import requests
requests.packages.urllib3.disable_warnings()


class VMware(object):

    def __init__(self, host, port, user, password):
        try:
            self.session = SmartConnect(host=host, user=user, pwd=password, port=int(port))
        except IOError:
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

    def start_task(self, task, success_msg, hint_msg=None):
        try:
            task.wait(
                queued=lambda t: sys.stdout.write("Queued...\n"),
                running=lambda t: sys.stdout.write("Running...\n"),
                success=lambda t: sys.stdout.write("\n{}\n".format(success_msg)),
                error=lambda t: sys.stdout.write('\nError!\n')
            )
        except Exception as e:
            print 'Exception: {}'.format(e.msg)
            if hint_msg:
                print 'Hint: {}'.format(hint_msg)

    def get_vm_props(self, vm_name, propfilter):

        # Starting point
        obj_spec = vmodl.query.PropertyCollector.ObjectSpec()
        obj_spec.obj = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.VirtualMachine, ], True)
        obj_spec.skip = True

        # Define path for search
        traversal_spec = vmodl.query.PropertyCollector.TraversalSpec()
        traversal_spec.name = 'traversing'
        traversal_spec.path = 'view'
        traversal_spec.skip = False
        traversal_spec.type = obj_spec.obj.__class__
        obj_spec.selectSet = [traversal_spec]

        # Identify the properties to the retrieved
        property_spec = vmodl.query.PropertyCollector.PropertySpec()
        property_spec.type = vim.VirtualMachine
        property_spec.pathSet = list(set(propfilter + ['name', ]))

        # Create filter specification
        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = [obj_spec]
        filter_spec.propSet = [property_spec]

        # Retrieve properties
        collector = self.session.content.propertyCollector
        props = collector.RetrieveContents([filter_spec])

        for obj in props:

            # Compile propeties
            properties = {prop.name: prop.val for prop in obj.propSet}

            # Only care about the specific VM
            if properties['name'] != vm_name:
                continue

            # Return this one with obj
            properties['obj'] = obj.obj
            return properties

        # Couldn't find VM
        raise VMwareException('Unable to find properties for VM {}'.format(vm_name))

    def add_memory(self, vm_name, add_gb):
        vm = self.get_vm_props(vm_name, ['config.hardware.memoryMB', 'config.hardware.numCPU', ])

        new_gb = (vm['config.hardware.memoryMB'] / 1024) + add_gb

        spec = vim.vm.ConfigSpec()
        spec.memoryMB = (new_gb * 1024)
        spec.numCPUs = vm['config.hardware.numCPU']

        self.start_task(
            vm['obj'].ReconfigVM_Task(spec=spec),
            success_msg='{} memory now: {:.1f}GB'.format(vm_name, new_gb),
            hint_msg='Hot plug memory may be disabled or limited (see: http://kb.vmware.com/kb/2008405)'
        )

    def get_memory(self, vm_name):
        vm = self.get_vm_props(vm_name, ['config.hardware.memoryMB', ])
        print(
            '\n{} memory: {:.1f}GB'.format(
                vm_name,
                vm['config.hardware.memoryMB'] / 1024
            )
        )

    def add_cpus(self, vm_name, add_cpu_count):
        vm = self.get_vm_props(vm_name, ['config.hardware.memoryMB', 'config.hardware.numCPU', ])

        new_cpu_count = vm['config.hardware.numCPU'] + add_cpu_count

        spec = vim.vm.ConfigSpec()
        spec.memoryMB = vm['config.hardware.memoryMB']
        spec.numCPUs = new_cpu_count

        self.start_task(
            vm['obj'].ReconfigVM_Task(spec=spec),
            success_msg='{} CPU count now: {}'.format(vm_name, new_cpu_count)
        )

    def get_cpus(self, vm_name):
        vm = self.get_vm_props(vm_name, ['config.hardware.numCPU', ])
        print(
            '\n{} CPU count: {}'.format(
                vm_name,
                vm['config.hardware.numCPU']
            )
        )

    def get_disks(self, vm_name):
        vm = self.get_vm_props(vm_name, ['config.hardware.device', ])
        print('Disks')
        print('-----')
        disk_index = 0
        for device in vm['config.hardware.device']:
            if type(device) == vim.vm.device.VirtualDisk:
                disk_index += 1
                thin_prov = ' (thin)' if device.backing.thinProvisioned else ''
                size_gb = device.capacityInKB / (1024 * 1024)
                datastore = device.backing.fileName
                print '{}) {} - {:.1f}GB{}'.format(disk_index, datastore, size_gb, thin_prov)

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
        vmconf.memoryMB = memory * 1024
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
        self.start_task(task, 'VM {} cloned in folder {}'.format(vm_name, folder_path))


def wait_for_task(task, *args, **kwargs):

    def no_op(task, *args):
        pass

    queued_callback = kwargs.get('queued', no_op)
    running_callback = kwargs.get('running', no_op)
    success_callback = kwargs.get('success', no_op)
    error_callback = kwargs.get('error', no_op)

    si = GetSi()
    pc = si.content.propertyCollector

    obj_spec = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)]
    prop_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task, pathSet=[], all=True)
    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = obj_spec
    filter_spec.propSet = [prop_spec]
    filter = pc.CreateFilter(filter_spec, True)

    try:
        version, state = None, None

        # Loop looking for updates till the state moves to a completed state.
        waiting = True
        while waiting:
            update = pc.WaitForUpdates(version)
            version = update.version
            for filterSet in update.filterSet:
                for objSet in filterSet.objectSet:
                    task = objSet.obj
                    for change in objSet.changeSet:
                        if change.name == 'info':
                            state = change.val.state
                        elif change.name == 'info.state':
                            state = change.val
                        else:
                            continue

                        if state == vim.TaskInfo.State.success:
                            success_callback(task, *args)
                            waiting = False

                        elif state == vim.TaskInfo.State.queued:
                            queued_callback(task, *args)

                        elif state == vim.TaskInfo.State.running:
                            running_callback(task, *args)

                        elif state == vim.TaskInfo.State.error:
                            error_callback(task, *args)
                            raise task.info.error

    finally:
        if filter:
            filter.Destroy()

vim.Task.wait = wait_for_task
