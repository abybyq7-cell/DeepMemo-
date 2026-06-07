"""Unified local launcher for DeepMemo services."""

import argparse
import subprocess
import sys


def _run(cmd: list[str]) -> int:
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepMemo service launcher")
    parser.add_argument(
        "target",
        choices=["web", "api", "healthcheck"],
        help="Service to start/check",
    )
    parser.add_argument("--web-port", default="8501")
    parser.add_argument("--api-port", default="8000")
    args = parser.parse_args()

    if args.target == "web":
        return _run(
            [
                "streamlit", "run", "frontend/app.py",
                "--server.port",
                args.web_port,
                "--server.address",
                "0.0.0.0",
            ]
        )
    if args.target == "api":
        return _run(
            [
                "uvicorn",
                "backend.api:app",
                "--host",
                "0.0.0.0",
                "--port",
                args.api_port,
            ]
        )
    return _run([sys.executable, "-m", "scripts.healthcheck"])


if __name__ == "__main__":
    raise SystemExit(main())

