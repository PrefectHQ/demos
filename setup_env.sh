#!/bin/bash

###############################################################################
# This script sets up a _paid_ Prefect Cloud account with resources:          #
#                                                                             #
# 1. Two workspaces: `production` and `staging` (customizable via env vars)   #
# 2. A Docker work pool in each workspace                                     #
# 3. A flow in each workspace                                                 #
# 4. The flow in each workspace is run multiple times                         #
# 5. The flow in `staging` has failures to demonstrate debugging              #
#                                                                             #
# NOTE: You must have Docker and Terraform installed                          #
###############################################################################

# Exit on any error
set -e

cleanup() {

    # Kill any remaining worker processes
    if [ ! -z "$PROD_WORKER_PID" ]; then
        kill $PROD_WORKER_PID 2>/dev/null || true
    fi
    if [ ! -z "$STAGING_WORKER_PID" ]; then
        kill $STAGING_WORKER_PID 2>/dev/null || true
    fi

    # Deactivate and remove virtual environment
    if [ -d "temp_venv" ]; then
        deactivate 2>/dev/null || true
        rm -rf temp_venv
    fi

    echo "🧹 Cleanup completed"

}

# Set up trap to call cleanup function on script exit (success or failure)
trap cleanup EXIT

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

# Check if jq is installed
echo "🔧 Checking if jq is installed..."
if ! command -v jq &> /dev/null; then
    echo "❌ Error: jq is not installed. Please install jq and try again."
    exit 1
fi

echo "✅ jq is installed"

###############################################################################
# Establish account and workspace details
###############################################################################

echo "🔑 Fetching Prefect account details..."

# Must have set TF_VAR_prefect_api_key and TF_VAR_prefect_account_id environment variables
if [ -z "$TF_VAR_prefect_api_key" ]; then
    echo "❌ Error: TF_VAR_prefect_api_key environment variable is not set"
    exit 1
fi

if [ -z "$TF_VAR_prefect_account_id" ]; then
    echo "❌ Error: TF_VAR_prefect_account_id environment variable is not set"
    exit 1
fi

# Set default workspace names if not provided via environment variables
PROD_WORKSPACE=${TF_VAR_prod_workspace:-"production"}
STAGING_WORKSPACE=${TF_VAR_staging_workspace:-"staging"}

# Export for Terraform to use
export TF_VAR_prod_workspace=$PROD_WORKSPACE
export TF_VAR_staging_workspace=$STAGING_WORKSPACE

# Account details
ACCOUNT_DETAILS=$(curl -s "https://api.prefect.cloud/api/accounts/$TF_VAR_prefect_account_id" \
    -H "Authorization: Bearer $TF_VAR_prefect_api_key")

# Get account handle and plan type using jq
ACCOUNT_HANDLE=$(echo "$ACCOUNT_DETAILS" | jq -r '.handle')
PLAN_TYPE=$(echo "$ACCOUNT_DETAILS" | jq -r '.plan_type')

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
pip install -r ./requirements.txt

###############################################################################
# Provision Prefect Cloud resources
###############################################################################

echo "🏗️ Running Terraform to provision infrastructure..."
terraform -chdir=infra/workspaces init
terraform -chdir=infra/workspaces apply -auto-approve

###############################################################################
# Run flows in production
###############################################################################

echo "🚀 Populate $PROD_WORKSPACE workspace..."

# Start worker for production workspace with suppressed output
prefect cloud workspace set --workspace "$ACCOUNT_HANDLE/$PROD_WORKSPACE"
prefect worker start --pool "my-work-pool" > /dev/null 2>&1 &
PROD_WORKER_PID=$!

# Give workers time to start
sleep 5

# Run in production workspace
python ./simulate_failures.py &
PROD_SIM_PID=$!

# Wait for simulations to complete
wait $PROD_SIM_PID

# Kill worker process
kill $PROD_WORKER_PID

###############################################################################
# Run flows in staging
###############################################################################

echo "🚀 Populate $STAGING_WORKSPACE workspace..."

# Start worker for staging workspace with suppressed output
prefect cloud workspace set --workspace "$ACCOUNT_HANDLE/$STAGING_WORKSPACE"
prefect worker start --pool "my-work-pool" > /dev/null 2>&1 &
STAGING_WORKER_PID=$!

# Give workers time to start
sleep 5

# Run in staging workspace
python ./simulate_failures.py --fail-at-run 3 &
STAGING_SIM_PID=$!

# Wait for simulations to complete
wait $STAGING_SIM_PID

# Kill worker process
kill $STAGING_WORKER_PID

echo "✅ All done!"
