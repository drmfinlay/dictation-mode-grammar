#!/bin/bash

# Shell script to rotate a file's contents between '0' and <max-status>.

# Exit codes:
# 0 - success
# 1 - invalid arguments
# 2 - could not find or write to the text file
# 3 - invalid file state

# Handle arguments.
usage () {
    echo "script usage: $(basename $0) [-h|--help] <max-status> <file>"
}

SCRIPT_NAME=$(basename $0)

# Arguments.
TXT_FILE=""
MAX_STATUS=""

while [[ $# -gt 0 ]]
do
    key="$1"
    case $key in
        -h|--help)
            usage
            exit 0
            ;;
        *)
            shift  # past argument
            if [[ -n $TXT_FILE ]]; then
                echo "Too many arguments."
                usage
                exit 1
            elif [[ -z $MAX_STATUS ]]; then
                MAX_STATUS=$key
            elif [[ -z $TXT_FILE ]]; then
                TXT_FILE=$key
            fi
            ;;
    esac
done

if [[ -z $MAX_STATUS ]]; then
    echo "Please specify the maximum status number for the file."
    usage
    exit 1
fi

if [[ -z $TXT_FILE ]]; then
    echo "Please specify the status file whose value should be rotated."
    usage
    exit 1
fi

# Check if the file exists.
if [[ ! -e $TXT_FILE ]]; then
    echo "File '$TXT_FILE' doesn't exist."
    usage
    exit 2
fi

# Do a simple check to make sure the file contains only one number on the
# first line
STATUS=$(head -n 1 $TXT_FILE | grep "[[:digit:]]\+$")

if [[ $? -ne 0 ]]; then
    echo "First line of the file isn't one number."
    exit 3
fi

# Calculate and set the next status number, wrapping around as necessary.
NEXT_STATUS=$((($STATUS + 1) % ($MAX_STATUS + 1)))
echo $NEXT_STATUS > $TXT_FILE
