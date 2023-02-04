import os
import sys
import time
import json
import base64
import logging
import hashlib
import requests as re
from urllib3.exceptions import InsecureRequestWarning

# 關閉requests SSL檢查錯誤輸出
re.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

def syslog_config():
    """
        設定執行日誌格式,並同時輸出syslog和stdout
    """
    formatter = logging.Formatter(fmt="%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s",
                                  datefmt='%Y-%m-%d %H:%M:%S')
    
    syslog_handler = logging.FileHandler("jenkins_download_plugin.log", mode="a")
    syslog_handler.setFormatter(formatter)
    
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    logger.addHandler(syslog_handler)
    logger.addHandler(stdout_handler)
    
    return logger

def update_and_retry(retry_times, delay_time):
    def retry_func(func):
        def wrapper(self, argc_list):
            for _ in range(retry_times):
                update_is_done, argc_list = func(self, argc_list)
                if update_is_done:
                    return True, argc_list
                if delay_time:
                    time.sleep(delay_time)
        return wrapper
    return retry_func

def summary_output(update_plugin_list, upload_plugin_list, upload_fail_plugin_list):
    logger.info("=====================================================================")
    logger.info(f"更新依賴套件後須下載數量: {len(update_plugin_list)}")
    logger.info(f"套件下載成功數量: {len(upload_plugin_list)}, 下載失敗數量: {len(update_plugin_list)-len(upload_plugin_list)}")
    logger.info(f"套件上傳成功數量: {len(upload_plugin_list)-len(upload_fail_plugin_list)}, 上傳失敗數量: {len(upload_fail_plugin_list)}")
    logger.info("=====================================================================")  

class download_prepare():
    """
        腳本執行環境檢查、Jenkins版本檢查與套件依賴更新
    """
    def __init__(self, script_varible):
        self.update_jenkins_version = script_varible["update_jenkins_version"]
        self.temp_download_folder = script_varible["temp_download_folder"]
        self.internet_proxy = script_varible["internet_proxy"]
        self.quay_jenkins_version = script_varible["quay_jenkins_version"]

    def check_update_version_is_avaliable(self):
        """
            取得在Jenkins Update Server可以更新的版本, 根據穩定版本(stableCore)與每周更新版本(weeklyCore)加入dynamic-stable與dynamic前綴
        """
        update_server_available_version = eval(re.get("https://updates.jenkins.io/tiers.json", proxies=self.internet_proxy, verify=False).text)

        if self.update_jenkins_version in update_server_available_version["stableCores"]:
            logger.info(f"[Version Confirm] confirm to download plugin with jenkins version: {self.update_jenkins_version}")
            return "dynamic-stable-"+self.update_jenkins_version
        elif self.update_jenkins_version in update_server_available_version["weeklyCores"] :
            logger.info(f"[Version Confirm] confirm to download plugin with jenkins version: {self.update_jenkins_version}")
            return "dynamic-"+self.update_jenkins_version
        else:
            logger.warning(f"jenkins update server no longer supports version {self.update_jenkins_version}")
            sys.exit()

    def get_update_version_dependent_plugin_list(self, jenkins_maintain_cycle_version):
        """
            從Jenkins Update Server取得指定版本的最新套件與依賴套件
        """
        plugin_depend_url = f"https://updates.jenkins.io/{jenkins_maintain_cycle_version}/update-center.actual.json"

        self.update_plugin_dependent_json = json.loads(re.get(plugin_depend_url, proxies=self.internet_proxy, verify=False).text)

        return self.update_plugin_dependent_json

    def check_dest_folder_ready(self):
        if not os.path.isdir(self.temp_download_folder):
            os.mkdir(self.temp_download_folder)

    @update_and_retry(retry_times=5, delay_time=0)
    def update_dependency_plugin(self, update_plugin_list):
        """
            檢查套件是否被棄用,並新增套件的依賴套件
            根據return boolen觸發update_and_retry重複執行,直到沒有新增依賴套件
        """
        plugin_len = len(update_plugin_list)
        tmp_update_plugin_list = update_plugin_list.copy()

        deprecations_list = list(self.update_plugin_dependent_json['deprecations'].keys())
        deorecation_plugin_need_list = list()

        for plugin_name in update_plugin_list:
            try:
                for dependency_item in self.update_plugin_dependent_json["plugins"][plugin_name]["dependencies"]:
                    if not dependency_item['optional'] and dependency_item['name'] not in update_plugin_list:
                        tmp_update_plugin_list.append(dependency_item['name'])
                        logger.info(f"[New Plugin] plugin: '{plugin_name}' need dependency plugin: '{dependency_item['name']}'")
                        
                    if dependency_item['name'] in deprecations_list:
                        deorecation_plugin_need_list.append(dependency_item['name'])
                        logger.warning(f"[Ready For Deprecation] '{dependency_item['name']}' is in deprecation list, but it's still use by '{plugin_name}'")
            except Exception as e:
                logger.warning(f"[Plugin Not Found] {plugin_name} is not avaliable to download, error message: {e}")
                tmp_update_plugin_list.remove(plugin_name)

        for plugin_name in update_plugin_list:
            if plugin_name in self.update_plugin_dependent_json['deprecations'] and plugin_name not in deorecation_plugin_need_list:
                tmp_update_plugin_list.remove(plugin_name)
                logger.warning(f"[Deprecation Plugin] {plugin_name}")

        tmp_update_plugin_list = list(set(tmp_update_plugin_list))

        if plugin_len != len(tmp_update_plugin_list):
            return False, tmp_update_plugin_list
        else:
            return True, tmp_update_plugin_list


class download_jenkins_plugin(download_prepare):
    """
        下載套件與檢查套件雜湊值
    """
    def __init__(self, update_plugin_dependent_json):
        super(download_jenkins_plugin, self).__init__(script_varible)
        self.update_plugin_dependent_json = update_plugin_dependent_json

    def plugin_download_control(self, update_plugin_list):
        """
            套件下載流程控制,呼叫下載套件與檢查雜湊值的功能
            只回傳有成功下載的清單供Nexus上傳
        """
        download_retry_list = update_plugin_list.copy()

        for loop_index, plugin_name in enumerate(update_plugin_list):
            plugin_info_dict = self.get_plugin_info(plugin_name)

            if os.path.isfile(plugin_info_dict["plugin_save_path"]) and self.check_sha256(plugin_info_dict["plugin_save_path"], plugin_info_dict["plugin_sha256"]):
                download_retry_list.remove(plugin_name)
                continue

            try:
                finish_download, _ = self.download_retry(plugin_info_dict)

                if finish_download:
                    download_retry_list.remove(plugin_name)
                    logger.info(f"[Download Success] {loop_index+1}/{len(update_plugin_list)} {plugin_info_dict['plugin_name']}")
            except Exception as e:
                logger.warning(f"[Download Failed] {plugin_name}, error message: {e}")

        return list(set(update_plugin_list) - set(download_retry_list))

    @update_and_retry(retry_times=5, delay_time=5)
    def download_retry(self, plugin_info_dict):
        """
            檔案下載,並呼叫雜湊值檢查
            如未通過會透過return boolen觸發update_and_retry重新下載並再次檢查
        """
        dowload_plugin_file = re.get(plugin_info_dict["plugin_download_url"], proxies=self.internet_proxy, verify=False)

        with open(plugin_info_dict["plugin_save_path"], "wb") as plugin_file:    
            plugin_file.write(dowload_plugin_file.content)

        if self.check_sha256(plugin_info_dict["plugin_save_path"], plugin_info_dict["plugin_sha256"]):
            return True, plugin_info_dict
        else:
            logger.warning(f"[Download Retry] {plugin_info_dict['plugin_name']} retry")
            return False, plugin_info_dict

    def get_plugin_info(self, plugin_name):
        """
            根據套件名稱回傳基本資訊,包含套件名稱,下載位置,儲存位置,雜湊值
            來源為Jenkins Update Server提供的Plugin Json
        """
        plugin_info_dict = {
            "plugin_name": plugin_name,
            "plugin_download_url": self.update_plugin_dependent_json["plugins"][plugin_name]["url"],
            "plugin_save_path": f"{self.temp_download_folder}/{plugin_name}.hpi",
            "plugin_sha256": base64.decodebytes(self.update_plugin_dependent_json["plugins"][plugin_name]["sha256"].encode('utf-8'))
        }
        return plugin_info_dict

    def check_sha256(self, jenkins_plugin_file, jenkins_plugin_sha256):
        file_sha256 = self.generate_sha256(jenkins_plugin_file)

        if jenkins_plugin_sha256 == file_sha256.digest() or jenkins_plugin_sha256 == file_sha256.hexdigest():
            return True
        else:
            return False

    def generate_sha256(self, jenkins_plugin_file):
        BufferSize = 65536
        file_sha256 = hashlib.sha256()

        with open(jenkins_plugin_file, "rb") as plugin_file:
            while True:
                data = plugin_file.read(BufferSize)
                if not data:
                    break
                file_sha256.update(data)

        return file_sha256

class action_on_nexus(download_jenkins_plugin):
    """
        套件上傳Nexus與雜湊值檢查
    """
    def __init__(self, nexus_connect_info):
        super(action_on_nexus, self).__init__(script_varible)
        self.nexus_server = nexus_connect_info["nexus_server"]
        self.nexus_auth = nexus_connect_info["nexus_auth"]
        self.nexus_jenkins_repository = nexus_connect_info["nexus_jenkins_repository"]
        self.nexus_component_api = f"{self.nexus_server}/service/rest/v1/components"

    def get_both_jenkins_version_plugin_list(self):
        """
            到Nexus抓取現有Jenkins套件清單,和到Github抓取目標更新版本套件清單
            新舊版本套件清單做聯集
        """
        image_source_code_github_url = f"https://raw.githubusercontent.com/openshift/jenkins/release-{self.quay_jenkins_version}/2/contrib/openshift/bundle-plugins.txt"
        image_plugin_list_file = re.get(image_source_code_github_url, proxies=self.internet_proxy, verify=False).text.strip().split("\n")
        image_plugin_list = [plugin_name.split(":")[0] for plugin_name in image_plugin_list_file if "#" not in plugin_name]
        
        current_version_json_content = json.load(open("./jenkins_plugin_list.json", 'r', encoding="utf-16"))
        current_version_plugin_list = [ plugin_item["shortName"] for plugin_item in current_version_json_content["plugins"] ]

        return list(set(image_plugin_list).union(current_version_plugin_list))

    @update_and_retry(retry_times=5, delay_time=0)
    def upload_to_nexus(self, upload_plugin_list):
        """
            將套件上傳到Nexus,完成後呼叫檢查Nexus雜湊值功能
            如有檢查失敗會將失敗清單重新帶入本功能再次上傳,重複次數根據update_and_retry參數
        """
        upload_plugin_list_len = len(upload_plugin_list)

        for loop_index, plugin_name in enumerate(upload_plugin_list):
            params = (("repository", self.nexus_jenkins_repository),)
            data = {
                "raw.directory": f"/containerd-ci/{jenkins_maintain_cycle_version}",
                "raw.asset1.filename ": f"{plugin_name}.hpi"
            }
            files = {
                "raw.asset1": (f"{plugin_name}.hpi", open(f"{self.temp_download_folder}/{plugin_name}.hpi" , "rb" ))
            }

            try:
                upload_response = re.post(f"http://{self.nexus_component_api}", params=params, data=data, files=files, auth=self.nexus_auth)

                if upload_response.status_code == 204:
                    logger.info(f"[Upload Success Without Check] {loop_index+1}/{upload_plugin_list_len} {plugin_name}")
                else:
                    logger.warning(f"[Upload Failed] {plugin_name}, with wrong http code")
                    logger.warning(f"[Upload Failed] {upload_response.text}")
            except Exception as e:
                logger.warning(f"[Upload Failed] {plugin_name}, error message: {e}")

        upload_plugin_list = self.check_upload_checksum(upload_plugin_list)

        if len(upload_plugin_list):
            return False, upload_plugin_list
        else:
            return True, upload_plugin_list

    def check_upload_checksum(self, upload_plugin_list):
        """
            取得Nexus API回傳資訊,比對上傳Nexus套件與Python下載套件的雜湊值
        """
        artifact_list = self.get_nexus_artifact()
        temp_upload_plugin_list = upload_plugin_list.copy()

        for loop_index, nexus_artifact in enumerate(artifact_list):
            plugin_filename = nexus_artifact['name'].split("/")[-1]

            if self.check_sha256(f"{self.temp_download_folder}/{plugin_filename}", nexus_artifact["assets"][0]["checksum"]['sha256']):
                temp_upload_plugin_list.remove(plugin_filename.replace(".hpi", ""))
                logger.info(f"[Upload Checksum Success] {loop_index+1}/{len(upload_plugin_list)} {nexus_artifact['name']}")
            else:
                logger.warning(f"[Upload Checksum Failed] {nexus_artifact['name']}")
            
        return temp_upload_plugin_list

    def get_nexus_artifact(self):
        """
            呼叫Nexus API取得已上傳套件的名稱與雜湊值
        """
        artifact_list = list()
        nexus_jenkins_repo_url = f"http://{self.nexus_component_api}?repository={self.nexus_jenkins_repository}"

        nexus_artifact_response = eval(re.get(nexus_jenkins_repo_url, auth=self.nexus_auth).text.replace("null", "\"null\""))
        artifact_list += nexus_artifact_response["items"]

        while nexus_artifact_response['continuationToken']!="null":
            nexus_artifact_response = eval(re.get(f"{nexus_jenkins_repo_url}&continuationToken={nexus_artifact_response['continuationToken']}", auth=self.nexus_auth, verify=False).text.replace("null", "\"null\""))
            artifact_list += nexus_artifact_response["items"]

        for nexus_artifact in artifact_list:
            if nexus_artifact["group"] != f"/v{self.update_jenkins_version}" or "hpi" not in nexus_artifact["name"]:
                artifact_list.remove(nexus_artifact)

        return artifact_list

if __name__ == '__main__':
    script_varible = {
        "update_jenkins_version": sys.argv[1],
        "temp_download_folder": f"./jenkins_{sys.argv[1]}_plugin",
        "quay_jenkins_version": "4.13",
        "internet_proxy": {"https": "192.168.50.98:3128"},
    }

    nexus_connect_info = {
        "nexus_server": "192.168.50.42:8081",
        "nexus_auth": ("admin", "sk89835049"),
        "nexus_jenkins_repository": "jenkins-plugin"
    }

    # 設定日誌格式與輸出方式
    logger = syslog_config()

    # Jenkins版本檢查與取得套件清單
    download_prepare_class = download_prepare(script_varible)

    jenkins_maintain_cycle_version = download_prepare_class.check_update_version_is_avaliable()
    download_prepare_class.check_dest_folder_ready()
    update_plugin_dependent_json = download_prepare_class.get_update_version_dependent_plugin_list(jenkins_maintain_cycle_version)

    download_jenkins_plugin_class = download_jenkins_plugin(update_plugin_dependent_json)
    action_on_nexus_class = action_on_nexus(nexus_connect_info)
    
    current_plugin_list = action_on_nexus_class.get_both_jenkins_version_plugin_list()

    # 更新套件依賴項
    _, update_plugin_list = download_prepare_class.update_dependency_plugin(current_plugin_list)

    # 下載Jenkins套件與失敗重試
    upload_plugin_list = download_jenkins_plugin_class.plugin_download_control(update_plugin_list)

    # 上傳套件到Nexus
    _, upload_fail_plugin_list = action_on_nexus_class.upload_to_nexus(upload_plugin_list, jenkins_maintain_cycle_version)
    
    # 執行結果輸出
    summary_output(update_plugin_list, upload_plugin_list, upload_fail_plugin_list)