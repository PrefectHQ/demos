from datetime import timedelta, datetime
from statistics import mean
from typing import List, Optional
import httpx

from prefect import flow, task
from prefect.tasks import task_input_hash
from prefect.concurrency.sync import rate_limit


@flow(log_prints=True)
def analyze_repo_health(repos: List[str]):
    """Analyze issue health metrics for GitHub repositories"""
    for repo in repos:
        print(f"Analyzing {repo}...")
        
        # Fetch and analyze all issues
        issues = fetch_repo_issues(repo)
        
        # Calculate metrics
        avg_response_time = calculate_response_times(issues)
        resolution_rate = calculate_resolution_rate(issues)
        
        print(f"Average response time: {avg_response_time:.1f} hours")
        print(f"Resolution rate: {resolution_rate:.1f}%")


@flow
def fetch_repo_issues(repo: str):
    """Fetch all issues for a single repository"""
    all_issues = []
    page = 1
    
    for page in range(1, 3):  # Limit to 2 pages to avoid hitting rate limits
        issues = fetch_page_of_issues(repo, page)
        if not issues or len(issues) == 0:
            break
        all_issues.extend(issues)
        page += 1

    issue_details = []
    for issue in all_issues[:5]:  # Limit to 5 issues to avoid hitting rate limits
        issue_details.append(
            fetch_issue_details.submit(repo, issue['number'])
        )
    
    details = []
    for issue in issue_details:
        details.append(issue.result())

    return details


@task(log_prints=True, retries=3, cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1))
def fetch_page_of_issues(repo: str, page: int = 1) -> Optional[dict]:
    """Fetch a page of issues for a GitHub repository"""
    rate_limit("github-api")
    try:
        response = httpx.get(
            f"https://api.github.com/repos/{repo}/issues",
            params={"page": page, "state": "all", "per_page": 100}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching issues for {repo}: {e}")
        return None


@task(retries=3, cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1))
def fetch_issue_details(repo: str, issue_number: int) -> dict:
    """Fetch detailed information about a specific issue"""
    rate_limit("github-api")
    response = httpx.get(f"https://api.github.com/repos/{repo}/issues/{issue_number}")
    issue_data = response.json()
    
    # Fetch comments for the issue
    comments = fetch_comments(issue_data['comments_url'])
    issue_data['comments_data'] = comments
    
    return issue_data


@task(log_prints=True, retries=3, cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1))
def fetch_comments(comments_url: str) -> List[dict]:
    """Fetch comments for an issue"""
    rate_limit("github-api")
    try:
        response = httpx.get(comments_url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching comments: {e}")
        return []


@task
def calculate_response_times(issues: List[dict]) -> float:
    """Calculate average time to first response for issues"""
    response_times = []
    
    for issue in issues:
        comments_data = issue.get('comments_data', [])
        if comments_data:  # If there are comments
            created = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
            first_comment = datetime.fromisoformat(
                comments_data[0]['created_at'].replace('Z', '+00:00')
            )
            response_time = (first_comment - created).total_seconds() / 3600
            response_times.append(response_time)

    return mean(response_times) if response_times else 0


@task
def calculate_resolution_rate(issues: List[dict]) -> float:
    """Calculate the percentage of closed issues"""
    if not issues:
        return 0
    closed = sum(1 for issue in issues if issue['state'] == 'closed')
    return (closed / len(issues)) * 100


if __name__ == "__main__":
    analyze_repo_health([
        "PrefectHQ/prefect",
        "pydantic/pydantic",
        "huggingface/transformers"
    ])
