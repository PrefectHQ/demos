terraform {
  required_providers {
    prefect = {
      source = "prefecthq/prefect"
    }
    aws = {
      source  = "hashicorp/aws"
    }
  }
}

provider "prefect" {
  # Provider will automatically use standard Prefect environment variables:
  # PREFECT_API_KEY=pnu_1234567890
  # PREFECT_API_URL=https://api.prefect.cloud
  # PREFECT_CLOUD_ACCOUNT_ID=9b649228-0419-40e1-9e0d-44954b5c0ab6
  workspace_id = var.prefect_workspace_id
}

provider "aws" {
  # Provider will automatically use standard AWS environment variables:
  # AWS_ACCESS_KEY_ID=AKIA1234567890
  # AWS_SECRET_ACCESS_KEY=1234567890/1234/12345
  # AWS_REGION=us-east-1
}

# IAM Role for Prefect
resource "aws_iam_role" "prefect_tutorial" {
  name = "prefect-tutorial"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
      }
    ]
  })
}

# Attach SageMaker Full Access policy
resource "aws_iam_role_policy_attachment" "sagemaker_full_access" {
  role       = aws_iam_role.prefect_tutorial.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# Attach S3 Full Access policy
resource "aws_iam_role_policy_attachment" "s3_full_access" {
  role       = aws_iam_role.prefect_tutorial.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# Data bucket
module "s3_data_bucket_to_prefect" {
  source      = "prefecthq/bucket-sensor/prefect//modules/s3"

  bucket_event_notification_types = ["Object Created"]

  bucket_name = var.data_bucket_name
  topic_name  = "prefect-ml-data-event-topic"

  webhook_name = "model-training"
  webhook_template = {
    event = "webhook.called",
    resource = {
      "prefect.resource.id" = "s3.bucket.{{ body.detail.bucket.name }}",
      "object-key"          = "{{ body.detail.object.key }}",
    }
  }
}

# Model bucket
module "s3_model_bucket_to_prefect" {
  source      = "prefecthq/bucket-sensor/prefect//modules/s3"

  bucket_event_notification_types = ["Object Created"]

  bucket_name = var.model_bucket_name
  topic_name  = "prefect-model-event-topic"

  webhook_name = "model-inference"
  webhook_template = {
    event = "webhook.called",
    resource = {
      "prefect.resource.id" = "s3.bucket.{{ body.detail.bucket.name }}",
      "object-key"          = "{{ body.detail.object.key }}",
    }
  }
}

# Automation for model training
resource "prefect_automation" "train_model" {
  name        = "train-model"
  enabled     = true

  trigger = {
    event = {
      posture = "Reactive"
      match_related = jsonencode({
        "prefect.resource.id" : ["prefect-cloud.webhook.${ module.s3_data_bucket_to_prefect.webhook.id }"]
      })
      expect    = ["webhook.called"]
      threshold = 1
      within    = 60
    }
  }
  actions = [
    {
      type   = "run-deployment"
      source = "selected"
      deployment_id = var.model_training_deployment_id
    }
  ]
}

# Automation for model inference
resource "prefect_automation" "run_inference" {
  name        = "run-inference"
  enabled     = true

  trigger = {
    event = {
      posture = "Reactive"
      match_related = jsonencode({
        "prefect.resource.id" : ["prefect-cloud.webhook.${ module.s3_model_bucket_to_prefect.webhook.id }"]
      })
      expect    = ["webhook.called"]
      threshold = 1
      within    = 60
    }
  }
  actions = [
    {
      type   = "run-deployment"
      source = "selected"
      deployment_id = var.model_inference_deployment_id
    }
  ]
}

# Variables
variable "prefect_workspace_id" {
  type        = string
  description = "Prefect workspace ID"
}

variable "data_bucket_name" {
  type        = string
  description = "Name of the S3 bucket for ML data"
}

variable "model_bucket_name" {
  type        = string
  description = "Name of the S3 bucket for models"
}

variable "model_training_deployment_id" {
  type        = string
  description = "ID of the deployment for model training"
}

variable "model_inference_deployment_id" {
  type        = string
  description = "ID of the deployment for model inference"
}
