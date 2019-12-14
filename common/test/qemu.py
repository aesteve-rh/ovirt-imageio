# ovirt-imageio
# Copyright (C) 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from __future__ import absolute_import

import logging
import os
import re

from contextlib import contextmanager

from ovirt_imageio_common.compat import subprocess

from . import testutil

QEMU = os.environ.get("QEMU", "qemu-kvm")

log = logging.getLogger("qemu")


def supports_audiodev():
    if not hasattr(supports_audiodev, "result"):
        cmd = [QEMU, "--help"]
        out = subprocess.check_output(cmd, env=env()).decode()
        m = re.search(r"^-audiodev +none\b", out, flags=re.MULTILINE)
        supports_audiodev.result = m is not None
    return supports_audiodev.result


def env():
    """
    Amend PATH to locate qemu-kvm on platforms that hide it in /usr/libexec
    (e.g RHEL).
    """
    env = dict(os.environ)
    env["PATH"] = ":".join((env["PATH"], "/usr/libexec"))
    return env


@contextmanager
def run(image, fmt, qmp_sock, start_cpu=True):
    # NOTES:
    # - Let qemu pick default memory size, since on some platforms memory have
    #   strange alignment. Here is a failure from ppc64le host:
    #       qemu-kvm: Memory size 0x1000000 is not aligned to 256 MiB
    cmd = [
        QEMU,
        # Use kvm if available, othrewise fallback to tcg. This allows running
        # qemu on Travis CI which does not support nested virtualization.
        "-nodefaults",
        "-machine", "accel=kvm:tcg",
        "-drive",
        "if=virtio,id=drive0,node-name=file0,file={},format={}".format(
            image, fmt),
        "-nographic",
        "-net", "none",
        "-monitor", "none",
        "-serial", "stdio",
        "-qmp", "unix:{},server,nowait".format(qmp_sock),
    ]

    # Workaround for bug in qemu-4.0.0-rc0 on Fedora, failing to start VM
    # becuase initilizing real audio driver failed.
    # See https://bugzilla.redhat.com/1692047.
    if supports_audiodev():
        cmd.append("-audiodev")
        cmd.append("none,id=1")

    if not start_cpu:
        cmd.append("-S")

    log.debug("Starting qemu %s", cmd)
    p = subprocess.Popen(
        cmd,
        env=env(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE)
    try:
        if not testutil.wait_for_socket(qmp_sock, 1):
            raise RuntimeError("Timeout waiting for socket: %s" % qmp_sock)
        yield Guest(p)
    finally:
        log.debug("Terminating qemu gracefully")
        p.terminate()
        try:
            p.wait(1)
        except subprocess.TimeoutExpired:
            log.warning("Timeout terminating qemu - killing it")
            p.kill()
            p.wait()
        log.debug("qemu terminated with exit code %s", p.returncode)


class Guest(object):

    def __init__(self, p):
        self._stdin = p.stdin
        self._stdout = p.stdout
        self._logged = False

    def login(self, name, password):
        assert not self._logged
        self._wait_for("login: ")
        self._send(name)
        self._wait_for("Password: ")
        self._send(password)
        self._wait_for("# ")
        self._logged = True

    def run(self, command):
        self._send(command)
        return self._wait_for("# ")

    def _send(self, s):
        log.debug("Sending: %r", s)
        self._stdin.write(s.encode("utf-8") + b"\n")
        self._stdin.flush()
        self._wait_for(s + "\r\n")

    def _wait_for(self, s):
        log.debug("Waiting for: %r", s)
        data = s.encode("utf-8")
        buf = bytearray()
        while True:
            buf += self._stdout.read(1)
            if buf.endswith(data):
                rep = buf[:-len(data)]
                return rep.decode("utf-8")
