# 參數調整 - 通用參數
$jenkins_version = "2.361.2"
$mac_username = "root"
$mac_ip_address = "10.250.75.160"

# 參數調整 - Openshift Jenkins
$ocp_domain = "ocp.olg.online.com"
$ocp_jenkins_url = "jenkins-jenkins-pv05.apps.ocp.olg.online.com"

# 參數調整 - VM Jenkins
$vm_jenkins_url = "10.250.75.132:8080"

function request_ocp_plugin_list {
    param (
        [String]$base64_creds
    )
    $request = (curl.exe --header "Authorization: Basic ${base64_creds}" --header "X-CSRF-Token: none" -ksI "https://oauth-openshift.apps.${ocp_domain}/oauth/authorize?client_id=openshift-challenging-client&response_type=token")

    $user_token = $request | Select-String -Pattern '(?<=access_token=)[^&]+' -AllMatches | Foreach-Object {$_.Matches} | Foreach-Object {$_.Value}

    curl.exe --header "Authorization: Bearer ${user_token}" -k "https://${ocp_jenkins_url}/pluginManager/api/json?depth=1" | Out-File jenkins_plugin_list_utf16.json
}

function request_vm_plugin_list {
    param (
        [String]$base64_creds
    )
    curl.exe --header "Authorization: Basic ${base64_creds}" -k "http://${vm_jenkins_url}/pluginManager/api/json?depth=1" | Out-File jenkins_plugin_list_utf16.json
}

function main {
    $choices = "ocp", "vm"
    $platform_selected = Read-Host "Please Jenkins Platform: $($choices -join ', ')"
    if (-not $choices.Contains($platform_selected)) {
        Write-Host "Invalid option: $platform_selected"
        return
    }
    $credential = Get-Credential -Message "Enter Jenkins Login Authentication"
    $username = $credential.UserName
    $password = $credential.GetNetworkCredential().password

    $base64_creds = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${username}:${password}"))

    if ($platform_selected -eq "ocp") {
        request_ocp_plugin_list -base64_creds ${base64_creds}
    } else {
        request_vm_plugin_list -base64_creds ${base64_creds}
    }

    Write-Output "`n[Mac Server] Send Jenkins package list to Mac server"
    $mac_remote_control = "ssh $mac_username@$mac_ip_address"
    $containerd_cicd_tool_path = "/home/$($mac_username)/splunk_upgrade_automation"
    Invoke-Expression "scp jenkins_plugin_list_utf16.json $($mac_username)@$($mac_ip_address):$containerd_cicd_tool_path"

    Write-Output "`n[Mac Server] Git pull"
    $gitlab_cred = Get-Credential -Message "Gitlab Username/Password:"
    $gitlab_cred_password =  [System.Web.HttpUtility]::UrlEncode($gitlab_cred.GetNetworkCredential().Password)

    Invoke-Expression "$mac_remote_control 'cd $containerd_cicd_tool_path; git pull https://$($gitlab_cred.UserName):$($gitlab_cred_password)@gitlab.com/upgrade_splunk_automation/splunk_upgrade_automation.git'"

    Write-Output "`n[Mac Server] Execute Python script"
    Invoke-Expression "$mac_remote_control 'bash $containerd_cicd_tool_path/execute_python_script.sh $containerd_cicd_tool_path $jenkins_version'"
}

main