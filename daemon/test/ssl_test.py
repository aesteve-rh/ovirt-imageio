# ovirt-imageio
# Copyright (C) 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import os
from contextlib import contextmanager

import pytest

from ovirt_imageio_common import configloader
from ovirt_imageio_common.ssl import check_protocol

from ovirt_imageio_daemon import config
from ovirt_imageio_daemon import server

TEST_DIR = os.path.dirname(__file__)


@contextmanager
def images_service(config_file):
    path = os.path.join(TEST_DIR, config_file)
    configloader.load(config, [path])
    s = server.ImagesService(config)
    s.start()
    try:
        yield s
    finally:
        s.stop()


@pytest.mark.parametrize("protocol", ["-ssl2", "-ssl3", "-tls1"])
def test_default_reject(protocol):
    with images_service("daemon.conf") as service:
        rc = check_protocol("127.0.0.1", service.port, protocol)
    assert rc != 0


@pytest.mark.parametrize("protocol", ["-tls1_1", "-tls1_2"])
def test_default_accept(protocol):
    with images_service("daemon.conf") as service:
        rc = check_protocol("127.0.0.1", service.port, protocol)
    assert rc == 0
