#!/bin/sh

if [ "$#" -gt 0 ]; then # if command line arguments were given
    if [ "$#" -gt 1 ]; then # spped argument given
        echo "walking speed provided"
        docker stop gracio_pywaffill_instance_$1_$2
        docker rm gracio_pywaffill_instance_$1_$2
        docker create --name gracio_pywaffill_instance_$1_$2 gracio_pywaffill --endpoint $1
        docker cp config_$2.json gracio_pywaffill_instance_$1_$2:/app/config.json
        docker start gracio_pywaffill_instance_$1_$2
    else
        docker stop gracio_pywaffill_instance_$1
        docker rm gracio_pywaffill_instance_$1
        docker run --name gracio_pywaffill_instance_$1 -d gracio_pywaffill --endpoint $1
    fi
    
    # docker logs -f gracio_pywaffill_instance_$1  ## do not force logs when multiple instances start

else # no command line args -> don't choose endpoint
    docker stop gracio_pywaffill_instance
    docker rm gracio_pywaffill_instance
    docker run --name gracio_pywaffill_instance -d gracio_pywaffill
    #docker logs -f gracio_pywaffill_instance
fi
