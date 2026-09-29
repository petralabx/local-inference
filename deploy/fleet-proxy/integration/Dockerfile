# Disposable fleet-proxy host for the integration test (agent fleet spec P1).
# Ubuntu 24.04 with systemd as PID 1, like the EC2 host. The image holds
# systemd and the test tools only. in-host.sh installs the README packages
# (PostgreSQL among them) and the fleet proxy, step by step from README.md.
# Never use this image for a real host.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      systemd systemd-sysv dbus curl ca-certificates iproute2 procps \
 && rm -rf /var/lib/apt/lists/*
# No consoles or logins in a container.
RUN systemctl mask getty.target console-getty.service systemd-logind.service \
      systemd-firstboot.service
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
