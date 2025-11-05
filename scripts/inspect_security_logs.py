"""
Utility script for inspecting security-relevant application logs.

This script extracts recent docker logs for the telegram2notion service and
filters them for warning or error messages that indicate rejected or suspicious
webhook traffic. It is intended for manual use when auditing the system for
potential unauthorized access attempts.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict
from typing import DefaultDict, Iterable, List, Tuple


DEFAULT_CONTAINER_NAME = "telegram2notion"
DEFAULT_SINCE = "24h"
SECURITY_KEYWORDS: List[str] = [
    "Webhook rejected",
    "Invalid secret token",
    "Forbidden source IP",
    "Missing X-Telegram-Bot-Api-Secret-Token",
    "Unable to determine client IP",
    "unsupported content type",
    "Invalid IP address string received",
]


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    """
    Parses CLI arguments for runtime configuration.
    Args:
        argv: Iterable of command line arguments, typically sys.argv[1:].
    Returns:
        Namespace: Parsed arguments containing the container name and since duration.
    """
    parser = argparse.ArgumentParser(
        description="Inspect security-relevant webhook log entries for telegram2notion."
    )
    parser.add_argument(
        "--container",
        default=DEFAULT_CONTAINER_NAME,
        help=f"Docker container to read logs from (default: {DEFAULT_CONTAINER_NAME}).",
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        help=(
            "Fetch logs since the given duration or timestamp (passed to docker logs --since). "
            f"Default: {DEFAULT_SINCE}."
        ),
    )
    return parser.parse_args(list(argv))


def resolve_container_name(requested: str) -> Tuple[str, List[str]]:
    """
    Resolves the docker container name against existing containers.
    Args:
        requested: The container name or prefix supplied by the user.
    Returns:
        Tuple[str, List[str]]: The container name to use and the list of available names.
    Raises:
        RuntimeError: If docker ps fails.
    """
    command = ["docker", "ps", "-a", "--format", "{{.Names}}"]
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        raise RuntimeError(f"Failed to list docker containers: {process.stderr.strip()}")
    available = [name.strip() for name in process.stdout.splitlines() if name.strip()]
    if requested in available:
        return requested, available
    prefixed = [name for name in available if name.startswith(requested)]
    if prefixed:
        return prefixed[0], available
    return "", available


def collect_logs(container: str, since: str) -> List[str]:
    """
    Retrieves docker logs for the specified container.
    Args:
        container: Name of the docker container to inspect.
        since: Duration/timestamp forwarded to docker's --since flag.
    Returns:
        List[str]: Log lines captured from the container.
    Raises:
        RuntimeError: If the docker command fails.
    """
    command = [
        "docker",
        "logs",
        "--since",
        since,
        container,
    ]
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        raise RuntimeError(
            f"Failed to collect logs from container '{container}': {process.stderr.strip()}"
        )
    return process.stdout.splitlines()


def filter_security_events(lines: Iterable[str]) -> DefaultDict[str, List[str]]:
    """
    Filters log lines for configured security keywords.
    Args:
        lines: Iterable of log lines to inspect.
    Returns:
        defaultdict: Mapping from keyword to matched lines.
    """
    matches: DefaultDict[str, List[str]] = defaultdict(list)
    for line in lines:
        lowered = line.lower()
        for keyword in SECURITY_KEYWORDS:
            if keyword.lower() in lowered:
                matches[keyword].append(line)
    return matches


def print_report(
    matches: DefaultDict[str, List[str]],
    container: str,
    since: str,
) -> None:
    """
    Prints a formatted report of the detected log events.
    Args:
        matches: Mapping of keywords to log lines.
        container: Name of the inspected container.
        since: Duration/timestamp used for log retrieval.
    """
    header = (
        f"=== Security Audit Report ===\n"
        f"Container : {container}\n"
        f"Since     : {since}\n"
        f"Keywords  : {len(SECURITY_KEYWORDS)} monitored\n"
        "=============================="
    )
    print(header)
    if not matches:
        print("✅ No security-relevant log entries detected for the selected time window.")
        return
    for keyword in SECURITY_KEYWORDS:
        lines = matches.get(keyword, [])
        if not lines:
            continue
        print(f"\n--- Matches for '{keyword}' ({len(lines)}) ---")
        for line in lines:
            print(f"⚠️ - {line}")


def main(argv: Iterable[str]) -> None:
    """
    Entry point for the CLI utility.
    Args:
        argv: Iterable of command line arguments (usually sys.argv[1:]).
    """
    args = parse_args(argv)
    try:
        container_name, available = resolve_container_name(args.container)
        if not container_name:
            message_lines = [
                f"No docker container named '{args.container}' could be found.",
            ]
            if available:
                message_lines.append(
                    "Available containers:\n  - " + "\n  - ".join(available)
                )
            else:
                message_lines.append("No docker containers are currently available.")
            print("\n".join(message_lines), file=sys.stderr)
            sys.exit(1)
        if container_name != args.container:
            print(
                f"Container '{args.container}' not found; using '{container_name}' based on prefix match."
            )
        lines = collect_logs(container_name, args.since)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    matches = filter_security_events(lines)
    print_report(matches, container_name, args.since)


if __name__ == "__main__":
    main(sys.argv[1:])
