#!/bin/sh
# Updates "version", "release_train" and/or "build_type" in version.json
set -e

if [ -z "$SET_VERSION" ] && [ -z "$SET_TRAIN" ] && [ -z "$SET_BUILDTYPE" ]; then
    # Why was I called? Nothing is set.
    exit 0
fi

OLD_VERSION=$(jq -r '.version' "$ISO_DIR/version.json")

for f in "$ISO_DIR/version.json" "$SQUASHFS_DIR/usr/share/vyos/version.json"; do
    jq --arg version "$SET_VERSION" --arg train "$SET_TRAIN" --arg buildtype "$SET_BUILDTYPE" \
       '(if $version != "" then .version = $version else . end)
        | (if $train != "" then .release_train = $train else . end)
        | (if $buildtype != "" then .build_type = $buildtype else . end)' \
       < "$f" > "$f.tmp"
    mv "$f.tmp" "$f"
    echo "Updated $f"
done

# The BIOS boot menu title includes the version string, but it's only visible
# in limited circumstances. Update it anyway.
if [ -n "$SET_VERSION" ] && [ "$OLD_VERSION" != "$SET_VERSION" ]; then
    old=$(printf '%s' "$OLD_VERSION" | sed 's/[.[\*^$/]/\\&/g')
    new=$(printf '%s' "$SET_VERSION" | sed 's/[\/&]/\\&/g')
    sed -i "s/$old/$new/" "$ISO_DIR/isolinux/menu.cfg"
    echo "Updated $ISO_DIR/isolinux/menu.cfg"
fi

echo "version=$(jq -r '.version' "$ISO_DIR/version.json") release_train=$(jq -r '.release_train' "$ISO_DIR/version.json") build_type=$(jq -r '.build_type' "$ISO_DIR/version.json")"
