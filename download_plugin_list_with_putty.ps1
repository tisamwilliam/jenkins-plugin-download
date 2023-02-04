$bastion_ip_address="192.168.50.99"
$mac_ip_address="10.250.75.137"

$ocp_api_url="https://api.ocp.olg.online.com:6443"

$jenkins_url="jenkins-jenkins-pv05.apps.ocp.olg.online.com"
$jenkins_version="2.361.2"

# 取得Bastion主機與Openshift的帳號密碼
$bastion_cred = Get-Credential -Message "請輸入Bastion主機 登入帳號/密碼"
$openshift_cred = Get-Credential -Message "請輸入Openshift 使用者帳號/密碼(${ocp_api_url})"
$bastion_remote_control = "plink -no-antispoof -l $($bastion_cred.UserName) -pw $($bastion_cred.GetNetworkCredential().Password) $($bastion_ip_address)"

Write-Output "`n登入Openshift"
Write-Output "Openshift API Server: ${ocp_api_url}"
Write-Output "Openshift Username: $($openshift_cred.UserName)"
Invoke-Expression "$bastion_remote_control oc login --username=$($openshift_cred.UserName) --password=$($openshift_cred.GetNetworkCredential().Password) --server=${ocp_api_url}"

Write-Output "`n透過Jenkins API取得套件清單"
Invoke-Expression "$bastion_remote_control 'curl --header \`"Authorization: Bearer `$(oc whoami -t)\`" -k https://$($jenkins_url)/pluginManager/api/xml\?depth\=1'" > jenkins_plugin_list.xml

Write-Output "`n傳送套件清單到Mac主機"
$mac_cred = Get-Credential -Message "請輸入Mac主機 登入帳號/密碼"
$mac_remote_control = "plink -no-antispoof -pw $($mac_cred.GetNetworkCredential().Password) -l $($mac_cred.UserName) $($mac_ip_address)"

pscp -l $mac_cred.UserName -pw $mac_cred.GetNetworkCredential().Password  jenkins_plugin_list.xml ${mac_ip_address}:"/home/$($mac_cred.UserName)/"

Write-Output "`n從Git更新Python腳本"
Invoke-Expression "$mac_remote_control 'cd /home/$($mac_cred.UserName)/jenkins-plugin-download; git pull'"

Write-Output "`n執行Python腳本下載套件"
Invoke-Expression "$mac_remote_control 'python3 /home/$($mac_cred.UserName)/jenkins-plugin-download/jenkins_download_plugin.py ${jenkins_version}'"