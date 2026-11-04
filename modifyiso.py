#!/usr/bin/env python3
import argparse
import configparser
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
from time import monotonic, sleep
from typing import Union, Optional


PROJECT_DIR = os.path.realpath(os.path.dirname(__file__))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_DIR, "modifyiso.conf")
DEFAULT_BRANDING_SCRIPT = os.path.join(PROJECT_DIR, "scripts", "branding.sh")
DEFAULT_VERSION_SCRIPT = os.path.join(PROJECT_DIR, "scripts", "updateversion.sh")

CONFIG_SECTION = "branding"
# Every key in the [branding] section is exported, upper-cased, to the branding and root scripts.
DEFAULT_CONFIG = {
    "brand": "PhoneBo.cx",
    "hostname": "phonebocx",
    "splash": "",
    "bugtracker_url": "https://example.com",
    "documentation_url": "https://example.com",
    "project_news_url": "https://example.com",
    "support_url": "https://example.com",
}

def load_config(path):
    """Read the config file, creating it with defaults if missing. Returns the [branding] values."""
    parser = configparser.ConfigParser(interpolation=None)
    if not os.path.exists(path):
        parser[CONFIG_SECTION] = DEFAULT_CONFIG
        with open(path, "w") as file:
            file.write("# vyos-modifyiso configuration. Every key below is exported, upper-cased\n")
            file.write("# (e.g. brand -> BRAND), to scripts/branding.sh and the --root-script.\n")
            file.write("# A relative splash path is relative to this file's directory.\n\n")
            parser.write(file)
        logging.info("Generated default config '%s'" % path)

    try:
        parser.read(path)
    except configparser.Error as e:
        raise ErrorException("Invalid config '%s': %s" % (path, e))
    if not parser.has_section(CONFIG_SECTION):
        raise ErrorException("Config '%s' has no [%s] section" % (path, CONFIG_SECTION))

    values = dict(DEFAULT_CONFIG)
    values.update(parser[CONFIG_SECTION])

    if values["splash"]:
        splash = os.path.join(os.path.dirname(os.path.realpath(path)), values["splash"])
        if not os.path.isfile(splash):
            raise ErrorException("Splash image '%s' doesn't exist" % splash)
        values["splash"] = splash

    return values


class ModifyIso:
    logger = logging

    def __init__(self, source_iso, temp_dir, chroot_script, target_iso, interactive=False,
                 skip_extract=False, skip_chroot=False, skip_iso=False, stdout_only=False, root_script=None,
                 config=None, branding_script=DEFAULT_BRANDING_SCRIPT, no_branding=False,
                 set_version=None, set_train=None, set_buildtype=None, version_script=DEFAULT_VERSION_SCRIPT):
        self.source_iso: str = os.path.realpath(source_iso)
        self.temp_dir = os.path.realpath(temp_dir)
        self.chroot_script = chroot_script
        self.root_script = os.path.realpath(root_script) if root_script else None
        self.branding_script = os.path.realpath(branding_script)
        self.config = dict(config or {})
        self.target_iso = target_iso
        self.interactive = interactive
        self.hostname = self.config.get("hostname")
        self.skip_extract = skip_extract
        self.skip_chroot = skip_chroot
        self.skip_iso = skip_iso
        self.no_branding = no_branding
        self.set_version = set_version
        self.set_train = set_train
        self.set_buildtype = set_buildtype
        self.version_script = os.path.realpath(version_script)
        self.stdout_only = stdout_only

        self.mount_dir = os.path.join(self.temp_dir, "mount")
        self.iso_dir = os.path.join(self.temp_dir, "iso")
        self.squashfs_dir = os.path.join(self.temp_dir, "squashfs")
        self.original_working_dir = os.getcwd()

        if not self.no_branding:
            self.check_executable(self.branding_script, "Branding script")
        if self.set_version or self.set_train or self.set_buildtype:
            self.check_executable(self.version_script, "Version script")
        if self.root_script:
            self.check_executable(self.root_script, "Root script")

    @staticmethod
    def check_executable(path, label):
        if not os.path.isfile(path):
            raise ErrorException("%s '%s' doesn't exist" % (label, path))
        if not os.access(path, os.X_OK):
            raise ErrorException("%s '%s' isn't executable" % (label, path))

    def run(self):
        if not self.skip_extract:
            self.mount_and_extract()

        if not self.skip_chroot:
            self.execute_chroot()

        if not self.no_branding:
            self.execute_host_script(self.branding_script, "branding script")

        # After branding.sh, which regenerates version.json from the original
        if self.set_version or self.set_train or self.set_buildtype:
            self.execute_host_script(self.version_script, "version script")

        if self.root_script:
            self.execute_host_script(self.root_script, "root script")

        if not self.skip_iso:
            self.generate_iso()

    def mount_and_extract(self):
        self.mount_iso(self.source_iso)

        if os.path.exists(self.iso_dir):
            shutil.rmtree(self.iso_dir)
        os.makedirs(self.iso_dir)

        self.logger.info("Copying ISO contents to '%s'" % self.iso_dir)
        self.execute(["/usr/bin/cp", "-a", os.path.join(self.mount_dir, "."), self.iso_dir])

        self.logger.info("Unmounting ISO")
        self.umount(self.mount_dir)

        if os.path.exists(self.squashfs_dir):
            self.umount_all(self.squashfs_dir)
            shutil.rmtree(self.squashfs_dir)

        self.logger.info("Extracting squashfs filesystem")
        os.chdir(self.temp_dir)
        self.execute([
            "/usr/bin/unsquashfs",
            "-d", self.squashfs_dir,
            os.path.join(self.iso_dir, "live/filesystem.squashfs")
        ])

    def execute_chroot(self):
        os.chdir(self.original_working_dir)
        self.logger.info("Preparing chroot")

        apt_sources_path = os.path.join(self.squashfs_dir, "etc/apt/sources.list")
        apt_sources_backup_path = "%s.bak" % apt_sources_path
        if not os.path.exists(apt_sources_backup_path):
            os.rename(apt_sources_path, apt_sources_backup_path)

        with open(apt_sources_backup_path, "r") as source_file:
            lines = []
            for line in source_file:
                url = "http://ftp.debian.org/debian/"
                if "security" in line:
                    url = "http://security.debian.org/debian-security"
                line = re.sub(r"(deb|deb-src)\s+[^\s]+\s+", "\\1 %s " % url, line)
                lines.append(line)

            with open(apt_sources_path, "w") as target_file:
                for line in lines:
                    target_file.write(line)
                    target_file.write("\n")

        resolv_path = os.path.join(self.squashfs_dir, "etc/resolv.conf")
        resolv_backup_path = "%s.bak" % resolv_path
        if not os.path.exists(resolv_backup_path):
            os.rename(resolv_path, resolv_backup_path)
        shutil.copy2("/etc/resolv.conf", resolv_path)

        for directory in ["dev", "proc", "sys"]:
            target = os.path.join(self.squashfs_dir, directory)
            self.execute(["/usr/bin/mount", "--bind", os.path.join("/", directory), target])

        temp_script_path = os.path.join(self.squashfs_dir, "custom.sh")
        chroot_temp_script_path = temp_script_path[len(self.squashfs_dir):]
        if self.chroot_script:
            shutil.copy2(self.chroot_script, temp_script_path)
            os.chmod(temp_script_path, 0o755)

        try:
            self.logger.info("Executing chroot '%s'" % self.squashfs_dir)

            if self.chroot_script:
                self.execute(["/usr/sbin/chroot", self.squashfs_dir, "/bin/sh", "-c", chroot_temp_script_path])

            if self.interactive:
                self.execute(["/usr/sbin/chroot", self.squashfs_dir, "/bin/sh"], stdin=sys.stdin)

            self.logger.info("Cleaning chroot")

            if os.path.exists(temp_script_path):
                os.remove(temp_script_path)

            os.remove(apt_sources_path)
            os.rename(apt_sources_backup_path, apt_sources_path)

            os.remove(resolv_path)
            os.rename(resolv_backup_path, resolv_path)

        finally:
            for directory in ["dev", "proc", "sys"]:
                target = os.path.join(self.squashfs_dir, directory)
                self.execute(["/usr/bin/umount", "-l", target], valid_codes=[0, 32])

    def execute_host_script(self, script, label):
        self.logger.info("Executing %s '%s' in '%s'" % (label, script, self.temp_dir))

        env = dict(os.environ)
        env.update({key.upper(): str(value) for key, value in self.config.items()})
        env.update(
            TEMP_DIR=self.temp_dir,
            ISO_DIR=self.iso_dir,
            SQUASHFS_DIR=self.squashfs_dir,
            SOURCE_ISO=self.source_iso,
        )
        if self.set_version:
            env["SET_VERSION"] = self.set_version
        if self.set_train:
            env["SET_TRAIN"] = self.set_train
        if self.set_buildtype:
            env["SET_BUILDTYPE"] = self.set_buildtype
        self.execute([script], cwd=self.temp_dir, env=env)

    def generate_iso(self):
        self.logger.info("Generating squashfs")

        squashfs_path = os.path.join(self.iso_dir, "live/filesystem.squashfs")
        if os.path.exists(squashfs_path):
            os.remove(squashfs_path)

        self.execute(["/usr/bin/mksquashfs", self.squashfs_dir, squashfs_path, "-comp", "xz"])

        self.logger.info("Generating checksums")
        self.generate_checksums(self.iso_dir)

        self.logger.info("Generating ISO")
        target_iso_path = self.target_iso
        if target_iso_path == "auto":
            parts = os.path.splitext(self.source_iso)
            target_iso_path = "%s-custom%s" % parts

        if os.path.exists(target_iso_path):
            os.remove(target_iso_path)

        os.chdir(self.original_working_dir)
        command = [
            "/usr/bin/xorriso",
            "-as", "mkisofs",
        ]
        command.extend(self.get_xorriso_arguments(self.source_iso))
        command.extend([
            "-output", target_iso_path,
            self.iso_dir,
        ])
        self.execute(command)

        self.verify_iso(target_iso_path)

        self.logger.info("ISO '%s' generated successfully" % target_iso_path)

    def get_xorriso_arguments(self, iso_path):
        command = [
            "/usr/bin/xorriso",
            "-indev", iso_path,
            "-report_el_torito", "as_mkisofs",
        ]
        output = self.execute(command, stdout=subprocess.PIPE)
        return shlex.split(str(output))

    def generate_checksums(self, directory):
        os.chdir(directory)
        excluded_paths = [
            "./sha256sum.txt",
            "./isolinux",
        ]
        with open("sha256sum.txt", "w") as file:
            for parent, directories, files in os.walk("."):
                for file_name in files:
                    path = os.path.join(parent, file_name)

                    excluded = False
                    for pattern in excluded_paths:
                        if path.startswith(pattern):
                            excluded = True
                            break

                    if excluded:
                        continue

                    output = self.execute(["/usr/bin/sha256sum", path], stdout=subprocess.PIPE)
                    file.write(str(output).strip())
                    file.write("\n")

    def verify_iso(self, iso_path):
        self.logger.info("Verifying ISO")

        self.mount_iso(iso_path, silent=True)

        os.chdir(self.iso_dir)
        self.execute(["/usr/bin/sha256sum", "-c", "sha256sum.txt"], stdout=subprocess.DEVNULL)

        self.umount(self.iso_dir)

        self.logger.info("ISO verified successfully")

    def mount_iso(self, iso_path, silent=False):
        if not os.path.exists(iso_path):
            raise ErrorException("Source ISO '%s' doesn't exist" % iso_path)

        if os.path.exists(self.mount_dir):
            self.umount(self.mount_dir)
        else:
            os.makedirs(self.mount_dir)

        if not silent:
            self.logger.info("Mounting ISO '%s' to '%s'" % (iso_path, self.mount_dir))

        self.execute(["/usr/bin/mount", "-o", "loop,ro", iso_path, self.mount_dir])

    def umount(self, mount):
        self.execute(["/usr/bin/umount", mount], valid_codes=[0, 32], stdout=subprocess.DEVNULL)

    def umount_all(self, target_dir):
        target_dir = os.path.realpath(target_dir)

        related_mounts = []
        with open("/proc/mounts", "r") as file:
            for line in file:
                parts = line.split()
                if len(parts) >= 2:
                    mount_point = os.path.realpath(parts[1].encode("utf-8").decode("unicode_escape"))
                    if mount_point == target_dir or mount_point.startswith(target_dir + os.sep):
                        related_mounts.append(mount_point)

        related_mounts.sort(key=lambda path: path.count(os.sep), reverse=True)

        for mount_point in related_mounts:
            self.umount(mount_point)

    def execute(self, command, valid_codes: Optional[Union[int, list]] = 0, timeout=0, **kwargs) -> Optional[str]:
        if "stdout" not in kwargs:
            kwargs.update({
                "stdout": sys.stdout,
                "stderr": sys.stdout if self.stdout_only else sys.stderr,
                "stdin": sys.stdin,
            })

        if "stderr" not in kwargs:
            kwargs["stderr"] = subprocess.DEVNULL

        process = subprocess.Popen(command, **kwargs)

        deadline = monotonic() + timeout
        while process.poll() is None:
            if timeout > 0 and monotonic() > deadline:
                process.kill()
                raise TimeoutError("Command '%s' timed out" % command)
            sleep(0.100)

        if valid_codes is not None:
            if not isinstance(valid_codes, list):
                valid_codes = [valid_codes]

        if process.returncode not in valid_codes:
            raise ProcessException(command, process.returncode, process.stdout, process.stderr)

        if process.stdout is None:
            return None
        return process.stdout.read().decode("utf-8")


class ProcessException(Exception):
    def __init__(self, command, returncode, stdout=None, stderr=None):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        message = "Command '%s' failed with code %s" % (self.command, self.returncode)
        if self.stdout:
            message += ", stdout: %s" % self.stdout.read().decode("utf-8")
        if self.stderr:
            message += ", stderr: %s" % self.stderr.read().decode("utf-8")
        return message


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_iso")
    parser.add_argument("--temp-dir", default=os.path.join(PROJECT_DIR, "build"))
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--chroot-script")
    parser.add_argument("--root-script")
    parser.add_argument("--target-iso", default="auto")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--skip-extract", action="store_true")
    parser.add_argument("--skip-chroot", action="store_true")
    parser.add_argument("--skip-iso", action="store_true")
    parser.add_argument("--no-branding", action="store_true")
    parser.add_argument("--set-version")
    parser.add_argument("--set-train")
    parser.add_argument("--set-buildtype")

    args = parser.parse_args()
    values = vars(args)
    values["config"] = load_config(values["config"])

    ModifyIso(**values).run()


class ErrorException(Exception):
    pass


class LessThanLevelFilter(logging.Filter):
    def __init__(self, exclusive_maximum, name="LessThanLevelFilter"):
        super(LessThanLevelFilter, self).__init__(name)
        self.maximum_level = exclusive_maximum

    def filter(self, record):
        return 1 if record.levelno < self.maximum_level else 0


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    stderr_level = logging.WARNING

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.addFilter(LessThanLevelFilter(stderr_level))
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(stderr_level)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)


if __name__ == "__main__":
    setup_logging()

    try:
        main()

    except ErrorException as e:
        logging.error(e)
        exit(1)
    except KeyboardInterrupt:
        exit(1)
    except Exception as e:
        logging.exception(e)
        exit(1)
