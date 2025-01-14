from prefect import flow

if __name__ == "__main__":
    flow.from_source(
        source="https://github.com/prefecthq/demos.git",
        entrypoint="my_workflow.py:show_stars",
        parameters={"github_repos": [
            "PrefectHQ/prefect",
            "pydantic/pydantic",
            "huggingface/transformers"
        ]},
    ).deploy(
        name="my-first-deployment",
        work_pool_name="my-work-pool",
        cron="0 1 * * *",
    )
