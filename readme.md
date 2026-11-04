> [!CAUTION]
> This project is an **independent third-party utility**.
> It is **not affiliated with, endorsed by, or sponsored by VyOS Networks Corporation** by any means.
> VyOS® is a registered trademark of VyOS Networks Corporation.

Utility for customizing existing VyOS images
==

This utility allows unpacking VyOS ISO image, modifying it within a chroot environment, 
and repacking it into a new ISO image.

The process isn't exactly straightforward. Especially if we intended to keep the
VyOS upgrade mechanism intact and also to avoid breaking secure boot compatibility
as far as possible. That's why this utility was created.

Modifying existing images may be useful as an alternative to building a new image
and all packages from scratch with the aim to have customized images. Especially
for VyOS Stream where building all packages is unfriendly, time-consuming, and
there isn't an official nor reliable method to do so straightforwardly.

Usage
--

Switch to root to allow all commands to run correctly.

```shell
sudo -i
```

Install additional required tools above the base system:

```shell
apt-get install squashfs-tools xorriso jq git
```

Get the utility:

```shell
git clone https://github.com/dd010101/vyos-modifyiso.git
```

Get image to modify:

```shell
wget https://community-downloads.vyos.dev/stream/2026.03/vyos-2026.03-generic-amd64.iso
```

Prepare your chroot script. For demonstration, we will use the example script
`./scripts/example.sh` which simply installs a few extra packages. Refer to the
`./scripts/example-zerotier.sh` script for a more complex patchset.

```shell
./vyos-modifyiso/modifyiso.py ./vyos-2026.03-generic-amd64.iso --chroot-script ./vyos-modifyiso/scripts/example.sh
```

If there is a need to interact with the chroot manually, we can use `--interactive` option.

```shell
sudo ./vyos-modifyiso/modifyiso.py ./vyos-2026.03-generic-amd64.iso --interactive
```

After the interactive shell exists successfully, the process of assembling the
image continues.

This can be also mixed with `--chroot-script` option, which will be executed first,
before branding is applied.

The `--interactive` option presents a limited shell, if there is a need for a
full shell, then use the `--interactive` option, wait for the utility to enter
the limited shell, and enter the chroot manually from another shell.

Configuration and branding
--

On the first run, `modifyiso.conf` is generated with default values.  Use `--config`
to point at a different file (which will be created if it does not exist) so you
can easily build multiple variations.

```ini
[branding]
brand = PhoneBo.cx
hostname = phonebocx
splash =
bugtracker_url = https://example.com
documentation_url = https://example.com
project_news_url = https://example.com
support_url = https://example.com
```

Note that `splash` is should be a path to a PNG; a relative path is relative to
the config file's directory. Leave it empty to keep the original logo.

After the chroot step, `./scripts/branding.sh` runs. Use `--no-branding` to skip it.

This uses `scripts/branding.sh` to changes the brand name in various places inside
the image, such as the boot menus and login messages. It also updates the default
config (removing the legacy serial console), and updates both `version.json`
files.

Every key from the config is exported to it as an upper-cased environment variable
(`BRAND`, `HOSTNAME`, `SPLASH`, `BUGTRACKER_URL`, ...), together with:

| Variable       | Content                                          |
|----------------|--------------------------------------------------|
| `TEMP_DIR`     | the temp directory, also the working directory   |
| `ISO_DIR`      | extracted ISO tree (`$TEMP_DIR/iso`)             |
| `SQUASHFS_DIR` | extracted root filesystem (`$TEMP_DIR/squashfs`) |
| `SOURCE_ISO`   | path of the source ISO                           |

For further changes, pass your own executable with `--root-script`. It runs after
`branding.sh`, in the same directory, with the same variables.

Note! Don't modify the EFI binaries or `efi.img`, as that will break secure boot.

Caution on using APT
--
The chroot environment doesn't have access to VyOS APT repositories, and that's why upgrading packages is 
strongly discouraged. Such action may lead to replacing custom packages with those from Debian upstream,  
breaking the OS in the process. Ideally, the VyOS packages shouldn't have overlap like that, thus this situation 
shouldn't arise, but that is not given. I use this utility and install packages with `apt-get install --no-upgrade`
and I didn't find any issues with various VyOS stream versions so far, but your mileage may vary.
