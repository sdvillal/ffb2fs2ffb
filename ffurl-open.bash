#!/bin/bash
MY_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
python -u ${MY_DIR}/ffb2fs2ffb.py open-ffurl "$1"
