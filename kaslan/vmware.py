import atexit
import sys
import re

from tzlocal import get_localzone
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

    def get_portgroup(self, vlan, host):
        def vlan_host_filter(props):

            # If host is in this network's host, return whether the vlan matches
            if host in (h.name for h in props['host']):
                return props['config.defaultPortConfig'].vlan.vlanId == vlan

            # Fallback to false
            return False

        return self.get_obj_props(
            prop_names=('host', 'config.defaultPortConfig'),
            obj_type=vim.dvs.DistributedVirtualPortgroup,
            obj_filter=vlan_host_filter
        )['obj']

    def start_task(self, task, success_msg, task_tag='', hint_msg=None, last_task=True):
        pre_result = '\n'
        if task_tag:
            task_tag = '[{}] '.format(task_tag)
            pre_result = ''
        try:
            task.wait(
                queued=lambda t: sys.stdout.write('{}Queued...\n'.format(task_tag)),
                running=lambda t: sys.stdout.write('{}Running...\n'.format(task_tag)),
                success=lambda t: sys.stdout.write('{}{}{}\n'.format(pre_result, task_tag, success_msg)),
                error=lambda t: sys.stdout.write('{}{}Error!\n'.format(pre_result, task_tag))
            )

        except Exception as e:
            print '\nException: {}'.format(e.msg)
            if hint_msg:
                print 'Hint: {}'.format(hint_msg)
            return False

        return True

    def get_obj_props(self, prop_names, obj_type=vim.VirtualMachine, obj_names=None, obj_filter=None, only_one=True):

        # Setup filter
        if not obj_filter and obj_names:
            obj_filter = lambda props: props['name'] in obj_names

        # Starting point
        obj_spec = vmodl.query.PropertyCollector.ObjectSpec()
        obj_spec.obj = self.content.viewManager.CreateContainerView(self.content.rootFolder, [obj_type, ], True)
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
        property_spec.type = obj_type
        property_spec.pathSet = list(set(tuple(prop_names) + ('name', )))

        # Create filter specification
        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = [obj_spec]
        filter_spec.propSet = [property_spec]

        # Retrieve properties
        collector = self.session.content.propertyCollector
        objs = collector.RetrieveContents([filter_spec])

        # Filter objects
        objs_and_props = []
        for obj in objs:

            # Compile propeties
            properties = {prop.name: prop.val for prop in obj.propSet}

            # If it fails filter, skip
            if obj_filter and not obj_filter(properties):
                continue

            # Return this one with obj
            properties['obj'] = obj.obj
            objs_and_props.append(properties)

        # If we only need one object, return first
        if only_one:
            if len(objs_and_props) == 1:
                return objs_and_props[0]
            elif len(objs_and_props) > 1:
                raise VMwareException('Found multiple {} objects that match filter'.format(obj_type))
            else:
                raise VMwareException('Could not find {} object that matches filter'.format(obj_type))

        # If we are okay with more, then return whole
        else:
            if len(objs_and_props):
                return objs_and_props
            else:
                raise VMwareException('Unable to find {} objects that match filter'.format(obj_type))

    def add_memory(self, vm_name, add_gb):
        vm = self.get_obj_props(
            obj_names=(vm_name, ),
            prop_names=('config.hardware.memoryMB', 'config.hardware.numCPU', )
        )

        # Need MB (long) and GB value
        new_mb = long(vm['config.hardware.memoryMB'] + (add_gb * 1024))
        new_gb = new_mb / 1024

        spec = vim.vm.ConfigSpec()
        spec.memoryMB = new_mb
        spec.numCPUs = vm['config.hardware.numCPU']

        self.start_task(
            vm['obj'].ReconfigVM_Task(spec=spec),
            success_msg='{} memory now: {:.1f}GB'.format(vm_name, new_gb),
            hint_msg='Hot plug memory may be disabled or limited (see: http://kb.vmware.com/kb/2008405)'
        )

    def get_memory(self, vm_name):
        vm = self.get_obj_props(
            obj_names=(vm_name, ),
            prop_names=('config.hardware.memoryMB', )
        )
        print(
            '{} memory: {:.1f}GB'.format(
                vm_name,
                vm['config.hardware.memoryMB'] / 1024
            )
        )

    def add_cpus(self, vm_name, add_cpu_count):
        vm = self.get_obj_props(
            obj_names=(vm_name, ),
            prop_names=('config.hardware.memoryMB', 'config.hardware.numCPU', )
        )

        new_cpu_count = vm['config.hardware.numCPU'] + add_cpu_count

        spec = vim.vm.ConfigSpec()
        spec.memoryMB = vm['config.hardware.memoryMB']
        spec.numCPUs = new_cpu_count

        self.start_task(
            vm['obj'].ReconfigVM_Task(spec=spec),
            success_msg='{} CPU count now: {}'.format(vm_name, new_cpu_count)
        )

    def get_cpus(self, vm_name):
        vm = self.get_obj_props(
            obj_names=(vm_name, ),
            prop_names=('config.hardware.numCPU', )
        )
        print(
            '{} CPU count: {}'.format(
                vm_name,
                vm['config.hardware.numCPU']
            )
        )

    def get_disks(self, vm_name):
        vm = self.get_obj_props(
            obj_names=(vm_name, ),
            prop_names=('config.hardware.device', )
        )
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

    def human_readable_b(self, bytes):
        for item in ['bytes', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return "%3.1f%s" % (bytes, item)
            bytes /= 1024.0
        return "%3.1f%s" % (bytes, 'TB')

    def get_cluster_datastores(self, cluster, ds_prefix):
        cluster_datastores = self.get_obj_props(
            obj_names=(cluster,),
            prop_names=(
                'datastore',
            ),
            obj_type=vim.ClusterComputeResource,
            only_one=True
        )

        for ds in cluster_datastores['datastore']:
            if not ds.summary.name.startswith(ds_prefix):
                continue

            space_free = self.human_readable_b(ds.summary.freeSpace or 0)
            space_total = self.human_readable_b(ds.summary.capacity)
            space_overprov = (ds.summary.uncommitted or 0) - (ds.summary.freeSpace or 0)
            percent_prov = ((ds.summary.capacity + space_overprov) / float(ds.summary.capacity)) * 100

            print '======================'
            print 'Name: {}'.format(ds.summary.name)
            print 'Space free: {}/{}'.format(space_free, space_total)
            print 'Space provisioned: {:.2f}%'.format(percent_prov)
            print 'VM count: {}'.format(len(ds.vm))

    def summarize_cluster_datastores(self, cluster, ds_prefix):
        cluster_datastores = self.get_obj_props(
            obj_names=(cluster,),
            prop_names=(
                'datastore',
            ),
            obj_type=vim.ClusterComputeResource,
            only_one=True
        )

        ds_prefixes = []
        for ds in cluster_datastores['datastore']:

            # Skip anything not matching prefix
            if not ds.summary.name.startswith(ds_prefix):
                print ds.summary.name
                continue

            # Strip numbers dashes and undercores from end
            this_prefix = ds.summary.name.rstrip('._-1234567890')
            if this_prefix not in ds_prefixes:
                ds_prefixes.append(this_prefix)

        if len(ds_prefixes) == 0:
            print 'No prefixes detected'
        else:
            print 'Datastore prefixes detected:'
            for ds in sorted(ds_prefixes):
                print '- {}'.format(ds)

    def get_a_datastore(self, cluster, ds_prefix, prov_limit, vm_limit):
        cluster_datastores = self.get_obj_props(
            obj_names=(cluster,),
            prop_names=(
                'datastore',
            ),
            obj_type=vim.ClusterComputeResource,
            only_one=True
        )
        acceptable_ds = []
        for ds in cluster_datastores['datastore']:

            # Get name and check if it has prefix
            ds_name = ds.summary.name
            if not ds_name.startswith(ds_prefix):
                continue

            # Get VM count and only continue if under limit
            vm_count = len(ds.vm)
            if vm_count >= vm_limit:
                continue

            # Getting free space now since used for later calc
            free_space = ds.summary.freeSpace or 0

            # Calculate provision percentage
            prov_space = (ds.summary.uncommitted or 0) - free_space
            prov_perc = ((ds.summary.capacity + prov_space) / float(ds.summary.capacity)) * 100
            if prov_perc >= prov_limit:
                continue

            # ASSERT: meets limits

            acceptable_ds.append({
                'name': ds_name,
                'vm_count': vm_count,
                'free_space': free_space,
                'prov_perc': prov_perc,
            })

        #  Check if we found a datastore
        if not len(acceptable_ds):
            raise VMwareException(
                'Could not find a {} datastore with {} perfix that has less than {} VMs and is under {:.0f}% provisioned '.format(
                    cluster,
                    ds_prefix,
                    vm_limit,
                    prov_limit
                )
            )

        # Get DS with highest free space
        highest_free = sorted(acceptable_ds, key=lambda ds: ds['free_space'])[0]['name']
        return highest_free

    def verify_datastore(self, cluster, ds):
        pass

    def get_status(self, vm_name):
        vm = self.get_obj_props(
            obj_names=(vm_name, ),
            prop_names=(
                'config.hardware.numCPU',
                'config.hardware.memoryMB',
                'guest.guestState',
                'guest.toolsStatus',
                'guest.ipAddress',
                'guest.hostName',
                'config.guestFullName',
                'config.version',
                'runtime.bootTime',
                'runtime.powerState',
            )
        )

        print 'Hostname    : {}'.format(vm['guest.hostName'])
        print 'OS          : {}'.format(vm['config.guestFullName'])
        print 'IP Address  : {}'.format(vm['guest.ipAddress'])
        print 'CPU Count   : {}'.format(vm['config.hardware.numCPU'])
        print 'Memory      : {:.1f}GB'.format(vm['config.hardware.memoryMB'] / 1024)
        print 'Power State : {}'.format(vm['runtime.powerState'])
        print 'VM Status   : {}'.format(vm['guest.guestState'])
        print 'Guest Tools : {}'.format(vm['guest.toolsStatus'])
        print 'VM Version  : {}'.format(vm['config.version'])
        if 'runtime.bootTime' in vm:
            boot_time = vm['runtime.bootTime'].astimezone(get_localzone()).strftime('%m/%d/%Y %H:%M')
            print 'Last Boot   : {}'.format(boot_time)

    def destroy(self, vm_name):
        vm = self.get_obj_props(
            obj_names=(vm_name, ),
            prop_names=('runtime.powerState', )
        )

        # If VM on, turn off
        if vm['runtime.powerState'] == vim.VirtualMachinePowerState.poweredOn:
            print 'Turning off VM before deleting...'
            self.start_task(vm['obj'].PowerOff(), success_msg='VM turned off, deleting from disk now...')

        self.start_task(vm['obj'].Destroy(), success_msg='VM {} has been destroyed'.format(vm_name))

    def clone(
        self,
        template_name,
        vm_name,
        cpus,
        memory,
        datacenter_name,
        cluster_name,
        ds_name,
        ip,
        domain,
        dns,
        vlan,
        subnet,
        gateway,
        folder_path=None,
        *args,
        **kwargs
    ):
        # Find objects
        datacenter = self.get_object(vim.Datacenter, datacenter_name)
        cluster = self.get_object(vim.ClusterComputeResource, cluster_name)
        datastore = self.get_object(vim.Datastore, ds_name)
        template_vm = self.get_object(vim.VirtualMachine, template_name)

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

        # Configuration specs
        vmconf = vim.vm.ConfigSpec()
        vmconf.numCPUs = cpus
        vmconf.memoryMB = memory * 1024
        vmconf.cpuHotAddEnabled = True
        vmconf.memoryHotAddEnabled = True

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
        result = self.start_task(
            task,
            task_tag='Cloning',
            success_msg='Cloned in folder {}'.format(folder_path),
            last_task=False
        )

        # Do not continue if we didn't get clone
        if not result:
            return

        # Change networking
        vm = self.get_object(vim.VirtualMachine, vm_name)
        vmconf = vim.vm.ConfigSpec()

        # Get right network
        network = self.get_portgroup(vlan, vm.runtime.host.name)

        # Modify NIC card
        nic = vim.vm.device.VirtualDeviceSpec()
        nic.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        for device in vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualEthernetCard):
                nic.device = device
                break
        nic.device.wakeOnLanEnabled = True
        portgroup_connection = vim.dvs.PortConnection()
        portgroup_connection.portgroupKey = network.key
        portgroup_connection.switchUuid = network.config.distributedVirtualSwitch.uuid
        nic.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
        nic.device.backing.port = portgroup_connection
        nic.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
        nic.device.connectable.startConnected = True
        nic.device.connectable.allowGuestControl = True
        vmconf.deviceChange = [nic, ]

        # Start task
        task = vm.ReconfigVM_Task(vmconf)
        self.start_task(
            task,
            task_tag='Networking',
            success_msg='VIF reconfigured'
        )


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
