"""Command line: ``protopitch serve | worker | migrate | probe | openapi``."""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
from dataclasses import asdict
from types import FrameType

from protopitch.logging_setup import configure_logging, get_logger

log = get_logger("cli")


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from protopitch.api.app import create_app
    from protopitch.settings import load_settings

    settings = load_settings()
    host = args.host or settings.server.host
    port = args.port or settings.server.port
    app = create_app(settings)
    worker: subprocess.Popen[bytes] | None = None
    if args.with_worker:
        worker = subprocess.Popen([sys.executable, "-m", "protopitch.cli", "worker"])
    try:
        uvicorn.run(app, host=host, port=port, log_config=None, access_log=False)
    finally:
        if worker is not None:
            worker.terminate()
            try:
                worker.wait(timeout=20)
            except subprocess.TimeoutExpired:
                worker.kill()
    return 0


def _worker(_args: argparse.Namespace) -> int:
    from protopitch.context import build_context

    ctx = build_context()
    worker = ctx.make_worker()

    def stop(_signum: int, _frame: FrameType | None) -> None:
        worker.request_stop()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    removed = ctx.sandbox.remove_exited()
    if removed:
        log.info("removed leftover sandbox containers", extra={"count": removed})
    worker.run_forever()
    ctx.close()
    return 0


def _migrate(_args: argparse.Namespace) -> int:
    from protopitch.context import build_context

    build_context().close()
    return 0


def _probe(_args: argparse.Namespace) -> int:
    from protopitch.sandbox.docker import build_sandbox_driver
    from protopitch.settings import load_settings

    capability = build_sandbox_driver(load_settings()).probe()
    sys.stdout.write(json.dumps(asdict(capability), indent=2) + "\n")
    return 0 if capability.available else 1


def _openapi(_args: argparse.Namespace) -> int:
    from fastapi import FastAPI

    from protopitch.api import jobs, projects, system

    app = FastAPI(title="ProtoPitch", version="0.1.0")
    for module in (system, projects, jobs):
        app.include_router(module.router, prefix="/api")
    sys.stdout.write(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="protopitch")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the API and web interface")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument("--with-worker", action="store_true", help="also run one worker")
    serve.set_defaults(func=_serve)
    sub.add_parser("worker", help="run a worker").set_defaults(func=_worker)
    sub.add_parser("migrate", help="create or upgrade the database").set_defaults(func=_migrate)
    sub.add_parser("probe", help="report whether the sandbox is usable").set_defaults(func=_probe)
    sub.add_parser("openapi", help="print the OpenAPI schema").set_defaults(func=_openapi)
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
