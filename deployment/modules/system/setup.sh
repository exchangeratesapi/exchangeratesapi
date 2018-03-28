#!/bin/sh

set -xeu

[[ -f setup/config-variables ]] && source setup/config-variables

sudo apt-get update && sudo apt-get install -y \
  acl \
  unattended-upgrades \
  policykit-1 \
  ntp \
  wget \
  curl \
  git \
  unzip \
  htop \
  tmux \
  logrotate \
  fail2ban

# Network Time Protocol
sudo service ntp start

# Unattended upgrades
sudo cp setup/modules/system/files/10periodic /etc/apt/apt.conf.d/10periodic
sudo chown root $_

sudo service unattended-upgrades restart

# Users

# SSH: disable root login & password login
sudo sed -i -e "s/PermitRootLogin.*/PermitRootLogin no/" /etc/ssh/sshd_config
sudo sed -i -e "s/PasswordAuthentication.*/PasswordAuthentication no/" /etc/ssh/sshd_config

sudo systemctl reload sshd
