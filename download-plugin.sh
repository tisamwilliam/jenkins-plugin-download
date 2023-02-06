#!/bin/bash

nexus_repo_path="http://192.168.50.42:8081/repository/jenkins-plugin/containerd-cicd/dynamic-stable-2.361.2"

curl ${nexus_repo_path}/metadata/plugin_list.txt -o plugin_list.txt

for plugin_name in $(cat plugin_list.txt)
do
    curl ${nexus_repo_path}/${plugin_name}.jpi -o ${plugin_name}.jpi
done