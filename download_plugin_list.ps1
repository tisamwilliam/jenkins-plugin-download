$bastion_username = "root"
$bastion_ip_address = "192.168.50.99"

$mac_username = "cluster"
$mac_ip_address = "10.250.75.137"

$ocp_api_url = "https://api.ocp.olg.online.com:6443"

$jenkins_url = "jenkins-jenkins-pv05.apps.ocp.olg.online.com"
$jenkins_version = "2.361.2"

# # 取得Bastion主機與Openshift的帳號密碼
# $openshift_cred = Get-Credential -Message "請輸入Openshift 使用者帳號/密碼(${ocp_api_url})"
# $bastion_remote_control = "ssh $bastion_username@$bastion_ip_address"

# Write-Output "`n[Openshift Bastion]登入Openshift"
# Write-Output "Openshift API Server: ${ocp_api_url}"
# Write-Output "Openshift Username: $($openshift_cred.UserName)"
# Invoke-Expression "$bastion_remote_control oc login --username=$($openshift_cred.UserName) --password=$($openshift_cred.GetNetworkCredential().Password) --server=${ocp_api_url}"

# Write-Output "`n[Openshift Bastion]透過Uert Token向Jenkins API取得套件清單"
# Invoke-Expression "$bastion_remote_control 'curl --header \`"Authorization: Bearer `$(oc whoami -t)\`" -k https://$($jenkins_url)/pluginManager/api/json\?depth\=1'" > jenkins_plugin_list.json

Write-Output "`n[Mac Server]傳送套件清單到Mac主機"
$mac_remote_control = "ssh $mac_username@$mac_ip_address"
# $containerd_cicd_tool_path = "/home/$($mac_username)/jenkins-plugin-download"

# Invoke-Expression "scp jenkins_plugin_list.json $($mac_username)@$($mac_ip_address):$containerd_cicd_tool_path"

# Write-Output "`n[Mac Server]從Git更新Python腳本"
# Invoke-Expression "$mac_remote_control 'cd /home/$($mac_username)/jenkins-plugin-download; git pull'"

Write-Output "`n[Mac Server]執行Python腳本下載套件"
Invoke-Expression "$mac_remote_control 'python3 /home/$($mac_username)/jenkins-plugin-download/jenkins_download_plugin.py ${jenkins_version}'"