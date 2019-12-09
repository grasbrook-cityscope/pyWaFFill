#!/bin/sh

docker stop gracio_pywaffill_instance
docker rm gracio_pywaffill_instance
if [ "$#" -gt 0 ]; then # if command line arguments were given
    docker run --name gracio_pywaffill_instance -d gracio_pywaffill --endpoint $1
else # no command line args -> don't choose endpoint
    docker run --name gracio_pywaffill_instance -d gracio_pywaffill
fi
docker logs -f gracio_pywaffill_instance