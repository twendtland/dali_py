#!/bin/bash
source ./env/bin/activate
pip3 install -r requirements.txt > /dev/null
python3 source/main.py --version $*
