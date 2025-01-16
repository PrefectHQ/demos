terraform {
  required_providers {
    prefect = {
      source = "PrefectHQ/prefect"
    }
  }
}

provider "prefect" {
  api_key     = var.prefect_api_key
  account_id  = var.prefect_account_id
}

# Create staging environment
module "staging" {
  source          = "./modules/workspace"
  workspace_name  = "Staging"
  workspace_handle = "staging"
}

# Create production environment
module "production" {
  source          = "./modules/workspace"
  workspace_name  = "Production"
  workspace_handle = "production"
}

variable "prefect_api_key" {
  description = "Prefect Cloud API key"
  type        = string
  sensitive   = true
}

variable "prefect_account_id" {
  description = "Prefect Cloud Account ID"
  type        = string
}