#!/bin/bash
i=1;
for param in "$@" 
do
    case $param in
        --name) paramname=$param;;
        --start) paramname=$param;;
        --stop) paramname=$param;;
        --watch) paramname=$param;;
        --restart) paramname=$param;;
        *)
            if [ -n $paramname ]
            then
                case $paramname in
                    --name) SERVICE_NAME=$param;;
                    --start) STARTCOMMAND=$param;;
                    --stop) STOPCOMMAND=$param;;
                    --watch) WATCHFOLDERS=$param;;
                    --restart) RESTARTTIME=$param;;
                esac
            fi
            paramname=''
            ;;
    esac
    i=$((i + 1));
done

mkdir /usr/services
mkdir "/usr/services/${SERVICE_NAME}"
echo Make the service start and stop bash scripts
echo -en '#!/bin/bash\n'\
    ''${STARTCOMMAND}' > /var/log/'${SERVICE_NAME}'_service.log 2>&1' > "/usr/services/${SERVICE_NAME}/start.sh"
echo -en '#!/bin/bash\n'\
    'pkill -f "'${SERVICE_NAME}'\/start.sh";\n'\
    'pkill -f "'${STOPCOMMAND}'"; echo service stopped  > /var/log/'${SERVICE_NAME}'_service.log 2>&1' > "/usr/services/${SERVICE_NAME}/stop.sh" 
chmod a+x "/usr/services/${SERVICE_NAME}/start.sh"
chmod a+x "/usr/services/${SERVICE_NAME}/stop.sh"
echo Make the service daemon definition
echo -en '[Unit]\n'\
    'Description='${SERVICE_NAME}' service\n'\
    'After=network.target\n'\
    '\n'\
    '[Service]\n'\
    'Type=simple\n'\
    'ExecStart=/bin/bash /usr/services/'${SERVICE_NAME}'/start.sh\n'\
    'ExecStop=/bin/bash /usr/services/'${SERVICE_NAME}'/stop.sh\n'\
    'Restart=always\n'\
    'RestartSec='${RESTARTTIME}'\n'\
    'TimeoutSec=60\n'\
    'RuntimeMaxSec=infinity\n'\
    'PIDFile=/tmp/'${SERVICE_NAME}'.pid\n'\
    '\n'\
    '[Install]\n'\
    'WantedBy=multi-user.target' > "/etc/systemd/system/${SERVICE_NAME}.service"
echo Make the srv-watcher.service daemon definition
if [ "$WATCHFOLDERS" != "" ]; 
then 
    echo -en '[Unit]\n'\
    'Description='${SERVICE_NAME}' restarter\n'\
    'After=network.target\n'\
    '\n'\
    '[Service]\n'\
    'Type=oneshot\n'\
    'ExecStart=systemctl restart '${SERVICE_NAME}'.service\n'\
    '\n'\
    '[Install]\n'\
    'WantedBy=multi-user.target' > "/etc/systemd/system/${SERVICE_NAME}-watcher.service"; 
fi
echo Make the srv-watcher.path daemon definition
if [ "$WATCHFOLDERS" != "" ]; 
then 
    echo -en '[Path]
    '${WATCHFOLDERS//;/"\nPathModified="}'\n'\
    '\n'\
    '[Install]\n'\
    'WantedBy=multi-user.target' > "/etc/systemd/system/${SERVICE_NAME}-watcher.path"; 
fi;
echo enable the service daemon
systemctl enable "/etc/systemd/system/${SERVICE_NAME}.service"
if [ "$WATCHFOLDERS" != "" ]; 
then 
    echo enable the watch daemon
    systemctl enable "/etc/systemd/system/${SERVICE_NAME}-watcher.service"; 
    echo start the watch daemon
    systemctl start "${SERVICE_NAME}-watcher.service";
fi
echo reload the deamon
systemctl daemon-reload
touch "/var/log/${SERVICE_NAME}_service.log"
chmod 776 "/var/log/${SERVICE_NAME}_service.log"

echo sudo rm "/usr/services/${SERVICE_NAME}/start.sh"
echo sudo rm "/usr/services/${SERVICE_NAME}/stop.sh"
echo sudo rm "/etc/systemd/system/${SERVICE_NAME}.service"
echo sudo rm "/etc/systemd/system/${SERVICE_NAME}-watcher.service"
echo sudo rm "/etc/systemd/system/${SERVICE_NAME}-watcher.path"
echo sudo rm "/var/log/${SERVICE_NAME}_service.log"
echo sudo systemctl daemon-reload

echo -en '<table>\n'\
'<tr>\n'\
'<td> </td> \n'\
'<td> Prod </td> \n'\
'</tr>\n'\
'<tr>\n'\
'<td> Running on </td> \n'\
'<td> \n'\
'\n'\
'[[raspberrypi4|HOME/raspberrypi4]] \n'\
'\n'\
'</td> \n'\
'\n'\
'</tr>\n'\
'<tr>\n'\
'<td> Service Config </td>\n'\
'<td> \n'\
'\n'\
'<table>\n'\
'<tr>\n'\
'<td> Type </td> \n'\
'<td> service </td>\n'\
'</tr>\n'\
'<tr>\n'\
'<td> Auto-Restart </td> \n'\
'<td> '${RESTARTTIME}' </td>\n'\
'</tr>\n'\
'<tr>\n'\
'<td> Watch Folders </td> \n'\
'<td> \n'\
'<ul>\n'\
''${WATCHFOLDERS//;/"</li>\n<li>"}'\n\n'\
'</ul>\n'\
'</td>\n'\
'</tr>\n'\
'</table>\n'\
'\n'\
'</td>\n'\
'\n'\
'\n'\
'</tr>\n'\
'\n'\
'\n'\
'\n'\
'<tr>\n'\
'<td> Service Status </td> \n'\
'<td> \n'\
'\n'\
'```shell\n'\
'sudo service '${SERVICE_NAME}' status\n'\
'sudo service '${SERVICE_NAME}'-watcher status\n'\
'```\n'\
'\n'\
'</td>\n'\
'</tr>\n'\
'<tr>\n'\
'<td> Manual Start </td> \n'\
'<td> \n'\
'\n'\
'```shell\n'\
'/bin/bash /usr/services/'${SERVICE_NAME}'/start.sh\n'\
'```\n'\
'\n'\
'</td>\n'\
'\n'\
'</tr>\n'\
'\n'\
'<tr>\n'\
'<td> CLI Run </td>\n'\
'<td> \n'\
'\n'\
'```shell\n'\
''${STARTCOMMAND}'\n'\
'```\n'\
'\n'\
'</td>\n'\
'\n'\
'</tr>\n'\
'<tr>\n'\
'<td> Service Log </td> \n'\
'<td>\n'\
'\n'\
'```shell\n'\
'tail -f /var/log/'${SERVICE_NAME}'_service.log\n'\
'```\n'\
'\n'\
'</td> \n'\
'\n'\
'</tr>\n'\
'</table>' > /tmp/${SERVICE_NAME}_wiki.html

echo 'created wiki file: /tmp/'${SERVICE_NAME}'_wiki.html'

