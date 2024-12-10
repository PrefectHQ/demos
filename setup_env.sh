#!/bin/bash

###############################################################################
# This script sets up a _paid_ Prefect Cloud account with resources:          #
#                                                                             #
# 1. Two workspaces: `production` and `staging`                               #
# 2. A default Docker work pool in each workspace                             #
# 3. A flow in each workspace                                                 #
# 4. The flow in each workspace is run multiple times                         #
# 5. The flow in `staging` has failures to demonstrate debugging              #
#
# NOTE: You must have Docker and Terraform installed                          #
###############################################################################

# Exit on any error
set -e

###############################################################################
# Check for dependencies
###############################################################################

# Check if Docker is running
echo "🐳 Checking if Docker is running..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "✅ Docker is running"

# Check if Terraform is installed
echo "🔧 Checking if Terraform is installed..."
if ! command -v terraform &> /dev/null; then
    echo "❌ Error: Terraform is not installed. Please install Terraform and try again."
    exit 1
fi

echo "✅ Terraform is installed"

# Check if Python is installed and determine the Python command
echo "🐍 Checking if Python is installed..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python is not installed. Please install Python 3.9 or higher and try again."
    exit 1
fi

# Verify Python version is 3.9 or higher
if ! $PYTHON_CMD -c "import sys; assert sys.version_info >= (3, 9), 'Python 3.9 or higher is required'" &> /dev/null; then
    echo "❌ Error: Python 3.9 or higher is required. Found $($PYTHON_CMD --version)"
    exit 1
fi

echo "✅ Python $(${PYTHON_CMD} --version) is installed"

###############################################################################
# Get auth credentials
###############################################################################

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

# Account details
ACCOUNT_DETAILS=$(curl -s "https://api.prefect.cloud/api/accounts/$ACCOUNT_ID" -H "Authorization: Bearer $API_KEY")

# Get account handle
ACCOUNT_HANDLE=$(echo $ACCOUNT_DETAILS | awk -F'"handle":"' '{print $2}' | awk -F'"' '{print $1}')

# Get plan type (fail if a personal account, since these do not support multiple workspaces)
PLAN_TYPE=$(echo $ACCOUNT_DETAILS | awk -F'"plan_type":"' '{print $2}' | awk -F'"' '{print $1}')

if [[ $PLAN_TYPE == "PERSONAL" ]]; then
    echo "❌ Error: This script requires a paid Prefect Cloud account with support for multiple workspaces."
    exit 1
fi

###############################################################################
# Set up virtual environment
###############################################################################

# Create and activate virtual environment
echo "🌟 Setting up Python virtual environment..."
$PYTHON_CMD -m venv temp_venv
source temp_venv/bin/activate

# Install requirements
echo "📦 Installing Python packages..."
pip install -r requirements.txt

echo "🔑 Reading Prefect API key and account ID..."

###############################################################################
# Provision Prefect Cloud resources
###############################################################################

echo "🏗️ Running Terraform to provision infrastructure..."
cd infra/
terraform init
terraform apply -auto-approve
cd ..

###############################################################################
# Run flows in production
###############################################################################

echo "🚀 Populate production workspace..."

# Start worker for production workspace with suppressed output
prefect cloud workspace set --workspace "$ACCOUNT_HANDLE/production"
prefect worker start --pool "default-work-pool" > /dev/null 2>&1 &
PROD_WORKER_PID=$!

# Give workers time to start
sleep 5

# Run in production workspace
python simulate_failures.py &
PROD_SIM_PID=$!

# Wait for simulations to complete
wait $PROD_SIM_PID

# Kill worker process
kill $PROD_WORKER_PID

###############################################################################
# Run flows in staging
###############################################################################

echo "🚀 Populate staging workspace..."

# Start worker for staging workspace with suppressed output
prefect cloud workspace set --workspace "$ACCOUNT_HANDLE/staging"
prefect worker start --pool "default-work-pool" > /dev/null 2>&1 &
STAGING_WORKER_PID=$!

# Give workers time to start
sleep 5

# Run in staging workspace
python simulate_failures.py --fail-at-run 3 &
STAGING_SIM_PID=$!

# Wait for simulations to complete
wait $STAGING_SIM_PID

# Kill worker process
kill $STAGING_WORKER_PID

###############################################################################
# Cleanup virtual environment
###############################################################################

deactivate
rm -rf temp_venv

echo "✅ All done!"