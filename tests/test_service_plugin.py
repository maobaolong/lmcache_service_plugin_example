# SPDX-License-Identifier: Apache-2.0
"""Tests for the example LMCache service plugin."""

from __future__ import annotations

import socket

# Standard
from concurrent import futures
from dataclasses import dataclass

# Third Party
import grpc

# First Party
from lmcache.v1.multiprocess.server_module import ServerModuleBuildContext

# Local
from lmcache_service_plugin_example.client import ExampleGrpcClient, ExampleZmqClient
from lmcache_service_plugin_example.server import build_server_modules


@dataclass
class _FakeZmqServer:
    ctx: object


def _unused_tcp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _fake_build_context(*, zmq_bind_url: str = "tcp://127.0.0.1:0"):
    return ServerModuleBuildContext(
        server_context=object(),
        mp_config=object(),
        coordinator_config=object(),
        modules=(),
        config={
            "prefix": "example",
            "zmq_bind_url": zmq_bind_url,
        },
    )


def test_grpc_service_registrar_registers_plugin_owned_service() -> None:
    components = build_server_modules(_fake_build_context())
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    port = server.add_insecure_port("127.0.0.1:0")
    for registrar in components.grpc_service_registrars:
        registrar(server)

    server.start()
    client = ExampleGrpcClient(f"127.0.0.1:{port}")
    try:
        assert "gRPC service is ready" in client.health()
        reply = client.echo("hello", tag="pytest")
    finally:
        client.close()
        server.stop(grace=None)

    assert reply.text == "example:hello"
    assert reply.tag == "pytest"
    assert reply.count == 1


def test_zmq_service_registrar_starts_plugin_owned_sidecar() -> None:
    endpoint = f"tcp://127.0.0.1:{_unused_tcp_port()}"
    components = build_server_modules(_fake_build_context(zmq_bind_url=endpoint))
    module = components.modules[0]
    for registrar in components.zmq_service_registrars:
        registrar(_FakeZmqServer(ctx=object()))

    client = ExampleZmqClient(endpoint)
    try:
        reply = client.echo("hello", tag="pytest")
    finally:
        client.close()
        module.close()

    assert reply.text == "example:hello"
    assert reply.tag == "pytest"
    assert reply.count == 1
