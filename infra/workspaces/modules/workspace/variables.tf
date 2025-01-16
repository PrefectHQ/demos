variable "workspace_name" {
  description = "Name of the workspace to create"
  type        = string
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
