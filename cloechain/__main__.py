"""`python -m cloechain --config path/to/config.yaml`"""

from __future__ import annotations

import argparse

from cloechain.runner import run_from_config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run sampling of posterior distribution from a YAML config file."
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to the YAML run configuration."
    )
    args = parser.parse_args()
    run_from_config(args.config)


if __name__ == "__main__":
    main()
