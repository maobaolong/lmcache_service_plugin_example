# SPDX-License-Identifier: Apache-2.0
"""Plugin-owned ZMQ sidecar service implementation."""

from __future__ import annotations

import threading

# Standard
from typing import Any

# Third Party
import msgspec
import zmq

# Local
from .protocol import EchoReply, EchoRequest, EchoResponse


class ZmqEchoService:
    """Small package-owned ZMQ service started by the LMCache registrar.

    Args:
        lmcache_context: Shared LMCache server context supplied to the plugin
            module.
        bind_url: ZMQ endpoint for the sidecar service.
        prefix: Prefix added to each echo response.
    """

    def __init__(
        self,
        lmcache_context: Any,
        bind_url: str,
        *,
        prefix: str = "plugin",
    ) -> None:
        self._lmcache_context = lmcache_context
        self._bind_url = bind_url
        self._prefix = prefix
        self._context = zmq.Context.instance()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._count = 0
        self._lock = threading.Lock()

    @property
    def bind_url(self) -> str:
        """Return the sidecar service bind URL."""
        return self._bind_url

    @property
    def is_running(self) -> bool:
        """Return whether the sidecar worker thread has started."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the sidecar ZMQ service thread."""
        if self.is_running:
            return
        self._thread = threading.Thread(
            target=self._serve,
            name="lmcache-plugin-example-zmq",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError(f"ZMQ plugin service failed to bind {self._bind_url}")

    def close(self) -> None:
        """Stop the sidecar ZMQ service thread."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _serve(self) -> None:
        _ = self._lmcache_context
        socket = self._context.socket(zmq.REP)
        socket.linger = 0
        poller = zmq.Poller()
        try:
            socket.bind(self._bind_url)
            poller.register(socket, zmq.POLLIN)
            self._ready.set()
            while not self._stop.is_set():
                events = dict(poller.poll(timeout=100))
                if socket not in events:
                    continue
                try:
                    request = msgspec.msgpack.decode(socket.recv(), type=EchoRequest)
                    reply = self._handle_echo(request)
                    socket.send(
                        msgspec.msgpack.encode(EchoResponse(ok=True, reply=reply))
                    )
                except Exception as exc:
                    socket.send(
                        msgspec.msgpack.encode(EchoResponse(ok=False, error=str(exc)))
                    )
        finally:
            poller.unregister(socket)
            socket.close(linger=0)

    def _handle_echo(self, request: EchoRequest) -> EchoReply:
        with self._lock:
            self._count += 1
            count = self._count
        return EchoReply(
            text=f"{self._prefix}:{request.text}",
            tag=request.tag,
            count=count,
        )
