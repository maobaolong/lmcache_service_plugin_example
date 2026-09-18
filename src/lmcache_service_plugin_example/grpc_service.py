# SPDX-License-Identifier: Apache-2.0
"""Plugin-owned gRPC service implementation."""

from __future__ import annotations

import threading

# Standard
from typing import Any

# Third Party
import grpc

# Local
from .protos import example_service_pb2, example_service_pb2_grpc


class ExampleServiceServicer(example_service_pb2_grpc.ExampleServiceServicer):
    """gRPC servicer owned by the extension package.

    Args:
        lmcache_context: Shared LMCache server context supplied to the plugin
            factory.
        prefix: Prefix added to each echo response so users can verify the
            plugin service handled the request.
    """

    def __init__(self, lmcache_context: Any, prefix: str = "plugin") -> None:
        self._lmcache_context = lmcache_context
        self._prefix = prefix
        self._lock = threading.Lock()
        self._count = 0

    def Echo(
        self,
        request: example_service_pb2.EchoRequest,
        context: grpc.ServicerContext,
    ) -> example_service_pb2.EchoReply:
        """Return a tagged echo response over the plugin-owned proto service."""
        _ = context
        _ = self._lmcache_context
        with self._lock:
            self._count += 1
            count = self._count
        return example_service_pb2.EchoReply(
            text=f"{self._prefix}:{request.text}",
            tag=request.tag,
            count=count,
        )

    def Health(
        self,
        request: example_service_pb2.HealthRequest,
        context: grpc.ServicerContext,
    ) -> example_service_pb2.HealthReply:
        """Report that the plugin-owned gRPC service is registered."""
        _ = request
        _ = context
        return example_service_pb2.HealthReply(
            ok=True,
            message="lmcache_service_plugin_example gRPC service is ready",
        )


def add_example_service_to_server(
    server: grpc.Server,
    lmcache_context: Any,
    *,
    prefix: str = "plugin",
) -> None:
    """Register the plugin-owned generated gRPC service with a gRPC server.

    Args:
        server: Concrete ``grpc.Server`` supplied by LMCache's gRPC transport.
        lmcache_context: Shared LMCache server context from the build context.
        prefix: Prefix added by the example service.
    """
    example_service_pb2_grpc.add_ExampleServiceServicer_to_server(
        ExampleServiceServicer(lmcache_context, prefix=prefix),
        server,
    )
