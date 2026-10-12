# SPDX-License-Identifier: Apache-2.0
"""Tests for the example LMCache service plugin."""

from __future__ import annotations

import socket

# Standard
from concurrent import futures
from dataclasses import dataclass
from unittest.mock import MagicMock

# Third Party
import grpc
import pytest

# First Party
from lmcache.v1.multiprocess import server as server_mod
from lmcache.v1.multiprocess.config import MPServerConfig
from lmcache.v1.multiprocess.engine_module import ModuleBuildContext
from lmcache.v1.multiprocess.ext_server_module import ExtServerModuleSpec
from lmcache.v1.multiprocess.modules import engine_driven_transfer as ed_mod
from lmcache.v1.multiprocess.modules import lmcache_driven_transfer as ld_mod
from lmcache.v1.multiprocess.modules import lookup as lookup_mod
from lmcache.v1.multiprocess.modules import p2p_controller as p2p_mod
from lmcache.v1.multiprocess.modules.blend import module as blend_mod
from lmcache.v1.multiprocess.modules.experimental import qstore as qstore_mod

# Local
from lmcache_service_plugin_example.client import ExampleGrpcClient, ExampleZmqClient
from lmcache_service_plugin_example.server import ExampleServiceModule


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
    return ModuleBuildContext(
        engine_context=object(),
        mp_config=MPServerConfig(),
        coordinator_config=object(),
        module_configs={
            ExampleServiceModule: {
                "prefix": "example",
                "zmq_bind_url": zmq_bind_url,
            }
        },
    )


def test_lmcache_composes_plugin_with_builtin_graph(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _stub_init(self, *args, **kwargs):
        return None

    for module_type in [
        lookup_mod.LookupModule,
        p2p_mod.P2PController,
        ld_mod.LMCacheDrivenTransferModule,
        ed_mod.EngineDrivenTransferModule,
        qstore_mod.QStoreModule,
        blend_mod.BlendModule,
    ]:
        monkeypatch.setattr(module_type, "__init__", _stub_init)

    caplog.set_level("INFO", logger="lmcache.v1.multiprocess.server")
    modules = server_mod._build_modules(
        MagicMock(name="ctx"),
        MPServerConfig(
            worker_reap_timeout_seconds=0,
            engine_type="blend",
            supported_transfer_mode="auto",
            enable=["transfer_query"],
            server_modules=[
                ExtServerModuleSpec(
                    "lmcache_service_plugin_example.server",
                    config={"prefix": "example"},
                )
            ],
        ),
        MagicMock(url="", event_reporting=False),
    )

    assert any(isinstance(module, ExampleServiceModule) for module in modules)
    log_message = next(
        message for message in caplog.messages if message.startswith("Composed ")
    )
    assert f"Composed {len(modules)} engine modules" in log_message
    assert all(
        f"{type(module).module_name}(dependencies=[" in log_message
        for module in modules
    )
    assert "blend(dependencies=[lmcache_driven_transfer])" in log_message
    assert "qstore(dependencies=[lmcache_driven_transfer])" in log_message
    assert (
        "kv_events(dependencies=[lmcache_driven_transfer, "
        "engine_driven_transfer])" in log_message
    )
    assert "lmcache_service_plugin_example(dependencies=[])" in log_message


def test_grpc_service_registrar_registers_plugin_owned_service() -> None:
    module = ExampleServiceModule.create(_fake_build_context())
    assert isinstance(module, ExampleServiceModule)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    port = server.add_insecure_port("127.0.0.1:0")
    module.register_grpc_services(server)

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
    module = ExampleServiceModule.create(_fake_build_context(zmq_bind_url=endpoint))
    assert isinstance(module, ExampleServiceModule)
    module.register_zmq_services(_FakeZmqServer(ctx=object()))

    client = ExampleZmqClient(endpoint)
    try:
        reply = client.echo("hello", tag="pytest")
    finally:
        client.close()
        module.close()

    assert reply.text == "example:hello"
    assert reply.tag == "pytest"
    assert reply.count == 1
