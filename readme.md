> [!CAUTION]
> This project is an **independent third-party utility**.
> It is **not affiliated with, endorsed by, or sponsored by VyOS Networks Corporation** by any means.
> VyOS® is a registered trademark of VyOS Networks Corporation.

Utility for customizing existing VyOS images
==

This utility allows unpacking VyOS ISO image, modifying it within a chroot environment, 
and repacking it into a new ISO image.

The process isn't exactly straightforward. Especially if we intended to keep the VyOS upgrade mechanism intact 
and also to avoid breaking secure boot compatibility as far as possible. That's why this utility was created.

Modifying existing images may be useful as an alternative to building a new image and all packages from scratch 
with the aim to have customized images. Especially for VyOS Stream where building all packages is unfriendly, 
time-consuming, and there isn't an official nor reliable method to do so straightforwardly.

Usage
--

Install additional required tools above the base system:

```shell
sudo apt-get install squashfs-tools xorriso git
```

Get the utility:

```shell
git clone https://github.com/dd010101/vyos-modifyiso.git
```

Get image to modify:

```shell
wget https://community-downloads.vyos.dev/stream/2026.03/vyos-2026.03-generic-amd64.iso
```

Prepare your chroot script. For demonstration, we will use the example script `./scripts/example.sh`.

```shell
sudo ./vyos-modifyiso/modifyiso.py ./vyos-2026.03-generic-amd64.iso --chroot-script ./vyos-modifyiso/scripts/example.sh
```

If there is a need to interact with the chroot manually, we can use `--interactive` option.

```shell
sudo ./vyos-modifyiso/modifyiso.py ./vyos-2026.03-generic-amd64.iso --interactive
```

After the interactive shell exists successfully, the process of assembling the image continues.
This can be also mixed with `--chroot-script` option, then the script will be executed first.
The `--interactive` option presents a limited shell, if there is a need for a full shell, then use the `--interactive`
option, wait for the utility to enter the limited shell, and enter the chroot manually from another shell.

Caution on using APT
--
The chroot environment doesn't have access to VyOS APT repositories, and that's why upgrading packages is 
strongly discouraged. Such action may lead to replacing custom packages with those from Debian upstream,  
breaking the OS in the process. Ideally, the VyOS packages shouldn't have overlap like that, thus this situation 
shouldn't arise, but that is not given. I use this utility and install packages with `apt-get install --no-upgrade`
and I didn't find any issues with various VyOS stream versions so far, but your mileage may vary.
