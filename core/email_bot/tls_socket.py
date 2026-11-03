from __future__ import annotations

import imaplib
import smtplib
import socket
import ssl
import time

from loguru import logger

PER_IP_TIMEOUT = 4.0


def resolve_ipv4(host: str, port: int, retries: int = 3) -> list[tuple]:
    last_error = None

    for attempt in range(retries):
        try:
            infos = socket.getaddrinfo(
                host,
                port,
                socket.AF_INET,
                socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            continue

        addresses = []
        seen = set()

        for family, socktype, proto, _, address in infos:
            ip = address[0]
            if ip not in seen:
                seen.add(ip)
                addresses.append((family, socktype, proto, address))

        if addresses:
            return addresses

    raise last_error or OSError(f"无法解析 {host}")


def open_tls_socket(host: str, port: int, timeout, context: ssl.SSLContext):
    operation_timeout = timeout if isinstance(timeout, (int, float)) else 15
    handshake_timeout = min(float(operation_timeout), PER_IP_TIMEOUT)
    last_error = None

    for family, socktype, proto, address in resolve_ipv4(host, port):
        ip = address[0]
        raw_socket = socket.socket(family, socktype, proto)
        raw_socket.settimeout(handshake_timeout)

        try:
            raw_socket.connect(address)
            tls_socket = context.wrap_socket(
                raw_socket,
                server_hostname=host,
            )
            tls_socket.settimeout(operation_timeout)
            logger.info("TLS connected: {}:{} via {}", host, port, ip)
            return tls_socket
        except OSError as exc:
            last_error = exc
            raw_socket.close()
            logger.warning("TLS failed: {}:{} via {}: {}", host, port, ip, exc)

    raise last_error or OSError(f"无法连接 {host}:{port}")


class ResilientIMAP4SSL(imaplib.IMAP4_SSL):
    def _create_socket(self, timeout):
        return open_tls_socket(
            self.host,
            self.port,
            timeout,
            self.ssl_context,
        )


class ResilientSMTPSSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        return open_tls_socket(
            host,
            port,
            timeout,
            self.context,
        )