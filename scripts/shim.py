#!/usr/bin/env python3
"""
This shim is a small utility to work around a current limitation in Prefect's CLI
when running the `prefect deploy` command.

Because Prefect needs to understand the entrypoint's types in order to build the schema,
it requires the entrypoints to be available in the current working directory.
We don't want to track entire repositories here, so we use this shim in order to make this happen.

This is achieved by running the pull steps defined in the `prefect.yaml` file jailed to a temporary directory.
Once the steps are executed, the shim creates a symbolic link to the entrypoints inside the current
working directory referenced by any deployment.

Usage:
    python shim.py [--config PATH] [--] [command [args ...]]
"""
import argparse
import asyncio
import sys
import tempfile
from pathlib import Path
import os
import shutil
import subprocess
from typing import List, Dict, Any

import yaml
from prefect.deployments.steps.core import run_steps as prefect_run_steps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clone repo, link entrypoints, and run a command."
    )
    parser.add_argument(
        "--config", default="prefect.yaml",
        help="Path to prefect.yaml file"
    )
    parser.add_argument(
        "cmd", nargs=argparse.REMAINDER,
        help="Command to run after linking (default: ['prefect', 'deploy', '--all'])"
    )
    return parser.parse_args()


def load_config(path: Path) -> Dict[str, Any]:
    """
    Load the configuration from a YAML file.
    """
    try:
        return yaml.safe_load(path.read_text()) or {}
    except FileNotFoundError:
        print(f"Configuration file not found: {path}", file=sys.stderr)
        sys.exit(1)


def get_top_level_segments(deployments: List[Dict[str, Any]]) -> List[str]:
    """
    Extract top-level segments from deployments' entrypoints.
    These will be used to create the symlinks.
    """
    segments = set()
    for dep in deployments:
        entry = dep.get("entrypoint")
        if not entry:
            continue
        path_part = entry.split(":")[0]
        segments.add(path_part.split("/")[0])
    return sorted(segments)


def should_link(segment: str, base_dir: Path) -> bool:
    """
    Check if we should create a symlink for the entrypoint.
    """
    target = base_dir / segment
    # Skip if exists as file/dir or as symlink
    if target.exists() or target.is_symlink():
        return False
    return True


def link_segments(repo_dir: Path, segments: List[str], base_dir: Path) -> List[Path]:
    """
    Create symbolic links for the specified segments in the base directory.
    """
    links = []
    for seg in segments:
        src = repo_dir / seg
        if not src.exists():
            continue
        dst = base_dir / seg
        dst.symlink_to(src)
        links.append(dst)
    return links


def cleanup_links(links: List[Path]) -> None:
    """
    Removes symbolic links created by the shim.
    """
    for link in links:
        try:
            link.unlink()
        except OSError as e:
            print(f"Failed to remove symlink {link}: {e}", file=sys.stderr)


async def run_steps(
    steps: List[Dict[str, Any]], tmpdir: Path
) -> Dict[str, Any]:
    """
    Hook into the Prefect run_steps function to execute the steps.
    This allows us to run any Prefect-supported steps without writing logic here.

    Add our jail to the steps so that they run in the correct temporary directory.
    """
    # Adjust any set_working_directory steps
    for step in steps:
        cwd_cfg = step.get('prefect.deployments.steps.set_working_directory', {})
        if 'directory' in cwd_cfg:
            cwd_cfg['directory'] = str(tmpdir / cwd_cfg['directory'])
    # Ensure first step sets working dir
    steps.insert(0, {"prefect.deployments.steps.set_working_directory": {"directory": str(tmpdir)}})
    return await prefect_run_steps(steps)


def run_user_command(cmd: List[str], cwd: Path) -> None:
    subprocess.run(cmd, check=True, cwd=str(cwd))


async def orchestrate(args: argparse.Namespace) -> None:
    config = load_config(Path(os.getcwd()).joinpath(args.config))
    base_dir = Path(args.config).resolve().parent
    pull_steps = config.get('pull', [])
    deployments = config.get('deployments', [])

    segments = get_top_level_segments(deployments)

    tempdir = Path(tempfile.mkdtemp(prefix='prefect_clone_'))
    symlinks: List[Path] = []

    try:
        result = await run_steps(pull_steps, tempdir)
        clone_dir = tempdir / result.get('directory', '')

        symlinks = link_segments(clone_dir, [seg for seg in segments if should_link(seg, base_dir)], base_dir)

        command = args.cmd if args.cmd else ['prefect', 'deploy', '--all']
        run_user_command(command, base_dir)

    except Exception as exc:
        print(f"Error during pull steps: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup_links(symlinks)
        shutil.rmtree(tempdir, ignore_errors=True)


def main() -> None:
    args = parse_args()
    asyncio.run(orchestrate(args))


if __name__ == "__main__":
    main()
