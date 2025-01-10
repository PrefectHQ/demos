terraform {
  required_providers {
    prefect = {
      source = "prefecthq/prefect"
    }
  }
}

provider "prefect" {
  # Prefect will automatically use standard Prefect environment variables:
  # PREFECT_API_KEY=pnu_1234567890
  # PREFECT_API_URL=https://api.prefect.cloud/api/accounts/<ACCOUNT_ID>/workspaces/<WORKSPACE_ID>
}

provider "aws" {
  # AWS provider will automatically use standard AWS environment variables:
  # AWS_ACCESS_KEY_ID=AKIA1234567890
  # AWS_SECRET_ACCESS_KEY=1234567890/1234/12345
  # AWS_REGION=us-east-1
}

# Data bucket
module "s3_data_bucket_to_prefect" {
  source      = "prefecthq/bucket-sensor/prefect"
  bucket_type = "s3"

  # Eventbridge S3 Event types:
  # https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventBridge.html
  bucket_event_notification_types = ["Object Created"]

  bucket_name = "prefect-ml-data"
  topic_name  = "prefect-ml-data-event-topic"

  webhook_name = "model-training"
  # Prefect Webhook templates:
  # https://docs.prefect.io/v3/automate/events/webhook-triggers#webhook-templates
  #
  # S3 Eventbridge Event Structure:
  # https://docs.aws.amazon.com/AmazonS3/latest/userguide/ev-events.html
  webhook_template = {
    event = "S3 {{ body.detail.reason }}",
    resource = {
      "prefect.resource.id" = "s3.bucket.{{ body.detail.bucket.name }}",
      "object-key"          = "{{ body.detail.object.key }}",
    }
  }
}

# Model bucket
module "s3_model_bucket_to_prefect" {
  source      = "prefecthq/bucket-sensor/prefect"
  bucket_type = "s3"

  # Eventbridge S3 Event types:
  # https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventBridge.html
  bucket_event_notification_types = ["Object Created"]

  bucket_name = "prefect-model"
  topic_name  = "prefect-model-event-topic"

  webhook_name = "model-inference"
  # Prefect Webhook templates:
  # https://docs.prefect.io/v3/automate/events/webhook-triggers#webhook-templates
  #
  # S3 Eventbridge Event Structure:
  # https://docs.aws.amazon.com/AmazonS3/latest/userguide/ev-events.html
  webhook_template = {
    event = "S3 {{ body.detail.reason }}",
    resource = {
      "prefect.resource.id" = "s3.bucket.{{ body.detail.bucket.name }}",
      "object-key"          = "{{ body.detail.object.key }}",
    }
  }
}