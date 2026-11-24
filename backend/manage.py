"""Developer entry point: `uv run python manage.py <command>`.

  migrate          apply database migrations (alembic upgrade head)
  seed [--reset]   load clearly-labelled demo data (--reset wipes the database first)
  serve [--port N] [--reload]   run the API server

Running through this script (instead of the alembic/uvicorn executables) keeps the
environment consistent across Windows/macOS/Linux; see app/__init__.py.
"""

import argparse
import os
import sys

os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    seed = sub.add_parser("seed")
    seed.add_argument("--reset", action="store_true")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    if args.cmd == "migrate":
        from alembic.config import main as alembic_main

        alembic_main(argv=["upgrade", "head"])
    elif args.cmd == "seed":
        from app.seed import run

        run(reset=args.reset)
    elif args.cmd == "serve":
        import uvicorn

        # Open live-refresh streams never finish on their own; without a timeout Ctrl+C would wait for
        # every browser tab to close.
        uvicorn.run(
            "app.main:app", host=args.host, port=args.port, reload=args.reload, timeout_graceful_shutdown=2
        )
    else:  # pragma: no cover
        sys.exit(2)


if __name__ == "__main__":
    main()
