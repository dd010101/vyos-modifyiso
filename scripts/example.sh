#!/bin/sh
set -e

# basics
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt_install="apt-get install --no-upgrade -y"

# example
$apt_install strace

# cleanup
apt clean
rm -rf /var/lib/apt/lists/*
