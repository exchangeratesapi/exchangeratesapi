#!/bin/sh

set -xeu

[[ -f setup/config-variables ]] && source setup/config-variables

curl -sSL https://agent.digitalocean.com/install.sh | sh