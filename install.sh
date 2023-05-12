#!/bin/bash

set -x

rm -rf ~/.reminder_environment
python3 -m venv ~/.reminder_environment

source ~/.reminder_environment/bin/activate

pip install timefhuman easygui holidays matplotlib pandas
