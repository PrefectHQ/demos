#!/bin/bash

###############################################################################
# This script sets up a Prefect Cloud account with the following environment  #
#                                                                             #
# 1. Two workspaces: `production` and `staging`                               #
# 2. A default Docker work pool in each workspace                             #
# 3. A flow in each workspace                                                 #
# 4. The flow in each workspace is run multiple times                         #
# 5. The flow in `staging` has failures to demonstrate debugging              #
#                                                                             #
# NOTE: You must have Docker running on your machine to run this script!!!    #
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

# Get account handle from the active workspace
ACCOUNT_HANDLE=$(prefect cloud workspace ls | awk '/^│ \*/ {print $3}' | cut -d'/' -f1)

echo "🏗️ Running Terraform to provision infrastructure..."
terraform destroy -auto-approve