from prefect import flow, task
from prefect_aws import AwsCredentials
from prefect.blocks.system import Secret
import sagemaker
from sagemaker.xgboost.estimator import XGBoost
import pandas as pd
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
def get_training_inputs():
    """Get the S3 paths for training and test data."""
    bucket = "prefect-tutorial"
    
    return {
        "train": f"s3://{bucket}/train.csv",
        "validation": f"s3://{bucket}/test.csv"
    }

@task
def create_training_script():
    """Create the training script dynamically"""
    training_script = """import argparse
import os
import json
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # Hyperparameters are described here.
    parser.add_argument(
        "--max_depth",
        type=int,
    )
    parser.add_argument("--eta", type=float)
    parser.add_argument("--gamma", type=float)
    parser.add_argument("--min_child_weight", type=float)
    parser.add_argument("--subsample", type=float)
    parser.add_argument("--verbosity", type=int)
    parser.add_argument("--objective", type=str)
    parser.add_argument("--num_round", type=int)
    parser.add_argument("--tree_method", type=str, default="auto")
    parser.add_argument("--predictor", type=str, default="auto")
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--num_class", type=int)

    # Sagemaker specific arguments. Defaults are set in the environment variables.
    parser.add_argument("--output-data-dir", type=str, default=os.environ["SM_OUTPUT_DATA_DIR"])
    parser.add_argument("--model-dir", type=str, default=os.environ["SM_MODEL_DIR"])
    parser.add_argument("--train", type=str, default=os.environ["SM_CHANNEL_TRAIN"])
    parser.add_argument("--validation", type=str, default=os.environ["SM_CHANNEL_VALIDATION"])
    parser.add_argument("--num-round", type=int, default=100)

    args, _ = parser.parse_known_args()

    # Load training and validation data with appropriate column names
    column_names = ['sepal_length', 'sepal_width', 'petal_length', 'petal_width', 'target']
    train_data = pd.read_csv(os.path.join(args.train, "train.csv"), 
                            names=column_names, 
                            header=None)
    validation_data = pd.read_csv(os.path.join(args.validation, "test.csv"), 
                                names=column_names, 
                                header=None)

    # For XGBoost, we need to convert the text labels to numeric values
    # Create a label encoder
    label_encoder = LabelEncoder()
    y_train = label_encoder.fit_transform(train_data['target'])
    y_validation = label_encoder.transform(validation_data['target'])

    # Get features (all columns except target)
    X_train = train_data.drop('target', axis=1)
    X_validation = validation_data.drop('target', axis=1)

    # Create DMatrix for XGBoost
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dvalidation = xgb.DMatrix(X_validation, label=y_validation)

    hyperparameters = {
        "max_depth": args.max_depth,
        "eta": args.eta,
        "gamma": args.gamma,
        "min_child_weight": args.min_child_weight,
        "subsample": args.subsample,
        "verbosity": args.verbosity,
        "objective": args.objective,
        "tree_method": args.tree_method,
        "predictor": args.predictor,
        "device": args.device,
        "num_class": args.num_class
    }

    # Train the model
    watchlist = [(dtrain, "train"), (dvalidation, "validation")]
    model = xgb.train(
        hyperparameters,
        dtrain,
        num_boost_round=args.num_round,
        evals=watchlist,
        early_stopping_rounds=10
    )

    # Save the model
    model_location = os.path.join(args.model_dir, "xgboost-model")
    model.save_model(model_location)

    # Save the model parameters
    hyperparameters_location = os.path.join(args.model_dir, "hyperparameters.json")
    with open(hyperparameters_location, "w") as f:
        json.dump(hyperparameters, f)
"""
    
    with open("train.py", "w") as f:
        f.write(training_script)

@task(cache_policy=None)
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
def train_iris_model():
    """Main flow to train XGBoost model on Iris dataset using SageMaker."""
    # Load AWS credentials from Prefect Block
    aws_credentials = AwsCredentials.load("aws-credentials")
    
    # Get SageMaker role ARN from Prefect Secret Block
    role_arn = Secret.load("sagemaker-role-arn").get()
    
    # Create SageMaker session
    sagemaker_session = get_sagemaker_session(aws_credentials)
    
    # Get training inputs
    training_inputs = get_training_inputs()
    create_training_script()
    
    # Create and train estimator
    estimator = create_xgboost_estimator(sagemaker_session, role_arn)

    print(estimator)
    estimator.fit(training_inputs, wait=True)
    
    return estimator

if __name__ == "__main__":
    train_iris_model()
