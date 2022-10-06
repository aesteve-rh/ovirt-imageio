# Copyright (C) 2022 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import json
import logging
import os
import stat
import subprocess
import time
import shutil
from collections import namedtuple
import http.client as http_client

import pytest

from ovirt_imageio._internal.units import KiB

from . import testutil
from . import http


log = logging.getLogger("test")

FILE_SIZE = 16 * KiB
CONTAINER_IMG_PATH = "/image/disk.raw"
CONTAINER_TICKET_PATH = "/ticket/file.json"
CONTAINER_IMAGE = "localhost/ovirt-imageio:latest"

Server = namedtuple("Server", ["host", "port"])
Ticket = namedtuple("Ticket", ["id", "path"])


def _imageio_image_missing():
    podman_cmd = "podman"
    if shutil.which(podman_cmd) is None:
        return True
    cmd = [podman_cmd, "image", "inspect", CONTAINER_IMAGE]
    try:
        return subprocess.check_call(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        return True


@pytest.fixture
def tmp_image(tmpdir):
    image_path = tmpdir.mkdir("image")
    image = testutil.create_tempfile(
        image_path, name=os.path.basename(CONTAINER_IMG_PATH), size=FILE_SIZE)
    os.chmod(image, stat.S_IROTH | stat.S_IWOTH)
    return str(image)


@pytest.fixture
def tmp_ticket(tmpdir):
    ticket = testutil.create_ticket(
        size=FILE_SIZE, url=f'file://{CONTAINER_TICKET_PATH}')
    ticket_dir = tmpdir.mkdir("ticket")
    ticket_path = ticket_dir.join(os.path.basename(CONTAINER_TICKET_PATH))
    ticket_path.write(json.dumps(ticket))
    os.chmod(ticket_path, stat.S_IROTH | stat.S_IWOTH)
    return Ticket(ticket["uuid"], str(ticket_path))


def _wait_for_server(port, timeout):
    start = time.monotonic()
    deadline = start + timeout
    conn = http_client.HTTPConnection("localhost", port)
    while True:
        try:
            conn.connect()
        except ConnectionRefusedError:
            now = time.monotonic()
            if now >= deadline:
                return False
            time.sleep(0.25)
        else:
            log.debug("Waited for %.6f seconds", time.monotonic() - start)
            return True


@pytest.fixture
def srv(tmp_ticket, tmp_image):
    random_port = testutil.random_tcp_port()
    cmd = ["podman", "run", "--rm", "--privileged", "-it"]
    # Port redirect.
    cmd.extend(("-p", f"{random_port}:80"))
    # Ticket volume.
    cmd.extend(("-v", f"{os.path.dirname(tmp_ticket.path)}"
                      f":{os.path.dirname(CONTAINER_TICKET_PATH)}"))
    # Image volume.
    cmd.extend(("-v", f"{os.path.dirname(tmp_image)}"
                      f":{os.path.dirname(CONTAINER_IMG_PATH)}:Z"))
    # Ticket path environment.
    cmd.extend(("--env", f"TICKET_PATH={CONTAINER_TICKET_PATH}"))
    cmd.append(CONTAINER_IMAGE)
    # Run command.
    srv_proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Wait for server to start.
    if not _wait_for_server(random_port, timeout=5):
        log.error("Dumping server logs:")
        #if srv_proc.stdout is not None:
        #    log.warning("%s", srv_proc.stdout.read().decode("utf-8"))
        #if srv_proc.stderr is not None:
        #    log.error("%s", srv_proc.stderr.read().decode("utf-8"))
        pytest.fail("Server could not start")
    yield Server("localhost", random_port)
    srv_proc.terminate()


@pytest.mark.xfail(
    reason="Container image not found",
    strict=True,
    condition=_imageio_image_missing())
def test_containerized_server(srv, tmp_ticket):
    data = b"a" * (FILE_SIZE // 2) + b"b" * (FILE_SIZE // 2)
    conn = http_client.HTTPConnection(srv.host, srv.port)
    # Test that we can upload.
    with http.HTTPClient(conn) as c:
        res = c.put(f"/images/{tmp_ticket.id}", data)
        assert res.status == http_client.OK
    # Test that we can download and matches the uploaded data.
    with http.HTTPClient(conn) as c:
        res = c.get(f"/images/{tmp_ticket.id}")
        assert res.read() == data
        assert res.status == http_client.OK
