#!/bin/bash

if [ -z "$1" ]; then
    # If no argument, use default
    echo "No argument provided. Using default python version."
    python_version="python"
else
    echo "Using: $1"
    python_version="$1"
fi

echo "Starting Observice!"
$python_version main.py &
$python_version discord_bot.py &
