"""Command-line interface: init, auth, status, serve."""

from __future__ import annotations

import argparse
import json
import sys

from ytmusic_mcp.auth import (
    auth_status,
    ensure_config_dir,
    is_authenticated,
    setup_auth,
)


def cmd_init(_args: argparse.Namespace) -> None:
    path = ensure_config_dir()
    print(f"Config directory ready: {path}")


def cmd_auth(args: argparse.Namespace) -> None:
    headers_raw: str | None = None
    if args.headers_file:
        with open(args.headers_file, "r", encoding="utf-8") as fh:
            headers_raw = fh.read()
        print(f"Reading headers from: {args.headers_file}")
    else:
        print("YouTube Music — Browser Auth Setup")
        print("=" * 40)
        print()
        print("Steps:")
        print("  1. Open Chrome and go to https://music.youtube.com")
        print("  2. Make sure you're logged in")
        print("  3. Open DevTools (Cmd+Opt+I on macOS) → Network tab")
        print("  4. Click on any request to music.youtube.com")
        print("  5. Right-click the request → Copy → Copy request headers")
        print("  6. Paste below when prompted (finish with Ctrl+D)")
        print()
        print("Tip: pass --headers-file path/to/headers.txt to skip the prompt")
        print()

    try:
        path = setup_auth(headers_raw=headers_raw)
        print(f"\nAuth saved to: {path}")
        print("Run 'ytmusic-mcp status' to verify.")
    except Exception as exc:  # noqa: BLE001
        print(f"\nAuth setup failed: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_status(_args: argparse.Namespace) -> None:
    status = auth_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    if not status.get("authenticated"):
        print("\nNot authenticated. Run 'ytmusic-mcp auth' first.")
        sys.exit(1)
    if not status.get("valid"):
        print(f"\nAuth file exists but validation failed: {status.get('error')}")
        sys.exit(1)
    print(f"\nAuthenticated as: {status.get('account_name', 'unknown')}")


def cmd_serve(_args: argparse.Namespace) -> None:
    """Start the MCP server (stdio transport)."""
    from ytmusic_mcp.server import main as serve_main

    serve_main()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ytmusic-mcp",
        description="YouTube Music MCP server",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize the config directory")
    auth_parser = sub.add_parser("auth", help="Run browser-cookie auth setup")
    auth_parser.add_argument(
        "--headers-file",
        help="File containing raw request headers (skips interactive prompt)",
    )
    sub.add_parser("status", help="Check authentication status")
    sub.add_parser("serve", help="Run the MCP server (stdio)")

    args = parser.parse_args()
    commands = {
        "init": cmd_init,
        "auth": cmd_auth,
        "status": cmd_status,
        "serve": cmd_serve,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
