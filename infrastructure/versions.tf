terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.93"
    }
    prefect = {
      source  = "prefecthq/prefect"
      version = ">= 2, <3"
    }
  }
}
