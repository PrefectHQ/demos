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
  workspace_handle = var.staging_workspace
}

# Create production environment
module "production" {
  source          = "./modules/workspace"
  workspace_name  = "Production"
  workspace_handle = var.prod_workspace
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

variable "prod_workspace" {
  description = "Name of the production workspace"
  type        = string
  default     = "production"
}

variable "staging_workspace" {
  description = "Name of the staging workspace"
  type        = string
  default     = "staging"
}
