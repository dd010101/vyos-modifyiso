#!/bin/sh

# Default branding script, updates the brand and logo if provided
set -e

# If no brand or hostname provided, use VyOS
if [ ! "$BRAND" ]; then
	export BRAND=VyOS
fi

if [ ! "$HOSTNAME" ]; then
	export HOSTNAME=vyos
fi

sed -i -r -e "s/\(vyos\)/\($BRAND\)/i" -e "s/hostname=vyos/hostname=$HOSTNAME/" "$ISO_DIR/boot/grub/grub.cfg"
sed -i -r "s/VyOS/$BRAND/" "$ISO_DIR/isolinux/menu.cfg"
sed -i -r -e "s/\(vyos/\($BRAND/i" -e "s/hostname=vyos/hostname=$HOSTNAME/" "$ISO_DIR/isolinux/live.cfg"

# This updates the 'Welcome to VyOS' things everywhere
for x in usr/share/vyos/templates/login/default_motd.j2 usr/libexec/vyos/conf_mode/system_login_banner.py usr/libexec/vyos/services/vyos-http-api-server usr/libexec/vyos/op_mode/image_installer.py; do
	sed -i "s/VyOS/$BRAND/g" squashfs/$x
	echo Updated $x
done

cat > squashfs/usr/share/vyos/templates/login/motd_vyos_nonproduction.j2 << EOF

---
WARNING: This system and software is based on, but unrelated to, the VyOS project.
         Do not attempt to contact them for support.
EOF

echo "Brand is now $BRAND and hostname is $HOSTNAME"

# Update Version.json to remove vyos URLs.
rm -f iso/version.json.orig squashfs/user/share/vyos/version.json

# Back up the old ones
mv iso/version.json iso/version.json.orig
mv squashfs/usr/share/vyos/version.json squashfs/usr/share/vyos/version.json.orig

jq --arg bugtracker "${BUGTRACKER_URL:-https://example.com}" \
   --arg documentation "${DOCUMENTATION_URL:-https://example.com}" \
   --arg news "${PROJECT_NEWS_URL:-https://example.com}" \
   --arg support "${SUPPORT_URL:-https://example.com}" \
   '.bugtracker_url = $bugtracker | .documentation_url = $documentation | .project_news_url = $news | .support_url = $support' \
   < iso/version.json.orig > iso/version.json
# Copy the new one from the root of the image to the local machine
cp iso/version.json squashfs/usr/share/vyos/version.json

# If we have a new splash, use that.
if [ -n "$SPLASH" ]; then
    # BIOS (isolinux) and EFI (grub) boot menus each have their own splash image
    cp "$SPLASH" "$ISO_DIR/isolinux/splash.png"
    cp "$SPLASH" "$ISO_DIR/boot/grub/splash.png"
    echo "Replaced boot splash images with '$SPLASH'"
fi

# Replace the default configuration. Changes are:
#   Remove the serial console
#   Set the default hostname
#
# The password for the vyos user is still 'vyos', even though it's auto-logged-in
PASS='$6$QxPS.uk6mfo$9QBSo8u1FkH16gMyAVhus6fU3LOzvLR9Z9.82m3tiHFAxTtIkhaZSWssSgzt4v4dGAL8rhVQxTg0oAG9/q11h/'

[ -e squashfs/usr/share/vyos/config.boot.default.orig ] || mv squashfs/usr/share/vyos/config.boot.default squashfs/usr/share/vyos/config.boot.default.orig
cat > squashfs/usr/share/vyos/config.boot.default << EOF
interfaces {
    loopback lo {
    }
}
service {
    ntp {
        allow-client {
            address "127.0.0.0/8"
            address "169.254.0.0/16"
            address "10.0.0.0/8"
            address "172.16.0.0/12"
            address "192.168.0.0/16"
            address "::1/128"
            address "fe80::/10"
            address "fc00::/7"
        }
        server time1.vyos.net {
        }
        server time2.vyos.net {
        }
        server time3.vyos.net {
        }
    }
}
system {
    config-management {
        commit-revisions "100"
    }
    host-name "$HOSTNAME"
    login {
        operator-group default {
            command-policy {
                allow "*"
            }
        }
        user vyos {
            authentication {
                encrypted-password "$PASS"
                plaintext-password ""
            }
        }
    }
    option {
        reboot-on-upgrade-failure "5"
    }
    syslog {
        local {
            facility all {
                level "info"
            }
            facility local7 {
                level "debug"
            }
        }
    }
}
EOF
