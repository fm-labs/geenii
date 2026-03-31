#!/bin/bash

CMD=$1

if [[ $CMD = "run-server" ]]; then
  echo "Starting geenii server daemon ..."
  exec geeniid
elif [[ $CMD = "interactive" ]]; then
  shift
  exec geenii -c "$@"
elif [[ $CMD = "help" ]]; then
  echo "Usage: entrypoint.sh [run-server|interactive|geenii|help]"
  exit 0
fi

exec "$@"