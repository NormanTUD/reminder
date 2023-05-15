#!/bin/bash

set -x

rm -rf ~/.reminder_environment
python3 -m venv ~/.reminder_environment

source ~/.reminder_environment/bin/activate

pip install timefhuman easygui holidays matplotlib pandas tabulate

mkdir -p ~/.config/systemd/user/
cat reminder.service | sed -e "s#{basepath}#${PWD}#" > ~/.config/systemd/user/reminder.service
systemctl --user daemon-reload

systemctl --user enable reminder
