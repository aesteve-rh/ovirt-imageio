FROM quay.io/centos/centos:stream9

# Runtime packages.
RUN echo v1 \
    && dnf install -y dnf-plugins-core \
    && dnf copr enable -y ovirt/ovirt-master-snapshot \
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
        qemu-img \
        qemu-kvm \
        rpm-build \
        sudo \
        systemd-udev \
        util-linux \
        xfsprogs \
    && dnf clean all

# Developemnt tools.
COPY requirements.txt requirements.txt
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install --requirement requirements.txt