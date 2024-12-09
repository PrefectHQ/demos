terraform {
  required_providers {
    prefect = {
      source = "PrefectHQ/prefect"
    }
  }
}

provider "prefect" {
  api_key = var.prefect_api_key
  account_id = var.prefect_account_id
}

# Create staging workspace
resource "prefect_workspace" "staging" {
  name        = "Staging"
  handle      = "staging"
}

# Create production workspace
resource "prefect_workspace" "production" {
  name        = "Production"
  handle      = "production"
}

# Create default work pool in staging workspace
resource "prefect_work_pool" "staging_default" {
  name        = "default-work-pool"
  workspace_id = prefect_workspace.staging.id
  type        = "docker"
}

# Create default work pool in production workspace
resource "prefect_work_pool" "production_default" {
  name        = "default-work-pool"
  workspace_id = prefect_workspace.production.id
  type        = "docker"
}
