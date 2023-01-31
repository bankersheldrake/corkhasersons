
#!/bin/bash
i=1;
for param in "$@" 
do
    case $param in
        --method) paramname=$param;;
        --url) paramname=$param;;
        --auth) paramname=$param;;
        --body) paramname=$param;;
        *)
            if [ -n $paramname ]
            then
                case $paramname in
                    --url) BC_URL=$param;;
                    --auth) BC_AUTH=$param;;
                    --method) BC_METHOD=$param;;
                    --body) BC_BODY=$param;;
                esac
            fi
            paramname=''
            ;;
    esac
    i=$((i + 1));
done
echo curl -X ${BC_METHOD} ${BC_URL}   -H 'accept: */*'   -H 'Content-Type: application/json' -H 'Authorization: '${BC_AUTH} -d ${BC_BODY}
curl -X ${BC_METHOD} ${BC_URL}   -H 'accept: */*'   -H 'Content-Type: application/json' -H 'Authorization: '${BC_AUTH} -d ${BC_BODY}
