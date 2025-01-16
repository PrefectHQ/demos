terraform {
  required_providers {
    prefect = {
      source = "PrefectHQ/prefect"
    }
  }
}

# Module for creating a Prefect workspace and its default work pool
resource "prefect_workspace" "workspace" {
  name   = var.workspace_name
  handle = var.workspace_handle
}

resource "prefect_work_pool" "default" {
  name         = var.work_pool_name
  workspace_id = prefect_workspace.workspace.id
  type         = var.work_pool_type
}

variable "workspace_name" {
  type        = string
  description = "Name of the Prefect workspace"
}

variable "workspace_handle" {
  type        = string
  description = "Handle (slug) for the Prefect workspace"
}

variable "work_pool_name" {
  type        = string
  description = "Name of the default work pool"
  default     = "my-work-pool"
}

variable "work_pool_type" {
  type        = string
  description = "Type of the work pool"
  default     = "docker"
}
