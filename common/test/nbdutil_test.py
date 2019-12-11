# ovirt-imageio
# Copyright (C) 2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from __future__ import absolute_import

import pytest

from ovirt_imageio_common import nbd
from ovirt_imageio_common import nbdutil


class Client:

    export_size = 6 * 1024**3

    def __init__(self, zero):
        self.zero = zero

    def extents(self, offset, length):
        assert 0 < length <= nbd.MAX_LENGTH
        assert offset + length <= self.export_size
        return self.reply(offset, length)

    def reply(self):
        raise NotImplementedError


class CompleteReply(Client):
    """
    Return what you asked for.
    """

    def reply(self, offset, length):
        return {"base:allocation": [nbd.Extent(length, self.zero)]}


class SingleExtent(Client):
    """
    Return short reply with single extent until user ask for the last extent.
    """

    def reply(self, offset, length):
        length = min(length, 128 * 1024**2)
        return {"base:allocation": [nbd.Extent(length, self.zero)]}


class ShortReply(Client):
    """
    Return short reply with multiple extents until user ask for the last
    extent.
    """

    def reply(self, offset, length):
        max_extent = 128 * 1024**2

        if length > max_extent:
            length -= max_extent

        extents = []
        while length > max_extent:
            extents.append(nbd.Extent(max_extent, self.zero))
            length -= max_extent

        extents.append(nbd.Extent(length, self.zero))

        return {"base:allocation": extents}


class ExcceedsLength(Client):
    """
    Return length + extra bytes in 2 extents until the caller ask for the last
    extent. The spec does not allow returning one extents exceeding requested
    range.
    """

    def reply(self, offset, length):
        extra = 128 * 1024**2

        if offset + length + extra < self.export_size and length > extra:
            extents = [
                nbd.Extent(length - extra, self.zero),
                nbd.Extent(2 * extra, self.zero),
            ]
        else:
            extents = [nbd.Extent(length, self.zero)]

        return {"base:allocation": extents}


class SomeData(Client):
    """
    Return even extents as data, odd extents as zero.
    """

    def __init__(self):
        pass

    extent_size = 2 * 1024**3

    def reply(self, offset, length):
        index = offset // self.extent_size
        zero = bool(index % 2)

        max_length = self.extent_size - (offset % self.extent_size)
        length = min(length, max_length)

        return {"base:allocation": [nbd.Extent(length, zero)]}


OFFSET_PARAMS = [
    pytest.param(0, id="stat to end"),
    pytest.param(2 * 1024**3, id="offset to end"),
]

OFFSET_LENGTH_PARAMS = [
    pytest.param(0, Client.export_size, id="start to export_size"),
    pytest.param(0, 2 * 1024**3, id="head"),
    pytest.param(2 * 1024**3, 2 * 1024**3, id="middle"),
    pytest.param(Client.export_size - 2 * 1024**3, 2 * 1024**3, id="tail"),
]


@pytest.mark.parametrize("zero", [True, False])
def test_complete_reply(zero):
    c = CompleteReply(zero)
    extents = list(nbdutil.extents(c))
    assert extents == [nbd.Extent(c.export_size, zero)]


@pytest.mark.parametrize("zero", [True, False])
@pytest.mark.parametrize("offset", OFFSET_PARAMS)
def test_complete_reply_offset(zero, offset):
    c = CompleteReply(zero)
    extents = list(nbdutil.extents(c, offset=offset))
    assert extents == [nbd.Extent(c.export_size - offset, zero)]


@pytest.mark.parametrize("zero", [True, False])
@pytest.mark.parametrize("offset,length", OFFSET_LENGTH_PARAMS)
def test_complete_reply_offset_length(zero, offset, length):
    c = CompleteReply(zero)
    extents = list(nbdutil.extents(c, offset=offset, length=length))
    assert extents == [nbd.Extent(length, zero)]


@pytest.mark.parametrize("zero", [True, False])
def test_single_extent(zero):
    c = SingleExtent(zero)
    extents = list(nbdutil.extents(c))
    assert extents == [nbd.Extent(c.export_size, zero)]


@pytest.mark.parametrize("zero", [True, False])
@pytest.mark.parametrize("offset", OFFSET_PARAMS)
def test_single_extent_offset(zero, offset):
    c = SingleExtent(zero)
    extents = list(nbdutil.extents(c, offset=offset))
    assert extents == [nbd.Extent(c.export_size - offset, zero)]


@pytest.mark.parametrize("zero", [True, False])
@pytest.mark.parametrize("offset,length", OFFSET_LENGTH_PARAMS)
def test_single_extent_offset_length(zero, offset, length):
    c = SingleExtent(zero)
    extents = list(nbdutil.extents(c, offset=offset, length=length))
    assert extents == [nbd.Extent(length, zero)]


@pytest.mark.parametrize("zero", [True, False])
def test_short_reply(zero):
    c = ShortReply(zero)
    extents = list(nbdutil.extents(c))
    assert extents == [nbd.Extent(c.export_size, zero)]


@pytest.mark.parametrize("zero", [True, False])
@pytest.mark.parametrize("offset", OFFSET_PARAMS)
def test_short_reply_offset(zero, offset):
    c = ShortReply(zero)
    extents = list(nbdutil.extents(c, offset=offset))
    assert extents == [nbd.Extent(c.export_size - offset, zero)]


@pytest.mark.parametrize("zero", [True, False])
@pytest.mark.parametrize("offset,length", OFFSET_LENGTH_PARAMS)
def test_short_reply_offset_length(zero, offset, length):
    c = ShortReply(zero)
    extents = list(nbdutil.extents(c, offset=offset, length=length))
    assert extents == [nbd.Extent(length, zero)]


@pytest.mark.parametrize("zero", [True, False])
@pytest.mark.parametrize("offset,length", OFFSET_LENGTH_PARAMS)
def test_last_extent_exceeds_length(zero, offset, length):
    c = ExcceedsLength(zero)
    extents = list(nbdutil.extents(c, offset=offset, length=length))
    assert extents == [nbd.Extent(length, zero)]


def test_some_data():
    c = SomeData()
    extents = list(nbdutil.extents(c))
    assert extents == [
        nbd.Extent(c.extent_size, False),
        nbd.Extent(c.extent_size, True),
        nbd.Extent(c.extent_size, False),
    ]


def test_some_data_offset():
    c = SomeData()
    extents = list(nbdutil.extents(c, offset=0))
    assert extents == [
        nbd.Extent(c.extent_size, False),
        nbd.Extent(c.extent_size, True),
        nbd.Extent(c.extent_size, False),
    ]


def test_some_data_offset_length():
    c = SomeData()
    extents = list(nbdutil.extents(c, offset=0, length=c.export_size))
    assert extents == [
        nbd.Extent(c.extent_size, False),
        nbd.Extent(c.extent_size, True),
        nbd.Extent(c.extent_size, False),
    ]


def test_some_data_offset_unaligned():
    c = SomeData()
    extents = list(nbdutil.extents(c, offset=c.extent_size // 2 * 3))
    assert extents == [
        nbd.Extent(c.extent_size // 2, True),
        nbd.Extent(c.extent_size, False),
    ]


def test_some_data_offset_length_unaligned():
    c = SomeData()
    extents = list(nbdutil.extents(
        c, offset=c.extent_size // 2, length=c.extent_size * 2))
    assert extents == [
        nbd.Extent(c.extent_size // 2, False),
        nbd.Extent(c.extent_size, True),
        nbd.Extent(c.extent_size // 2, False),
    ]