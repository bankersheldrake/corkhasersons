#!/bin/bash
while getopts name:start:stop:watch:restart flag
do
    case "${flag}" in
        name) SERVICE_NAME=${OPTARG};;
        start) STARTCOMMAND=${OPTARG};;
        stop) STOPCOMMAND=${OPTARG};;
        watch) WATCHFOLDERS=${OPTARG};;
        restart) RESTARTTIME=${OPTARG};;
    esac
done


echo '<table>
\n<tr>
\n<td> </td> 
\n<td> Prod </td> 
\n</tr>
\n<tr>
\n<td> Running on </td> 
\n<td> 
\n    
\n[[raspberrypi4|HOME/raspberrypi4]] 
\n    
\n</td> 
\n
\n</tr>
\n<tr>
\n<td> Service Config </td>
\n<td> 
\n    
\n<table>
\n<tr>
\n<td> Type </td> 
\n<td> service </td>
\n</tr>
\n<tr>
\n<td> Auto-Restart </td> 
\n<td> '${RESTARTTIME}' </td>
\n</tr>
\n<tr>
\n<td> Watch Folders </td> 
\n<td> 
\n<ul>
\n'${WATCHFOLDERS/;/"</li>\n<li>"}'\n
\n</ul>
\n</td>
\n</tr>
\n</table>
\n    
\n</td>
\n
\n
\n</tr>
\n    
\n
\n    
\n<tr>
\n<td> Service Status </td> 
\n<td> 
\n
\n```shell
\nsudo service '${SERVICE_NAME}' status
\nsudo service '${SERVICE_NAME}'-watcher status
\n```
\n
\n</td>
\n</tr>
\n<tr>
\n<td> Manual Start </td> 
\n<td> 
\n
\n```shell
\n/bin/bash /usr/services/'${SERVICE_NAME}'/start.sh
\n```
\n
\n</td>
\n
\n</tr>
\n    
\n<tr>
\n<td> CLI Run </td>
\n<td> 
\n        
\n```shell
\n'${STARTCOMMAND}'
\n```
\n
\n</td>
\n
\n</tr>
\n<tr>
\n<td> Service Log </td> 
\n<td>
\n
\n```shell
\ntail -f /var/log/'${SERVICE_NAME}'_service.log
\n```
\n
\n</td> 
\n
\n</tr>
\n</table>'

