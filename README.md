#kaslan
pyVmomi based CLI for common VMware tasks.


##Requirements
* Python 2.7+

##Install
 pip install -r requirements.txt

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
