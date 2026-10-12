# SPDX-License-Identifier: Apache-2.0
"""LMCache server-module entry point for the example service plugin."""

from __future__ import annotations

# Standard
from typing import Any

# Third Party
import grpc

# First Party
from lmcache.v1.multiprocess.engine_module import (
    DiscoverableModule,
    EngineModule,
    ModuleBuildContext,
)

# Local
from .grpc_service import add_example_service_to_server
from .zmq_service import ZmqEchoService

DEFAULT_ZMQ_BIND_URL = "tcp://127.0.0.1:6011"


class ExampleServiceModule(DiscoverableModule):
    """LMCache module wrapper that owns service lifecycle and status.

    Args:
        lmcache_context: Shared LMCache server context.
        config: Plugin-specific JSON config from ``--server-module``.
    """

    module_name = "lmcache_service_plugin_example"

    @classmethod
    def create(cls, build_ctx: ModuleBuildContext) -> EngineModule | None:
        """Construct the plugin through LMCache's shared module contract."""
        return cls(
            build_ctx.engine_context,
            dict(build_ctx.config_for(cls)),
        )

    def __init__(self, lmcache_context: Any, config: dict[str, Any]) -> None:
        self._lmcache_context = lmcache_context
        self._config = config
        self._zmq_service: ZmqEchoService | None = None

    @property
    def context(self) -> Any:
        """Return the shared LMCache server context."""
        return self._lmcache_context

    def report_status(self) -> dict[str, Any]:
        """Return plugin service status for LMCache's aggregated status."""
        return {
            "lmcache_service_plugin_example": {
                "grpc_service": "registered when LMCache transport is grpc",
                "zmq_bind_url": self._config.get("zmq_bind_url", DEFAULT_ZMQ_BIND_URL),
                "zmq_running": (
                    self._zmq_service.is_running
                    if self._zmq_service is not None
                    else False
                ),
            }
        }

    def close(self) -> None:
        """Stop package-owned sidecar resources."""
        if self._zmq_service is not None:
            self._zmq_service.close()
            self._zmq_service = None

    def register_grpc_services(self, server: grpc.Server) -> None:
        """Register the plugin-owned generated gRPC service.

        Args:
            server: Concrete ``grpc.Server`` supplied by LMCache's gRPC
                transport during server startup.
        """
        add_example_service_to_server(
            server,
            self._lmcache_context,
            prefix=str(self._config.get("prefix", "plugin")),
        )

    def register_zmq_services(self, server: Any) -> None:
        """Start the plugin-owned ZMQ sidecar service.

        Args:
            server: Concrete LMCache ``MessageQueueServer``. The example uses
                this object only as the registrar anchor; its protocol remains
                package-owned and runs on ``zmq_bind_url``.
        """
        if self._zmq_service is not None:
            return
        self._zmq_service = ZmqEchoService(
            getattr(server, "ctx", self._lmcache_context),
            str(self._config.get("zmq_bind_url", DEFAULT_ZMQ_BIND_URL)),
            prefix=str(self._config.get("prefix", "plugin")),
        )
        self._zmq_service.start()
