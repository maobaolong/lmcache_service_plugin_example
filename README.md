# LMCache service plugin example

This repository is a minimal out-of-tree LMCache server extension package.
It demonstrates the preferred pattern for plugin-owned services and protocols:

- the plugin owns `src/lmcache_service_plugin_example/protos/example_service.proto`
- the plugin owns the generated gRPC client/server stubs
- the plugin owns a ZMQ sidecar protocol defined with `msgspec`
- LMCache explicitly imports this package's `DiscoverableModule` subclass and
  calls the service registrar method for the selected transport

The `SERVER_MODULE_CALL(method, payload)` envelope is still useful for small
control-plane calls, but this example intentionally uses first-class
plugin-owned services for the runtime API.

## Repository layout

```text
src/lmcache_service_plugin_example/
  server.py          # LMCache --server-module entry point
  grpc_service.py    # plugin-owned generated gRPC service implementation
  zmq_service.py     # plugin-owned ZMQ sidecar service implementation
  client.py          # plugin-owned gRPC and ZMQ clients
  protocol.py        # plugin-owned ZMQ msgpack schema
  protos/
    example_service.proto
```

## Install against an LMCache checkout

Use an LMCache checkout that includes the unified external
`DiscoverableModule` API. Install LMCache first so its Python runtime
dependencies, including `torch`, are available.

```bash
cd /path/to/LMCache
NO_NATIVE_EXT=1 uv pip install -e .

cd /path/to/lmcache_service_plugin_example
uv pip install -e ".[dev]"
```

If you do not use `uv`, the same editable installs work with `pip`.

## Regenerate gRPC bindings

The generated files are checked in so users can install the example directly.
Regenerate them after changing the proto. Use the same environment you use for
LMCache so the generated protobuf code does not require a newer runtime than
LMCache has installed:

```bash
python -m grpc_tools.protoc \
  -I src \
  --python_out=src \
  --grpc_python_out=src \
  --pyi_out=src \
  src/lmcache_service_plugin_example/protos/example_service.proto
```

## Enable the plugin with LMCache gRPC transport

Start the LMCache server with the example package installed:

```bash
lmcache server \
  --mp-transport grpc \
  --host 127.0.0.1 \
  --port 65432 \
  --server-module '{
    "module_path": "lmcache_service_plugin_example.server",
    "config": {"prefix": "example"}
  }'
```

Verify the plugin-owned generated gRPC service:

```bash
lmcache-service-plugin-client \
  --transport grpc \
  --target 127.0.0.1:65432 \
  --text hello \
  --tag grpc-demo
```

Expected output includes:

```text
lmcache_service_plugin_example gRPC service is ready
EchoResult(text='example:hello', tag='grpc-demo', count=1)
```

The request does not go through LMCache's opaque extension envelope. It uses
the service and message types generated from this repository's proto file.

## Enable the plugin with LMCache ZMQ transport

The ZMQ transport keeps the LMCache core socket on `--host/--port`. The plugin
starts a package-owned sidecar socket at `config.zmq_bind_url`.

```bash
lmcache server \
  --mp-transport zmq \
  --host 127.0.0.1 \
  --port 65432 \
  --server-module '{
    "module_path": "lmcache_service_plugin_example.server",
    "config": {
      "prefix": "example",
      "zmq_bind_url": "tcp://127.0.0.1:6011"
    }
  }'
```

Verify the plugin-owned ZMQ protocol:

```bash
lmcache-service-plugin-client \
  --transport zmq \
  --target tcp://127.0.0.1:6011 \
  --text hello \
  --tag zmq-demo
```

Expected output:

```text
EchoResult(text='example:hello', tag='zmq-demo', count=1)
```

## Run tests

After installing LMCache and this plugin, run:

```bash
uv run --extra dev pytest -q
```

To test this branch against the matching LMCache PR checkout, place the two
repositories next to each other, activate a Python 3.12 environment containing
LMCache's development dependencies, and run:

```bash
PYTHONPATH="$PWD/src:../LMCache" python -m pytest -vv \
  -o log_cli=true --log-cli-level=INFO
```

The tests compose the plugin with LMCache's built-in dependency graph, then
exercise the plugin-owned generated gRPC service and package-owned ZMQ sidecar
through the same registrars LMCache calls at server startup. The composition
test also captures LMCache's module count and dependency log.
