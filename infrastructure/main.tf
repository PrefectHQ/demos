module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "prefect-demo-vpc"
  cidr = "10.0.0.0/16"

  azs            = ["us-east-1a", "us-east-1b", "us-east-1c"]
  public_subnets = ["10.1.0.0/16", "10.2.0.0/16", "10.3.0.0/16"]
}

module "ecs" {
  source = "terraform-aws-modules/ecs/aws"

  region = "us-east-1"

  cluster_name = "prefect-demo-push-pool"

  create_task_exec_iam_role = true

  default_capacity_provider_strategy = {
    FARGATE_SPOT = {
      weight = 100
    }
  }
}

# ECS Push Work Pool Policy
module "iam_policy" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-policy"
  version = "5.59.0"

  name = "prefect-ecs-push-worker-policy"

  policy = <<-EOF
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PrefectEcsPolicy",
                "Effect": "Allow",
                "Action": [
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:CreateSecurityGroup",
                    "ec2:CreateTags",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeVpcs",
                    "ecs:CreateCluster",
                    "ecs:DeregisterTaskDefinition",
                    "ecs:DescribeClusters",
                    "ecs:DescribeTaskDefinition",
                    "ecs:DescribeTasks",
                    "ecs:ListAccountSettings",
                    "ecs:ListClusters",
                    "ecs:ListTaskDefinitions",
                    "ecs:RegisterTaskDefinition",
                    "ecs:RunTask",
                    "ecs:StopTask",
                    "ecs:TagResource",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:GetLogEvents",
                ],
                "Resource": "*",
            }
        ],
    }
  EOF
}

module "iam_account" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-user"
  version = "5.59.0"

  name                  = "prefect-demo-ecs-push"
  create_iam_access_key = true
  policy_arns           = [module.iam_policy.arn]
}

module "ecs_task_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-assumable-role"

  trusted_role_services = [
    "ecs-tasks.amazonaws.com"
  ]

  create_role = true
  role_name   = "prefect-push-ecs-task-role"

  custom_role_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonS3FullAccess"
  ]
  number_of_custom_role_policy_arns = 3
}

resource "prefect_block" "ecs_push_pool" {
  name = "ecs-push-pool"

  type_slug = "aws-credentials"

  data_wo = jsonencode({
    aws_access_key_id     = module.iam_account.iam_access_key_id
    aws_secret_access_key = module.iam_account.iam_access_key_secret
    region_name           = "us-east-1"
  })
}

resource "prefect_work_pool" "ecs_push_pool" {
  name = "ecs-push"
  type = "ecs:push"

  # prefect work-pool get-default-base-job-template --type ecs:push
  base_job_template = jsonencode({
    variables = {
      launch_type = "FARGATE" # this will be spot by default

      aws_credentials = {
        block_type_slug = "aws-credentials"
        block_name      = prefect_block.ecs_push_pool.name
      }

      cluster = module.ecs.cluster_name

      vpc_id = module.vpc.vpc_id # required for FARGATE launch type

      network_configuration = {
        "Subnets" = module.vpc.public_subnets
      }

      configure_cloudwatch_logs = true

      execution_role_arn = module.ecs.task_exec_iam_role_arn # while starting
      task_role_arn      = module.ecs_task_role.iam_role_arn # while running
    }
  })
}