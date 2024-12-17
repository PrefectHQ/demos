from prefect import flow, task
import argparse
import asyncio
from prefect.client.orchestration import get_client

@task
def process_data(run: int, fail_at_run: int | None = None) -> bool:
    """Simulate data processing with failures"""
    if fail_at_run and run >= fail_at_run:
        raise Exception(f"Run failed")
    
    return True

@flow(name="data-pipeline")
def data_pipeline(run: int, fail_at_run: int | None = None):
    """Main flow for data processing"""
    process_data(run, fail_at_run)

async def create_runs(deployment_id: str, num_runs: int, fail_at_run: int | None):
    """Async function to create and space out the flow runs"""
    client = get_client()
    
    # Calculate time intervals to spread 20 runs over 1 minute
    total_duration = 60  # 1 minute in seconds
    interval = total_duration / 20  # Time between each run
    
    for run in range(1,num_runs+1):
        try:
            # Create and execute the run
            await client.create_flow_run_from_deployment(
                deployment_id=deployment_id,
                parameters={"run": run, "fail_at_run": fail_at_run}
            )
            print(f"Started run {run}")
        except Exception as e:
            print(f"Error starting run {run}: {str(e)}")
        
        # Sleep for the interval
        await asyncio.sleep(interval)

if __name__ == "__main__":
    # Argument parsing
    parser = argparse.ArgumentParser(description='Run data pipeline simulation')
    parser.add_argument('--name', type=str, default='pipeline-deployment', help='Deployment name (default: pipeline-deployment)')
    parser.add_argument('--runs', type=int, default=10, help='Number of flow runs to generate (default: 10)')
    parser.add_argument('--fail-at-run', type=int, help='Run number at which to start failing')
    parser.add_argument('--tags', type=str, default='team-a,red', help='Comma-separated list of tags (default: team-a,red)')
    args = parser.parse_args()
    
    # Deploy the flow
    deployment_id = data_pipeline.deploy(
        name=args.name,
        work_pool_name="default-work-pool",
        image="prefecthq/prefect:3-latest",
        push=False,
        tags=args.tags.split(',')
    )

    # Trigger flow runs
    asyncio.run(create_runs(deployment_id=deployment_id, num_runs=args.runs, fail_at_run=args.fail_at_run))
