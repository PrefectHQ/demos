from prefect import flow, task
from prefect_aws import AwsCredentials
from prefect.cache_policies import NONE
from prefect.blocks.system import Secret
import sagemaker
from sagemaker.xgboost.estimator import XGBoost
import boto3

@task(log_prints=True)
def get_sagemaker_session(aws_credentials):
    """Create a SageMaker session using AWS credentials."""
    boto_session = boto3.Session(
        aws_access_key_id=aws_credentials.aws_access_key_id,
        aws_secret_access_key=aws_credentials.aws_secret_access_key.get_secret_value(),
        region_name=aws_credentials.region_name
    )
    return sagemaker.Session(boto_session=boto_session)

@task
def get_training_inputs(data_bucket):
    """Get the S3 paths for training and test data."""
    
    return {
        "train": f"s3://{data_bucket}/train.csv",
        "validation": f"s3://{data_bucket}/test.csv"
    }

@task
def create_training_script(model_bucket):
    """Create the training script dynamically from template"""
    # Read the template
    with open("templates/sagemaker_script_template.py", "r") as f:
        training_script = f.read()

    # Format the script with the model bucket
    training_script = training_script.format(model_bucket=model_bucket)

    # Write the formatted script
    with open("train.py", "w") as f:
        f.write(training_script)

@task(cache_policy=NONE)
def create_xgboost_estimator(sagemaker_session, role_arn):
    """Create and configure the XGBoost estimator."""
    hyperparameters = {
        "max_depth": 5,
        "eta": 0.2,
        "gamma": 4,
        "min_child_weight": 6,
        "subsample": 0.8,
        "objective": "multi:softmax",
        "num_class": 3,
        "num_round": 100,
        "tree_method": "gpu_hist",
        "device": "cuda"
    }

    return XGBoost(
        entry_point="train.py",
        hyperparameters=hyperparameters,
        role=role_arn,
        instance_count=1,
        instance_type="ml.g4dn.xlarge",
        framework_version="1.7-1",
        py_version="py3",
        sagemaker_session=sagemaker_session
    )

@flow(log_prints=True)
def train_model(data_bucket: str = "prefect-ml-data", model_bucket: str = "prefect-model"):
    """Main flow to train XGBoost model on Iris dataset using SageMaker."""
    # Load AWS credentials from Prefect Block
    aws_credentials = AwsCredentials.load("aws-credentials")
    
    # Get SageMaker role ARN from Prefect Secret Block
    role_arn = Secret.load("sagemaker-role-arn").get()
    
    # Create SageMaker session
    sagemaker_session = get_sagemaker_session(aws_credentials)

    # Get training inputs
    training_inputs = get_training_inputs(data_bucket)
    create_training_script(model_bucket)
    
    # Create and train estimator
    estimator = create_xgboost_estimator(sagemaker_session, role_arn)

    estimator.fit(training_inputs, wait=True)
    
    return estimator

if __name__ == "__main__":
    flow.from_source(
        source="https://github.com/PrefectHQ/demos.git",
        entrypoint="model_training.py:train_model"
    ).deploy(
        name="model-training",
        work_pool_name="my-process-pool"
    )
