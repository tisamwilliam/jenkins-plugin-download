import os
import json
import urllib
import base64
import requests as re
import os
import hashlib
import time

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
    
class plugin_data():
    def plugin_info(self,):
        plugin_depend_url = f"https://updates.jenkins.io/dynamic-stable-2.361.2/update-center.actual.json"

        return json.loads(re.get(plugin_depend_url).text)

    def get_plugin_info(self, plugin_json, plugin_name):
        plugin_info_dict = {
            "plugin_name": plugin_name,
            "plugin_download_url": plugin_json["plugins"][plugin_name]["url"].replace("updates.jenkins.io/download","sg.mirror.servanamanaged.com/jenkins"),
            "plugin_sha256": base64.decodebytes(plugin_json["plugins"][plugin_name]["sha256"].encode('utf-8')),
            "plugin_size": plugin_json["plugins"][plugin_name]["size"],
            "plugin_save_path": f"{plugin_name}.hpi"
        }
        
        return plugin_info_dict
    
class part_download_function():
    def download_control(self, plugin_info, batch_size):
        file_batch_size_range = list()
        end_byte = -1

        while end_byte < plugin_info["plugin_size"]:
            if end_byte+batch_size < plugin_info["plugin_size"]:
                file_batch_size_range.append([end_byte+1, end_byte+batch_size+1])
                end_byte = end_byte+batch_size+1
            else:
                file_batch_size_range.append([end_byte+1, plugin_info["plugin_size"]])
                end_byte = plugin_info["plugin_size"]

        with open(plugin_info_dict["plugin_save_path"], "wb") as f:
            pass        
        
        for download_range_list in file_batch_size_range:
            
            headers = {"Range": f"bytes={download_range_list[0]}-{download_range_list[1]}"}
            plugin_info_dict["header"] = headers
            
            part_plugin_file = self.download_retry(plugin_info_dict)
            time.sleep(1)

        return plugin_info_dict["plugin_save_path"], plugin_info_dict["plugin_sha256"]
    
    @update_and_retry(retry_times=5, delay_time=5)            
    def download_retry(self, plugin_info_dict):
        """
            檔案下載,並呼叫雜湊值檢查
            如未通過會透過return boolen觸發update_and_retry重新下載並再次檢查
        """        
        part_plugin_file = re.get(plugin_info_dict["plugin_download_url"], headers=plugin_info_dict["header"])
        
        if len(part_plugin_file.content) == int(part_plugin_file.headers["Content-Length"]):  
            with open(plugin_info_dict["plugin_save_path"], "ab") as plugin_file:    
                plugin_file.write(part_plugin_file.content)
                
            print(f"Part Download Succees, File Content: {len(part_plugin_file.content)}, Header Content Length: {part_plugin_file.headers['Content-Length']}")
            return True, plugin_info_dict
        
        print(f"Part Download Failed, File Content: {len(part_plugin_file.content)}, Header Content Length: {part_plugin_file.headers['Content-Length']}")
        return False, plugin_info_dict
    
 
class check_file():
    def check_sha256(self, jenkins_plugin_file, jenkins_plugin_sha256):
        file_sha256 = self.generate_sha256(jenkins_plugin_file)

        if jenkins_plugin_sha256 == file_sha256.digest() or jenkins_plugin_sha256 == file_sha256.hexdigest():
            print("Checksum Pass")
        else:
            print("Checksum False")

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
    
    
if __name__ == "__main__":
    plugin_data_class = plugin_data()
    plugin_json = plugin_data_class.plugin_info()
    
    for plugin_name in ["blueocean-core-js"]:
        
        # get plugin info
        plugin_info_dict = plugin_data_class.get_plugin_info(plugin_json, plugin_name)
        
        # download type
        download_function_class = part_download_function() 
        plugin_path, _ = download_function_class.download_control(plugin_info_dict, 1048576)

        # file checksum
        check_file_class = check_file()
        check_file_class.check_sha256(plugin_path, plugin_info_dict["plugin_sha256"])
        