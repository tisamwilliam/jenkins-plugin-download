$bastion_username = "root"
$bastion_ip_address = "192.168.50.99"

$mac_username = "cluster"
$mac_ip_address = "10.250.75.149"

$ocp_api_url = "https://api.ocp.olg.online.com:6443"

$jenkins_url = "jenkins-jenkins-pv05.apps.ocp.olg.online.com"
$jenkins_version = "2.361.2"

$openshift_cred = Get-Credential -Message "Openshift Username/Password(${ocp_api_url}:)"
$bastion_remote_control = "ssh $bastion_username@$bastion_ip_address"

Write-Output "`n[Openshift Bastion] Login Openshift"
Write-Output "Openshift API Server: ${ocp_api_url}"
Write-Output "Openshift Username: $($openshift_cred.UserName)"
Invoke-Expression "$bastion_remote_control oc login --username=$($openshift_cred.UserName) --password=$($openshift_cred.GetNetworkCredential().Password) --server=${ocp_api_url}"

Write-Output "`n[Openshift Bastion] Get Jenkins package list through API"
Invoke-Expression "$bastion_remote_control 'curl --header \`"Authorization: Bearer `$(oc whoami -t)\`" -k https://$($jenkins_url)/pluginManager/api/json\?depth\=1'" > jenkins_plugin_list_utf16.json

Write-Output "`n[Mac Server] Send Jenkins package list to Mac server"
$mac_remote_control = "ssh $mac_username@$mac_ip_address"
$containerd_cicd_tool_path = "/home/$($mac_username)/jenkins-plugin-download"

Invoke-Expression "scp jenkins_plugin_list_utf16.json $($mac_username)@$($mac_ip_address):$containerd_cicd_tool_path"

$gitlab_cred = Get-Credential -Message "Gitlab Username/Password:"
Write-Output "`n[Mac Server] Git pull"
Invoke-Expression "$mac_remote_control 'cd $containerd_cicd_tool_path; git pull https://$($gitlab_cred.Username):$($gitlab_cred.GetNetworkCredential().Password)@gitlab.com/upgrade_splunk_automation/splunk_upgrade_automation.git'"

Write-Output "`n[Mac Server] Execute Python script"
Invoke-Expression "$mac_remote_control 'bash $containerd_cicd_tool_path/execute_python_script.sh $containerd_cicd_tool_path $jenkins_version'"