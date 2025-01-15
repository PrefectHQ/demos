from prefect import flow, task
from prefect_aws import S3Bucket
import xgboost as xgb
import numpy as np
import tempfile
import os
from typing import Union

# Load the saved model:
@task
def load_model(filename: str) -> xgb.Booster:
    """Load a saved XGBoost model from S3"""

    # Get the S3 bucket block
    s3_bucket = S3Bucket.load("s3-bucket-block")

    # Create a temporary file to store the model
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name
        
        # Download the model file
        s3_bucket.download_object_to_path(
            from_path=filename,
            to_path=temp_path
        )
        
        # Load the XGBoost model
        model = xgb.Booster()
        model.load_model(temp_path)
    
    # Clean up the temporary file
    os.unlink(temp_path)

    return model

# Run inference with loaded model:
@task
def predict(model: xgb.Booster, X: Union[list[list[float]], np.ndarray]) -> np.ndarray:
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
def run_inference(samples: Union[list[list[float]], None] = None) -> None:
    samples = samples or [[5.0,3.4,1.5,0.2], [6.4,3.2,4.5,1.5], [7.2,3.6,6.1,2.5]]
    model = load_model('xgboost-model')
    predictions = predict(model, samples)
    for sample, prediction in zip(samples, predictions):
        print(f"Prediction for sample {sample}: {prediction}")

if __name__ == "__main__":
    flow.from_source(
        source="https://github.com/PrefectHQ/demos.git",
        entrypoint="model_inference.py:run_inference",
    ).deploy(
        name="model-inference",
        work_pool_name="my-work-pool",
    )
