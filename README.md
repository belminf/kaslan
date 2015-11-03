#kaslan
pyVmomi based CLI for common VMware tasks.

##Install
### Requires
* Python 2.7+
* setuptools 0.9.8+

### Setup
    python setup.py install

Use `kaslan.yaml` for configuration. Search preference:

1. Current working directory (`./kaslan.yaml`)
2. Home directory(`~/.kaslan.yaml`)
3. System config (`/etc/kaslan.yaml`)

##Commands
For more detailed help: `kaslan --help`

###`clone`
Clones a template to a new VM.

##### Features
* Uses short aliases for template names.
* (Optional) Determines IP address if DNS record matche VM name and domain.
* (Optional) Uses ping to verify that IP address is not in use before proceeding.
* (Optional) Determines appropriate network based on IP address and kaslan configuration.

##### Examples
* `kaslan clone --cpu=2 RHEL7 ds_cluster_1 syslog_server01`
* `kaslan clone --ip=192.168.4.81 RHEL5 ds_linux_04 puppetmaster_05` 
