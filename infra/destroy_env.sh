#!/bin/bash

###############################################################################
# This script destroys any Prefect Cloud resources created by `setup_env.sh`  #
###############################################################################

# Exit on any error
set -e

echo "🔑 Reading Prefect API key and account ID..."

# Get active profile from `profiles.toml`
ACTIVE_PROFILE=$(awk -F ' = ' '/^active/ {gsub(/"/, "", $2); print $2}' ~/.prefect/profiles.toml)

# Get API key for the active profile from `profiles.toml`
API_KEY=$(awk -v profile="profiles.$ACTIVE_PROFILE" '
  $0 ~ "\\[" profile "\\]" {in_section=1; next}
  in_section && /^\[/ {in_section=0}
  in_section && /PREFECT_API_KEY/ {
    gsub(/"/, "", $3)
    print $3
    exit
  }
' ~/.prefect/profiles.toml)
export TF_VAR_prefect_api_key=$API_KEY

# Extract account ID from `prefect config view`
ACCOUNT_ID=$(prefect config view | awk -F'/' '/^https:\/\/app.prefect.cloud\/account\// {print $5}')
export TF_VAR_prefect_account_id=$ACCOUNT_ID

echo "🏗️ Running Terraform to provision infrastructure..."
terraform destroy -auto-approve
