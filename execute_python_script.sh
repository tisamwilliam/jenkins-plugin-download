#! /bin/bash

total_retry_time=5
counting_start=1
execute_python_command="python3 $1/jenkins_download_plugin.py $2"

if file -b --mime-encoding jenkins_plugin_list_utf16.json | grep -q "utf-16le" ; then
    iconv -f utf-16 -t us-ascii $1/jenkins_plugin_list_utf16.json > jenkins_plugin_list.json
fi 

for retry_time in $(eval echo "{$counting_start..$total_retry_time}")
do
    echo "Run python script [ ${retry_time} / ${total_retry_time} times ] "
    $execute_python_command

    if [ $? -eq 0 ]; then
         break
    fi
done