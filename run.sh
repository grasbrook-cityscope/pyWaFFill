#!/bin/sh

if [ "$#" -gt 0 ]; then # if command line arguments were given
    docker stop gracio_pywaffill_instance_$1
    docker rm gracio_pywaffill_instance_$1
    docker run --name gracio_pywaffill_instance_$1 -d gracio_pywaffill --endpoint $1
    # docker logs -f gracio_pywaffill_instance_$1  ## do not force logs when multiple instances start

else # no command line args -> don't choose endpoint
    docker stop gracio_pywaffill
    docker rm gracio_pywaffill
    docker run --name gracio_pywaffill -d gracio_pywaffill
    docker logs -f gracio_pywaffill
fi
