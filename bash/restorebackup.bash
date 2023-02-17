#!/bin/bash
RB_CONFIRM=0
i=1;
for param in "$@"
do
    case $param in
        --filename) paramname=$param;;
        --move) paramname=$param;;
        --confirm) paramname=$param;;
        
        *)
            if [ -n $paramname ]
            then
                case $paramname in
                    --filename) RB_FILE=$param;;
                    --move) RB_MOVENOTCOPY=$param;;
                    --confirm) RB_CONFIRM=$param;;
                esac
            fi
            paramname=''
            ;;
    esac
    i=$((i + 1));
done
if echo x"$RB_FILE" | grep '*' > /dev/null; then
    RB_CONFIRM=1
fi
# echo "$RB_FILE"
RB_FIND='sudo find /tmp/bak/sputnik/ -type f -iname '"'""$RB_FILE""'"
RB_ROOTDIRESCAPED=\/tmp\/bak\/\sputnik\/
RB_CONTINUE=1
RB_FOUNDFILE=0
RB_CHECKEDARCHIVE=0
while [ "$RB_CONTINUE" == "1" ]
do
    # eval $RB_FIND
    for file in $(eval $RB_FIND); do
        # dest=${file/$RB_ROOTDIRESCAPED/\/home\/pi\/prod/\sputnik\/}
        dest=/home/pi/prod/sputnik$(echo "$file" | sed 's/.*sputnik//')
        # x=$(echo "$x" | sed 's/:/ /g')
        if [ "$RB_CONFIRM" == "1" ]; then
            read -p 'Found '$file' -> '$dest'. Do want to continue (Y/F/N/X): ' RB_GOAHEAD
        else
            RB_GOAHEAD=Y
        fi
        if [ "$RB_GOAHEAD" == "y" ] || [ "$RB_GOAHEAD" == "Y" ] || [ "$RB_GOAHEAD" == "f" ] || [ "$RB_GOAHEAD" == "F" ]; then
            if [ "$RB_MOVENOTCOPY" == "1" ]; then
                mv -v "$file" "$dest"
            else
                cp -v "$file" "$dest"
            fi
            RB_FOUNDFILE=1
        fi
        if [ "$RB_GOAHEAD" == "x" ] || [ "$RB_GOAHEAD" == "X" ] || [ "$RB_GOAHEAD" == "f" ] || [ "$RB_GOAHEAD" == "F" ]; then
            RB_FOUNDFILE=1
            BREAK
        fi
    done
    RB_CONTINUE=0
    if [ "$RB_FOUNDFILE" == "0" ] && [ "$RB_CHECKEDARCHIVE" == "0" ]; then
        echo $RB_FOUNDFILE
        echo $RB_CHECKEDARCHIVE
        read -p 'No matches for '"'""$RB_FILE""'"' in last overwrite. Try other archived backups (Y/N): ' RB_GOAHEAD
        if [ "$RB_GOAHEAD" == "y" ] || [ "$RB_GOAHEAD" == "Y" ]; then
            RB_FIND='sudo find /tmp/bak_success/ -type f -iname '"'""$RB_FILE""'"' | sort -V -r | head -n 10 '
            RB_ROOTDIRESCAPED=\/tmp\/bak_success\/
            RB_CONTINUE=1
            RB_CONFIRM=1
            RB_CHECKEDARCHIVE=1
        fi
    fi

done
