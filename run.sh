#!/bin/bash

# Function to clean up background processes if the script exits
cleanup() {
    echo "Stopping all processes..."
    kill $(jobs -p)
}

# Trap script exit to run cleanup
trap cleanup EXIT

# Check if an argument is provided
if [ -z "$1" ]; then
    # If no argument, use default
    echo "No argument provided. Using default python version."
    python_version="python"
else
    echo "Using: $1"
    python_version="$1"
fi


echo "Starting Observice!"
$python_version main.py &  # Run main.py in the background
main_pid=$!

$python_version discord_bot.py &  # Run discord_bot.py in the background
bot_pid=$!

# Wait for the processes to finish
wait $main_pid
wait $bot_pid
