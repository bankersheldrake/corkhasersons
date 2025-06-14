#!/bin/bash
CONFIG_WAS_LOADED=false
PROMPTED=false

i=1;
for param in "$@" 
do
    if [[ "$param" == --config=* ]]; then
        CONFIG_FILE="${param#--config=}"
        if [ -f "$CONFIG_FILE" ]; then
            echo "🔄 Loading previous values from $CONFIG_FILE..."
            if ! grep -q '^SERVICE_NAME=' "$CONFIG_FILE"; then
                echo "⚠️ Invalid config file structure. Aborting."
                exit 1
            fi
            source "$CONFIG_FILE"
            CONFIG_WAS_LOADED=true
        else
            echo "⚠️ Config file not found: $CONFIG_FILE"
            exit 1
        fi
    fi
    case $param in
        --name) paramname=$param;;
        --start) paramname=$param;;
        --watch) paramname=$param;;
        --restart) paramname=$param;;
        --user) paramname=$param;; 
        --cwd) paramname=$param;; 
        * )
            if [ -n "$paramname" ]; then
                case $paramname in
                    --name) SERVICE_NAME=$param;;
                    --start) STARTCOMMAND=$param;;
                    --watch) WATCHFOLDERS=$param;;
                    --restart) RESTARTTIME=$param;;
                    --user) RUN_AS_USER=$param; RUN_AS_GROUP=$(id -gn "$RUN_AS_USER");;
                    --cwd) WORKING_DIR=$param;;
                esac
            fi
            paramname=''
            ;;
    esac
    i=$((i + 1));
done
# Fallback to interactive input if missing
if [ -z "$SERVICE_NAME" ]; then
    read -rp "Enter service name (--name): " SERVICE_NAME
    PROMPTED=true
fi
if [ -z "$STARTCOMMAND" ]; then
    read -rp "Enter start command (--start): " STARTCOMMAND
    PROMPTED=true
fi

if [ -z "$SERVICE_MODE" ]; then
    echo "Choose how the service should run:"
    echo "  [1] Always running (auto-restarts on failure)"
    echo "  [2] Scheduled every X seconds (e.g., every 600s)"
    echo "  [3] Run once per day at specific time (e.g., 03:15)"
    read -rp "Enter choice [1/2/3]: " SERVICE_MODE_CHOICE
    case "$SERVICE_MODE_CHOICE" in
        2)
            SERVICE_MODE="interval"
            read -rp "Enter interval in seconds (e.g., 900 for 15min): " RESTARTTIME_SECONDS
            ;;
        3)
            SERVICE_MODE="daily"
            read -rp "Enter time of day to run (HH:MM, 24h format): " RUN_DAILY_TIME
            ;;
        *)
            SERVICE_MODE="always"
            ;;
    esac
    PROMPTED=true
fi

# Add user prompt logic with group filtering
if [ -z "$RUN_AS_USER" ]; then
    # To add users that are listed in this choice:
    # sudo groupadd -f serviceusers && \
    # sudo usermod -aG serviceusers tailscaleuser && \
    # sudo usermod -aG serviceusers forgeLANAccess && \
    # echo "✅ Users added to 'serviceusers' group."
    # ✅ Users added to 'serviceusers' group.
    DEFAULT_USER=${SUDO_USER:-$(whoami)}

    # Include: root, all users in serviceusers group, and any UID >= 1000 with login shell
    SERVICE_GROUP_USERS=$(getent group serviceusers | awk -F: '{print $4}' | tr ',' '\n')

    # Also include 'root' and other valid login users (UID >= 1000 with real shell)
    SYSTEM_USERS=$(awk -F: '($3 == 0 || $3 >= 1000) && ($7 !~ /(false|nologin)$/) {print $1}' /etc/passwd)

    # Combine and deduplicate
    AVAILABLE_USERS=$(echo -e "${SERVICE_GROUP_USERS}\n${SYSTEM_USERS}\nroot" | sort -u)

    echo "Choose which user account the service should run under:"
    select SELECTED_USER in $AVAILABLE_USERS; do
        if [ -n "$SELECTED_USER" ]; then
            break
        else
            echo "⚠️ Invalid choice. Please choose a valid number."
        fi
    done

    RUN_AS_USER="$SELECTED_USER"
    RUN_AS_GROUP=$(id -gn "$RUN_AS_USER")
    PROMPTED=true
fi


if [ -z "$WORKING_DIR" ]; then
    DEFAULT_DIR="/home/${RUN_AS_USER}"
    read -rp "Enter working directory for the service (default: $DEFAULT_DIR): " WORKING_DIR
    WORKING_DIR="${WORKING_DIR:-$DEFAULT_DIR}"

    # Validate it exists
    while [ ! -d "$WORKING_DIR" ]; do
        echo "❌ Directory does not exist: $WORKING_DIR"
        read -rp "Please enter a valid working directory: " WORKING_DIR
    done

    PROMPTED=true
fi

if [ "$SERVICE_MODE" == "always" ] && [ -z "$RESTARTTIME" ]; then
    read -rp "Enter restart delay after failure (--restart), e.g., 3s: " RESTARTTIME
    RESTARTTIME=${RESTARTTIME:-3s}
    PROMPTED=true
fi

if [ -z "$WATCHFOLDERS" ]; then
    WATCHFOLDERS=""
    while true; do
        read -rp "Enter folder(s) or file(s) to watch (--watch), separated by semicolons if more than one: " INPUT_PATHS
        INPUT_PATHS=$(echo "$INPUT_PATHS" | xargs)  # Trim

        if [[ "$INPUT_PATHS" == *";"* ]]; then
            # Multiple entries — don't prompt for subfolders
            IFS=';' read -ra PATH_ARRAY <<< "$INPUT_PATHS"
            for path in "${PATH_ARRAY[@]}"; do
                if [ -e "$path" ]; then
                    WATCHFOLDERS+="${path};"
                else
                    echo "⚠️ Path not found: $path"
                fi
            done
        else
            # Single entry
            if [ -f "$INPUT_PATHS" ]; then
                # File: just add it
                WATCHFOLDERS+="${INPUT_PATHS};"
            elif [ -d "$INPUT_PATHS" ]; then
                read -rp "Include all subfolders of $INPUT_PATHS? [y/N]: " INCLUDE_SUBFOLDERS
                INCLUDE_SUBFOLDERS=${INCLUDE_SUBFOLDERS^^}  # Uppercase

                if [ "$INCLUDE_SUBFOLDERS" = "Y" ]; then
                    SUBFOLDERS=$(find "$INPUT_PATHS" -type d)
                    for folder in $SUBFOLDERS; do
                        WATCHFOLDERS+="${folder};"
                    done
                else
                    WATCHFOLDERS+="${INPUT_PATHS};"
                fi
            else
                echo "⚠️ Path not found: $INPUT_PATHS"
            fi
        fi

        read -rp "Add another path to watch? [y/N]: " ADD_ANOTHER
        ADD_ANOTHER=${ADD_ANOTHER^^}
        [[ "$ADD_ANOTHER" != "Y" ]] && break
    done

    WATCHFOLDERS="${WATCHFOLDERS%;}"  # Strip trailing ;
    PROMPTED=true
fi

if [ -z "$LOG_RETAIN_COUNT" ]; then
    read -rp "Enter how many rotated log files to retain (e.g., 3): " LOG_RETAIN_COUNT
    LOG_RETAIN_COUNT=${LOG_RETAIN_COUNT:-3}  # Default to 3 if blank
    PROMPTED=true
fi
if [ "$SERVICE_MODE" == "always" ] && [ -z "$MAX_RUNTIME" ]; then
    read -rp "Enter maximum allowed runtime in seconds (0 for no limit): " MAX_RUNTIME
    MAX_RUNTIME=${MAX_RUNTIME:-0}
    PROMPTED=true
fi

echo ""
echo "🔍 Please review the collected service configuration:"
echo "----------------------------------------------------"
echo "Service Name        : $SERVICE_NAME"
echo "Start Command       : $STARTCOMMAND"
echo "Service Mode        : $SERVICE_MODE"
[ "$SERVICE_MODE" == "interval" ] && echo "Interval (seconds)  : ${RESTARTTIME_SECONDS:-<not set>}"
[ "$SERVICE_MODE" == "daily" ] && echo "Run Time (daily)    : ${RUN_DAILY_TIME:-<not set>}"
[ "$SERVICE_MODE" == "always" ] && echo "Restart Delay       : ${RESTARTTIME:-<not set>}"
[ -n "$MAX_RUNTIME" ] && echo "Max Runtime (sec)   : $MAX_RUNTIME"
[ -n "$LOG_RETAIN_COUNT" ] && echo "Log Retain Count    : $LOG_RETAIN_COUNT"
[ -n "$RUN_AS_USER" ] && echo "Run As User         : $RUN_AS_USER"
[ -n "$RUN_AS_GROUP" ] && echo "Run As Group        : $RUN_AS_GROUP"
[ -n "$WORKING_DIR" ] && echo "Working Directory   : $WORKING_DIR"

if [ -n "$WATCHFOLDERS" ]; then
    echo "Watched Folders     :"
    IFS=';' read -ra PATHS <<< "$WATCHFOLDERS"
    for path in "${PATHS[@]}"; do
        echo "  - $path"
    done
else
    echo "Watched Folders     : <none>"
fi
echo "----------------------------------------------------"

read -rp "✅ Proceed with service creation? [Y/N]: " CONFIRM
CONFIRM=${CONFIRM^^}
if [ "$CONFIRM" != "Y" ]; then
    echo "❌ Aborting setup by user choice."
    exit 0
fi

if [ "$PROMPTED" = true ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    TMP_CONFIG_FILE="/tmp/${SERVICE_NAME}_service_${TIMESTAMP}.config"
    echo "💾 Saving service config to $TMP_CONFIG_FILE"
escape_quotes() {
    echo "$1" | sed 's/"/\\"/g'
}

cat > "$TMP_CONFIG_FILE" <<EOF
SERVICE_NAME="$SERVICE_NAME"
STARTCOMMAND="$(escape_quotes "$STARTCOMMAND")"
WATCHFOLDERS="$(escape_quotes "$WATCHFOLDERS")"
RESTARTTIME="$RESTARTTIME"
LOG_RETAIN_COUNT="$LOG_RETAIN_COUNT"
MAX_RUNTIME="$MAX_RUNTIME"
SERVICE_MODE="$SERVICE_MODE"
RESTARTTIME_SECONDS="${RESTARTTIME_SECONDS:-}"
RUN_DAILY_TIME="${RUN_DAILY_TIME:-}"
RUN_AS_USER="$RUN_AS_USER"
RUN_AS_GROUP="$RUN_AS_GROUP"
WORKING_DIR="$WORKING_DIR"
EOF



    ln -sf "$TMP_CONFIG_FILE" "/tmp/${SERVICE_NAME}_service_latest.config"
fi

# Ensure process_launcher.sh exists
PROCESS_LAUNCHER_PATH="/usr/services/process_launcher.sh"

if [ ! -f "$PROCESS_LAUNCHER_PATH" ]; then
echo "⚙️ Creating missing $PROCESS_LAUNCHER_PATH..."
mkdir -p /usr/services
cat > "$PROCESS_LAUNCHER_PATH" <<EOF
#!/bin/bash

PROCESS_NAME="\$1"
SCRIPT_PATH="\$2"
MAX_RUNTIME="\$3"
LOG_FILE="\$4"

if [[ -z "\$PROCESS_NAME" || -z "\$SCRIPT_PATH" || -z "\$MAX_RUNTIME" ]]; then
    echo "Usage: \$0 <PROCESS_NAME> <SCRIPT_PATH> <MAX_RUNTIME> [LOG_FILE]"
    exit 0
fi

if [[ -n "\$LOG_FILE" && ! -w "\$LOG_FILE" ]]; then
    touch "\$LOG_FILE" && chmod 664 "\$LOG_FILE"
fi

log() {
    if [[ -n "\$LOG_FILE" && -w "\$LOG_FILE" ]]; then
        echo "\$(date '+%Y-%m-%d %H:%M:%S') - \$1" >> "\$LOG_FILE"
    else
        echo "\$(date '+%Y-%m-%d %H:%M:%S') - \$1"
    fi
}

log "Checking for running instances of \$PROCESS_NAME..."

PIDS=\$(pgrep -fa "/bin/bash \$SCRIPT_PATH" | awk '{print \$1}' | grep -v \$\$ | grep -v \$PPID)
VALID_PROCESS_FOUND=false

kill_process_tree() {
    local PARENT_PID=\$1
    CHILD_PIDS=\$(pgrep -P "\$PARENT_PID")
    if [[ -n "\$CHILD_PIDS" ]]; then
        for CHILD in \$CHILD_PIDS; do
            kill_process_tree "\$CHILD"
        done
    fi

    log "Killing process \$PARENT_PID and its children..."
    kill "\$PARENT_PID"
    sleep 2

    if ps -p "\$PARENT_PID" > /dev/null 2>&1; then
        log "Process \$PARENT_PID did not exit, forcing SIGKILL..."
        kill -9 "\$PARENT_PID"
    fi
}

if [[ -n "\$PIDS" ]]; then
    for PID in \$PIDS; do
        if ! ps -p "\$PID" > /dev/null 2>&1; then
            log "Detected process \$PID is no longer running. Ignoring."
            continue
        fi

        ELAPSED_TIME=\$(ps -o etimes= -p "\$PID" | awk '{print \$1}')

        if [[ -n "\$ELAPSED_TIME" ]]; then
            if [[ "\$ELAPSED_TIME" -gt "\$MAX_RUNTIME" ]]; then
                log "Process \$PID has been running for more than \$MAX_RUNTIME seconds. Killing it and its children..."
                kill_process_tree "\$PID"
            else
                log "Process \$PID is running within allowed time of \$MAX_RUNTIME seconds. Exiting with 'found_valid_process'."
                VALID_PROCESS_FOUND=true
            fi
        fi
    done
fi

if [[ "\$VALID_PROCESS_FOUND" == true ]]; then
    exit 1
else
    exit 0
fi
EOF


    chmod +x "$PROCESS_LAUNCHER_PATH"
fi



mkdir "/usr/services/${SERVICE_NAME}"
echo Make the service start and stop bash scripts

cat > "/usr/services/${SERVICE_NAME}/start.sh" <<EOF
#!/bin/bash
set -e

PROCESS_NAME="${SERVICE_NAME}"
SCRIPT_PATH="/usr/services/\${PROCESS_NAME}/start.sh"
LOG_FILE="/var/log/\${PROCESS_NAME}_service.log"
PROCESS_LAUNCHER="/usr/services/process_launcher.sh"
MAX_RUNTIME=${MAX_RUNTIME}

# Rotate logs
for ((i=${LOG_RETAIN_COUNT}; i>0; i--)); do
    if [ -f "\${LOG_FILE}.\$((i-1))" ]; then
        mv "\${LOG_FILE}.\$((i-1))" "\${LOG_FILE}.\$i"
    fi
done
[ -f "\${LOG_FILE}" ] && mv "\${LOG_FILE}" "\${LOG_FILE}.1"

# Use process manager unless MAX_RUNTIME is 0
if [[ "\$MAX_RUNTIME" -gt 0 ]]; then
    "\$PROCESS_LAUNCHER" "\$PROCESS_NAME" "\$SCRIPT_PATH" "\$MAX_RUNTIME" "\$LOG_FILE"
    [[ \$? -eq 1 ]] && exit 0
fi

echo "\$(date '+%Y-%m-%d %H:%M:%S') - Starting \$PROCESS_NAME..." > "\$LOG_FILE"
if ! ${STARTCOMMAND} 2>&1 | tee -a "\$LOG_FILE"; then
    echo "\$(date '+%Y-%m-%d %H:%M:%S') - Error: Execution failed." >> "\$LOG_FILE"
    exit 1
fi
echo "\$(date '+%Y-%m-%d %H:%M:%S') - \$PROCESS_NAME completed." >> "\$LOG_FILE"
exit 0
EOF


echo "Make the service stop bash script"
cat > "/usr/services/${SERVICE_NAME}/stop.sh" <<EOF
#!/bin/bash
set -e

PROCESS_NAME="${SERVICE_NAME}"
SCRIPT_PATH="/usr/services/\${PROCESS_NAME}/start.sh"
LOG_FILE="/var/log/\${PROCESS_NAME}_service.log"
PROCESS_LAUNCHER="/usr/services/process_launcher.sh"

# Force cleanup: treat all existing processes as over time limit
"\$PROCESS_LAUNCHER" "\$PROCESS_NAME" "\$SCRIPT_PATH" 1 "\$LOG_FILE" || true

echo "\$(date '+%Y-%m-%d %H:%M:%S') - Service stopped." >> "\$LOG_FILE"
EOF


chmod a+x "/usr/services/${SERVICE_NAME}/start.sh"
chmod a+x "/usr/services/${SERVICE_NAME}/stop.sh"
echo "Make the service daemon definition"

if [ "$SERVICE_MODE" == "interval" ]; then
    # Interval-based service
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    {
        echo "[Unit]"
        echo "Description=${SERVICE_NAME} interval-based service"
        echo "After=network.target"
        echo ""
        echo "[Service]"
        echo "Type=oneshot"
        echo "ExecStart=/usr/services/${SERVICE_NAME}/start.sh"
        echo "ExecStop=/usr/services/${SERVICE_NAME}/stop.sh"
        [ -n "$RUN_AS_USER" ] && echo "User=${RUN_AS_USER}"
        [ -n "$RUN_AS_GROUP" ] && echo "Group=${RUN_AS_GROUP}"
        [ -n "$WORKING_DIR" ] && echo "WorkingDirectory=${WORKING_DIR}"
        echo "TimeoutSec=300"
        echo ""
        echo "[Install]"
        echo "WantedBy=multi-user.target"
    } > "$SERVICE_FILE"

    TIMER_FILE="/etc/systemd/system/${SERVICE_NAME}.timer"
    {
        echo "[Unit]"
        echo "Description=Interval timer for ${SERVICE_NAME}"
        echo ""
        echo "[Timer]"
        echo "OnBootSec=5min"
        [ -n "$RESTARTTIME_SECONDS" ] && echo "OnUnitActiveSec=${RESTARTTIME_SECONDS}"
        echo "AccuracySec=1s"
        echo "Unit=${SERVICE_NAME}.service"
        echo ""
        echo "[Install]"
        echo "WantedBy=timers.target"
    } > "$TIMER_FILE"

elif [ "$SERVICE_MODE" == "daily" ]; then
    # Daily timer service
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    {
        echo "[Unit]"
        echo "Description=${SERVICE_NAME} daily service"
        echo "After=network.target"
        echo ""
        echo "[Service]"
        echo "Type=oneshot"
        echo "ExecStart=/usr/services/${SERVICE_NAME}/start.sh"
        echo "ExecStop=/usr/services/${SERVICE_NAME}/stop.sh"
        [ -n "$RUN_AS_USER" ] && echo "User=${RUN_AS_USER}"
        [ -n "$RUN_AS_GROUP" ] && echo "Group=${RUN_AS_GROUP}"
        [ -n "$WORKING_DIR" ] && echo "WorkingDirectory=${WORKING_DIR}"
        echo "TimeoutSec=300"
        echo ""
        echo "[Install]"
        echo "WantedBy=multi-user.target"
    } > "$SERVICE_FILE"

    TIMER_FILE="/etc/systemd/system/${SERVICE_NAME}.timer"
    {
        echo "[Unit]"
        echo "Description=Daily timer for ${SERVICE_NAME}"
        echo ""
        echo "[Timer]"
        [ -n "$RUN_DAILY_TIME" ] && echo "OnCalendar=*-*-* ${RUN_DAILY_TIME}"
        echo "AccuracySec=1s"
        echo "Unit=${SERVICE_NAME}.service"
        echo ""
        echo "[Install]"
        echo "WantedBy=timers.target"
    } > "$TIMER_FILE"

else
    # Always-on service
    SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
    {
        echo "[Unit]"
        echo "Description=${SERVICE_NAME} always-on service"
        echo "After=network.target"
        echo ""
        echo "[Service]"
        echo "Type=simple"
        echo "ExecStart=/usr/services/${SERVICE_NAME}/start.sh"
        echo "ExecStop=/usr/services/${SERVICE_NAME}/stop.sh"
        echo "Restart=always"
        [ -n "$RESTARTTIME" ] && echo "RestartSec=${RESTARTTIME}"
        [ -n "$RUN_AS_USER" ] && echo "User=${RUN_AS_USER}"
        [ -n "$RUN_AS_GROUP" ] && echo "Group=${RUN_AS_GROUP}"
        [ -n "$WORKING_DIR" ] && echo "WorkingDirectory=${WORKING_DIR}"
        echo "TimeoutSec=60"
        echo "RuntimeMaxSec=infinity"
        echo "PIDFile=/tmp/${SERVICE_NAME}.pid"
        echo ""
        echo "[Install]"
        echo "WantedBy=multi-user.target"
    } > "$SERVICE_FILE"
fi

echo Make the srv-watcher.service daemon definition
if [ "$WATCHFOLDERS" != "" ]; then
    echo "Make the srv-watcher.service daemon definition"

    cat > "/etc/systemd/system/${SERVICE_NAME}-watcher.service" <<EOF
[Unit]
Description=${SERVICE_NAME} restarter
After=network.target

[Service]
Type=oneshot
ExecStart=systemctl restart ${SERVICE_NAME}.service

[Install]
WantedBy=multi-user.target
EOF

    echo "Make the srv-watcher.path daemon definition"
    
    CLEANED_WATCHFOLDERS=$(echo "$WATCHFOLDERS" | tr ';' '\n' | sed '/^\s*$/d')
    
    if [ -n "$CLEANED_WATCHFOLDERS" ]; then
        {
            echo "[Path]"
            echo "$CLEANED_WATCHFOLDERS" | sed 's/^/PathModified=/'
            echo ""
            echo "[Install]"
            echo "WantedBy=multi-user.target"
        } > "/etc/systemd/system/${SERVICE_NAME}-watcher.path"
    fi
fi

echo enable the service daemon "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl enable "/etc/systemd/system/${SERVICE_NAME}.service"
# echo enabled the service daemon "/etc/systemd/system/${SERVICE_NAME}.service"
if [ "$WATCHFOLDERS" != "" ]; 
then 
    echo enable the watch daemon
    systemctl enable "/etc/systemd/system/${SERVICE_NAME}-watcher.service"; 
    # systemctl start "${SERVICE_NAME}-watcher.service";
fi
echo reload the deamon
systemctl daemon-reload

# Determine current user
OWNER_USER=${SUDO_USER:-$(whoami)}
OWNER_GROUP=$(id -gn "$OWNER_USER")


# Create or touch the log file
LOG_FILE="/var/log/${SERVICE_NAME}_service.log"
touch "$LOG_FILE"
chown "$OWNER_USER:$OWNER_GROUP" "$LOG_FILE"
chmod 664 "$LOG_FILE"


CLEANUP_SCRIPT="/tmp/cleanup_${SERVICE_NAME}.sh"
cat > "$CLEANUP_SCRIPT" <<EOF
#!/bin/bash
sudo rm "/usr/services/${SERVICE_NAME}/start.sh"
sudo rm "/usr/services/${SERVICE_NAME}/stop.sh"
sudo rm -rf "/usr/services/${SERVICE_NAME}/"
sudo rm "/etc/systemd/system/${SERVICE_NAME}.service"
sudo rm "/etc/systemd/system/${SERVICE_NAME}-watcher.service"
sudo rm "/etc/systemd/system/${SERVICE_NAME}-watcher.path"
sudo rm "/var/log/${SERVICE_NAME}_service.log"
sudo systemctl daemon-reload
EOF

chmod +x "$CLEANUP_SCRIPT"
echo "🧹 Cleanup script written to $CLEANUP_SCRIPT"


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

echo "Validating systemd units..."
if [ "$WATCHFOLDERS" != "" ]; then
    systemd-analyze verify /etc/systemd/system/${SERVICE_NAME}*.service /etc/systemd/system/${SERVICE_NAME}*.path || true
else
    systemd-analyze verify /etc/systemd/system/${SERVICE_NAME}*.service || true
fi

read -p 'Would you like to start the services (Y/N)?: ' sInput
sInput=${sInput^^}  # Convert input to uppercase for case-insensitive comparison
if [ "$sInput" = "Y" ]; then
    echo "Starting the service..."
    systemctl enable "${SERVICE_NAME}.service"

    if [ "$SERVICE_MODE" == "interval" ] || [ "$SERVICE_MODE" == "daily" ]; then
        systemctl enable "${SERVICE_NAME}.timer"
        systemctl start "${SERVICE_NAME}.timer"
    elif [ "$WATCHFOLDERS" != "" ]; then
        echo "Starting the path watch service"
        systemctl start "${SERVICE_NAME}-watcher.service"
    fi
fi
