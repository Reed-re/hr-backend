from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
import ssl
import asyncio
from .tls_socket import ResilientSMTPSSL

class SmtpClient:
    """A tiny SMTP client wrapped with asyncio.to_thread."""

    def __init__(
        self,
        host: str,
        port: int = 587,
        *,
        starttls: bool = True,
    ):
        self._host = host
        self._port = port
        self._starttls = starttls
        self._conn: smtplib.SMTP | None = None

    async def connect(self) -> None:
        def _connect():
            if self._port == 465:
                conn = ResilientSMTPSSL(
                    self._host,
                    self._port,
                    timeout=15,
                    context=ssl.create_default_context(),
                )
            else:
                conn = smtplib.SMTP(
                    self._host,
                    self._port,
                    timeout=15,
                )

            conn.ehlo()

            if self._starttls and self._port != 465:
                conn.starttls(context=ssl.create_default_context())
                conn.ehlo()

            return conn

        last_error = None

        for attempt in range(3):
            try:
                self._conn = _connect()
                return
            except (OSError, smtplib.SMTPException) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)

        raise last_error

    async def login(self, username: str, password: str) -> None:
        if not self._conn:
            raise RuntimeError("SMTP not connected")
        self._conn.login(username, password)

    async def send_message(self, msg: EmailMessage) -> None:
        if not self._conn:
            raise RuntimeError("SMTP not connected")
        self._conn.send_message(msg)

    async def quit(self) -> None:
        if not self._conn:
            return
        try:
            self._conn.quit()
        finally:
            self._conn = None

