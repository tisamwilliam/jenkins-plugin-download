#! /bin/bash

total_retry_time=5
counting_start=1
execute_python_command="python3 $1/jenkins_download_plugin.py $2"

for retry_time in $(eval echo "{$counting_start..$total_retry_time}")
do
    echo "Run python script [ ${retry_time} / ${total_retry_time} times ] "
    $execute_python_command

    if [ $? -eq 0 ]; then
         break
    fi
done