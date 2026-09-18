# SPDX-License-Identifier: Apache-2.0
"""Plugin-owned ZMQ wire protocol messages."""

from __future__ import annotations

# Third Party
import msgspec


class EchoRequest(msgspec.Struct):
    """Request body for the package-owned ZMQ echo service."""

    text: str
    tag: str = ""


class EchoReply(msgspec.Struct):
    """Successful response body for the package-owned ZMQ echo service."""

    text: str
    tag: str
    count: int


class EchoResponse(msgspec.Struct):
    """Top-level ZMQ response envelope owned by this plugin package."""

    ok: bool
    reply: EchoReply | None = None
    error: str = ""
