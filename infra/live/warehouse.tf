# S1: wire the Redshift cluster (infra/modules/redshift) into this root module, and expose the
# outputs that contracts/platform.yaml lists under terraform_outputs.

module "redshift" {
  source     = "../modules/redshift"
  subnet_ids = data.aws_subnets.default.ids
}

output "redshift_cluster_id" {
  value       = module.redshift.cluster_id
  description = "Cluster identifier of the Redshift warehouse"
}

output "redshift_database" {
  value       = module.redshift.database
  description = "Database name of the Redshift warehouse"
}
