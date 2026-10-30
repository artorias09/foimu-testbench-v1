import argparse
import json
import math
import sys
from .config import load_config, validate_config
from .runners import demo, serve, acquire, replay


def positive(value):
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive and finite")
    return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(description="FO-IMU digital interface testbench (synthetic, no optical physics)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("demo", "simulate", "acquire", "replay"):
        item = sub.add_parser(name)
        item.add_argument("--config")
        if name != "simulate":
            item.add_argument("--out", required=True, help="New output directory; existing directories are never overwritten")
        if name in ("demo", "simulate"):
            item.add_argument("--packets", type=int)
        if name == "demo":
            item.add_argument("--no-record", action="store_true", help="Metrics only; no wire, CSV or chunk files")
        if name in ("simulate", "acquire"):
            item.add_argument("--host", default="127.0.0.1")
            item.add_argument("--port", type=int, default=8765)
        if name == "simulate":
            item.add_argument("--disconnect-at", type=int, help="Force one TCP disconnect before this zero-based frame index")
        if name == "acquire":
            item.add_argument("--seconds", type=positive, default=30.0)
            item.add_argument("--max-packets", type=int)
        if name == "replay":
            item.add_argument("--input", required=True)
            item.add_argument("--timing", help="chunks.jsonl from a capture; otherwise arrival timing is invented")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if getattr(args, "packets", None) is not None:
            config["packets"] = args.packets
        config = validate_config(config)
        if getattr(args, "max_packets", None) is not None and args.max_packets <= 0:
            raise ValueError("max-packets must be positive")
        if args.command == "demo":
            result = demo(config, args.out, not args.no_record)
        elif args.command == "simulate":
            result = serve(config, args.host, args.port, args.disconnect_at)
        elif args.command == "acquire":
            result = acquire(config, args.out, args.host, args.port, args.seconds, args.max_packets)
        else:
            result = replay(config, args.out, args.input, args.timing)
        metrics = result.get("metrics", result)
        print(json.dumps({key: value for key, value in metrics.items() if not isinstance(value, dict)}, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
