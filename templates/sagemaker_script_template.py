import argparse
import boto3
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

    hyperparameters = {{
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
    }}

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
    filename = "xgboost-model"
    model_location = os.path.join(args.model_dir, filename)
    model.save_model(model_location)

    # Save the model parameters
    hyperparameters_location = os.path.join(args.model_dir, "hyperparameters.json")
    with open(hyperparameters_location, "w") as f:
        json.dump(hyperparameters, f)

    # Upload the model to an S3 bucket for inference using boto3
    s3_client = boto3.client('s3')
    bucket_name = "{model_bucket}"
    s3_client.upload_file(
        model_location,
        bucket_name,
        filename
    )