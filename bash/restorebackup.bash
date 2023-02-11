#!/bin/bash
i=1;
for param in "$@"
do
    case $param in
        --filename) paramname=$param;;
        --move) paramname=$param;;
        *)
            if [ -n $paramname ]
            then
                case $paramname in
                    --filename) RB_FILE=$param;;
                    --move) RB_MOVENOTCOPY=$param;;
                esac
            fi
            paramname=''
            ;;
    esac
    i=$((i + 1));
done

#echo from="sudo find /tmp/bak/sputnik/ -type f -name $RB_FILE"

for file in $(sudo find /tmp/bak/sputnik/ -type f -name $RB_FILE); do
  dest=${file/\/tmp\/bak\/sputnik\//\/home\/pi\/prod/\sputnik\/}
  if [ "$RB_MOVENOTCOPY" == "1" ]; then
      mv -v "$file" "$dest"
  else
      cp -v "$file" "$dest"
  fi
done