from typing import Any
from datetime import timedelta

import httpx
from prefect import flow, task
from prefect.cache_policies import INPUTS
from prefect.concurrency.sync import rate_limit

@task(
    retries=3,
    cache_policy=INPUTS,
    cache_expiration=timedelta(days=1)
)
def fetch_stats(github_repo: str) -> dict[str, Any]:
    """Task 1: Fetch the statistics for a GitHub repo"""
    rate_limit("github-api")
    return httpx.get(f"https://api.github.com/repos/{github_repo}").json()


@task
def get_stars(repo_stats: dict[str, Any]) -> int:
    """Task 2: Get the number of stars from GitHub repo statistics"""
    return repo_stats["stargazers_count"]


@flow(log_prints=True)
def show_stars(github_repos: list[str]) -> None:
    """Flow: Show number of GitHub repo stars"""

    # Task 1: Make HTTP requests concurrently
    stats_futures = fetch_stats.map(github_repos)

    # Task 2: Once each concurrent task completes, get the star counts
    stars = get_stars.map(stats_futures).result()

    # Show the results
    for repo, star_count in zip(github_repos, stars):
        print(f"{repo}: {star_count} stars")


# Run the flow
if __name__ == "__main__":
    show_stars([
        "PrefectHQ/prefect",
        "pydantic/pydantic",
        "huggingface/transformers"
    ])
