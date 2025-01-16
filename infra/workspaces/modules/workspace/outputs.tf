output "workspace_id" {
  value       = prefect_workspace.workspace.id
  description = "ID of the created workspace"
}

output "workspace_handle" {
  value       = prefect_workspace.workspace.handle
  description = "Handle of the created workspace"
}

output "work_pool_id" {
  value       = prefect_work_pool.default.id
  description = "ID of the created work pool"
}
