# SPDX-License-Identifier: Apache-2.0
"""Clients for the plugin-owned gRPC and ZMQ service protocols."""

from __future__ import annotations

import argparse

# Standard
from dataclasses import dataclass

# Third Party
import grpc
import msgspec
import zmq

# Local
from .protocol import EchoRequest, EchoResponse
from .protos import example_service_pb2, example_service_pb2_grpc


@dataclass(frozen=True)
class EchoResult:
    """Transport-neutral result returned by example clients."""

    text: str
    tag: str
    count: int


class ExampleGrpcClient:
    """Client for the plugin-owned generated gRPC service."""

    def __init__(self, target: str) -> None:
        self._channel = grpc.insecure_channel(target)
        self._stub = example_service_pb2_grpc.ExampleServiceStub(self._channel)

    def echo(self, text: str, *, tag: str = "", timeout: float = 5) -> EchoResult:
        """Call the plugin-owned gRPC Echo method."""
        reply = self._stub.Echo(
            example_service_pb2.EchoRequest(text=text, tag=tag),
            timeout=timeout,
        )
        return EchoResult(text=reply.text, tag=reply.tag, count=reply.count)

    def health(self, *, timeout: float = 5) -> str:
        """Call the plugin-owned gRPC Health method."""
        reply = self._stub.Health(example_service_pb2.HealthRequest(), timeout=timeout)
        if not reply.ok:
            raise RuntimeError(reply.message)
        return reply.message

    def close(self) -> None:
        """Close the gRPC channel."""
        self._channel.close()


class ExampleZmqClient:
    """Client for the plugin-owned ZMQ sidecar protocol."""

    def __init__(self, endpoint: str) -> None:
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.REQ)
        self._socket.linger = 0
        self._socket.connect(endpoint)

    def echo(self, text: str, *, tag: str = "", timeout: float = 5) -> EchoResult:
        """Call the plugin-owned ZMQ echo service."""
        self._socket.send(msgspec.msgpack.encode(EchoRequest(text=text, tag=tag)))
        if not self._socket.poll(int(timeout * 1000)):
            raise TimeoutError("timed out waiting for ZMQ plugin reply")
        payload = self._socket.recv()
        response = msgspec.msgpack.decode(payload, type=EchoResponse)
        if not response.ok:
            raise RuntimeError(response.error)
        if response.reply is None:
            raise RuntimeError("ZMQ plugin reply did not include an EchoReply")
        reply = response.reply
        return EchoResult(text=reply.text, tag=reply.tag, count=reply.count)

    def close(self) -> None:
        """Close the ZMQ client socket."""
        self._socket.close(linger=0)


def main() -> None:
    """Run a small CLI client for manual verification."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=("grpc", "zmq"), required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--text", default="hello")
    parser.add_argument("--tag", default="manual")
    args = parser.parse_args()

    if args.transport == "grpc":
        client = ExampleGrpcClient(args.target)
        try:
            print(client.health())
            print(client.echo(args.text, tag=args.tag))
        finally:
            client.close()
    else:
        client = ExampleZmqClient(args.target)
        try:
            print(client.echo(args.text, tag=args.tag))
        finally:
            client.close()


if __name__ == "__main__":
    main()
