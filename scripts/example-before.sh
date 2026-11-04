#!/usr/bin/env bash
set -euo pipefail

echo "I run outside chroot and before"
echo "These variables are available in all scripts:"
echo -e "\tTEMP_DIR=$TEMP_DIR"
echo -e "\tISO_DIR=$ISO_DIR"
echo -e "\tSQUASHFS_DIR=$SQUASHFS_DIR"
echo -e "\tSOURCE_ISO=$SOURCE_ISO"
echo -e "\tTARGET_ISO=$TARGET_ISO"

echo "We can also potentially include custom variables such as TEST=$TEST"
