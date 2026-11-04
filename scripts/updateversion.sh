#!/bin/sh
# Updates "version", "release_train" and/or "build_type" in version.json
set -e

if [ -z "$SET_VERSION" ] && [ -z "$SET_TRAIN" ] && [ -z "$SET_BUILDTYPE" ]; then
    # Why was I called? Nothing is set.
    exit 0
fi

CURRENT_VERSION=$(jq -r '.version' "$ISO_DIR/version.json")
if [ ! "$CURRENT_VERSION" ]; then
    echo "Error! Can't figure out the current version from $ISO_DIR/version.json"
    exit 1
fi

for f in "$ISO_DIR/version.json" "$SQUASHFS_DIR/usr/share/vyos/version.json"; do
    jq --arg version "$SET_VERSION" --arg train "$SET_TRAIN" --arg buildtype "$SET_BUILDTYPE" \
       '(if $version != "" then .version = $version else . end)
        | (if $train != "" then .release_train = $train else . end)
        | (if $buildtype != "" then .build_type = $buildtype else . end)' \
       < "$f" > "$f.tmp"
    mv "$f.tmp" "$f"
    echo "Updated $f"
done

# The version string also appears in a bunch of other places.
VFILES="$ISO_DIR/isolinux/menu.cfg $ISO_DIR/.disk/info $SQUASHFS_DIR/opt/vyatta/etc/version"

# Escape any /'s so we can use them in the release. But you probably shouldn't.
new=$(printf '%s' "$SET_VERSION" | sed 's/[\/&]/\\&/g')
old=$(printf '%s' "$CURRENT_VERSION" | sed 's/[.[\*^$/]/\\&/g')

for f in $VFILES; do
    sed -i "s/$old/$new/" $f
    echo "Updated $f"
done

echo "version=$(jq -r '.version' "$ISO_DIR/version.json") release_train=$(jq -r '.release_train' "$ISO_DIR/version.json") build_type=$(jq -r '.build_type' "$ISO_DIR/version.json")"
