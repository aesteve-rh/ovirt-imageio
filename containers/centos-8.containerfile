FROM quay.io/centos/centos:stream8

# Runtime packages.
RUN echo v1 \
    && dnf install -y dnf-plugins-core \
    && dnf copr enable -y \
        ovirt/ovirt-master-snapshot \
        centos-stream-8 \
    && dnf install -y ovirt-release-master \
    && dnf install -y \
        createrepo_c \
        e2fsprogs \
        gcc \
        git \
        libguestfs-tools-c \
        make \
        openssl \
        python3-devel \
        python3-ovirt-engine-sdk4 \
        python3-pip \
        python3-setuptools \
        python3-systemd \
        python38-devel \
        python38-ovirt-engine-sdk4 \
        python38-pip \
        python38-setuptools \
        qemu-img \
        qemu-kvm \
        rpm-build \
        sudo \
        systemd-devel \
        systemd-udev \
        util-linux \
        xfsprogs \
    && dnf clean all

# Developemnt tools.
COPY requirements.txt requirements.txt
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install --requirement requirements.txt