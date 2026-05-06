"""Network utilities for the tournament display."""

import socket


def get_local_ip() -> str | None:
    """Return the primary outbound IPv4 address, or None if unavailable.

    Opens a UDP socket destined for an external address. UDP is
    connectionless, so no packets are sent — but the OS picks the
    interface that routes to the internet, and getsockname() reveals
    the LAN IP that other machines on the network would see.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1.0)
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


def get_local_ip_last_octet() -> str | None:
    """Return the last octet of the local IPv4 address, or None."""
    ip = get_local_ip()
    if not ip:
        return None
    parts = ip.split(".")
    if len(parts) != 4:
        return None
    return parts[3]
