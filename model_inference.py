from prefect import flow, task
from prefect_aws import S3Bucket
from prefect.runner.storage import GitRepository
import xgboost as xgb
import numpy as np

from io import BytesIO

# Load the saved model:
@task
def load_model(filename):
    """Load a saved XGBoost model from S3"""

    # Get the S3 bucket block
    s3_bucket = S3Bucket.load("s3-bucket-block")
    
    # Download the model file to a BytesIO object
    model_bytes = BytesIO()
    s3_bucket.download_object_to_file_object(
        filename,
        model_bytes
    )
    
    # Reset the buffer position to the start
    model_bytes.seek(0)
    loaded_model = xgb.Booster()
    loaded_model.load_model(filename)
    return loaded_model

# Run inference with loaded model:
@task
def predict(model, X):
    """Make predictions using the loaded model
    Args:
        model: Loaded XGBoost model
        X: Features array/matrix in the same format used during training
    """
    # Convert input to DMatrix (optional but recommended)
    dtest = xgb.DMatrix(np.array(X))
    # Get predictions
    predictions = model.predict(dtest)
    return predictions

@flow(log_prints=True)
def run_inference(samples: list = [[5.0,3.4,1.5,0.2], [6.4,3.2,4.5,1.5], [7.2,3.6,6.1,2.5]]):
    model = load_model('xgboost-model')
    predictions = predict(model, samples)
    for sample, prediction in zip(samples, predictions):
        print(f"Prediction for sample {sample}: {prediction}")

if __name__ == "__main__":
    flow.from_source(
        source=GitRepository(
            url="https://github.com/daniel-prefect/demos",
            branch="train_model_from_s3_data"
        ),
        entrypoint="model_inference.py:run_inference",
    ).deploy(
        name="model-inference",
        work_pool_name="my-managed-pool",
    )
