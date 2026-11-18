#------------------------------------------------------------------------------
# written by: Lawrence McDaniel
#             https://lawrencemcdaniel.com/
#
# date:   Dec-2025
#
# usage:  Smarter Account Manager local variables
#------------------------------------------------------------------------------

locals {
  platform_domain               = "${var.shared_resource_identifier}.${var.root_domain}"
  api_domain                    = "api.${local.platform_domain}"
  environment_platform_domain   = "${var.platform_subdomain}.${var.root_domain}"
  environment_api_domain        = "${var.api_subdomain}.${var.root_domain}"
  ecr_repository_name           = local.environment_namespace
  ecr_repository_image          = "${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${local.ecr_repository_name}:latest"

  environment                   = var.environment
  environment_namespace         = lower("${var.shared_resource_prefix}-${var.shared_resource_identifier}-${local.environment}")
  mysql_database                = substr("${var.shared_resource_prefix}_${var.shared_resource_identifier}_${local.environment}", -64, -1)
  mysql_username                = local.mysql_database

  # the shared MariaDB server: the smarter Helm chart's, the Service smarter-mariadb in the
  # Smarter platform's namespace. Account Manager has no database server of its own.
  smarter_namespace             = lower("${var.smarter_namespace_base}-${local.environment}")
  mysql_host                    = var.mysql_host != "" ? var.mysql_host : "smarter-mariadb.${local.smarter_namespace}.svc.cluster.local"

  tags = merge(
    var.tags,
    {
      "am/platform_domain"               = local.platform_domain
      "am/api_domain"                    = local.api_domain
      "am/environment"                   = local.environment
      "am/environment_platform_domain"   = local.environment_platform_domain
      "am/environment_api_domain"        = local.environment_api_domain
      "am/environment_namespace"         = local.environment_namespace
    }
  )

}
