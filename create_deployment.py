from prefect import flow

# Source for the code to deploy (here, a GitHub repo)
SOURCE_REPO="https://github.com/prefecthq/demos.git"

if __name__ == "__main__":
    flow.from_source(
        source=SOURCE_REPO,
        entrypoint="my_workflow.py:show_stars", # Specific flow to run
    ).deploy(
        name="my-first-deployment",
        parameters={
            "github_repos": [
                "PrefectHQ/prefect",
                "pydantic/pydantic",
                "huggingface/transformers"
            ]
        },
        work_pool_name="my-work-pool",
        cron="0 * * * *",  # Run every hour
    )
