# S2: wire the SageMaker notebook instance into the root module.
# It lives in the same VPC as the platform host so it can reach MLflow on port 5000.

module "notebook" {
  source    = "../modules/notebook"
  subnet_id = data.aws_subnets.primary.ids[0]
  repo_url  = "https://github.com/${var.github_repo}.git"

  env = {
    MLFLOW_TRACKING_URI = "http://${module.platform.private_ip}:5000"
    REDSHIFT_CLUSTER_ID = "lab"
    REDSHIFT_DATABASE   = "lab"
    LAB_DATA_BUCKET     = var.lab_data_bucket
    LAB_ARTIFACT_BUCKET = module.artifact_bucket.name
    AWS_DEFAULT_REGION  = "us-east-1"
  }
}

output "notebook_name" {
  value       = module.notebook.name
  description = "SageMaker notebook instance name"
}
