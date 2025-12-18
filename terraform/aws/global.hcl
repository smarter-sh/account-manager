#------------------------------------------------------------------------------
# written by: Lawrence McDaniel
#             https://lawrencemcdaniel.com/
#
# date: Dec-2025
#
# usage: create global parameters, exposed to all
#        Terragrunt modules in this repository.
#------------------------------------------------------------------------------
locals {

    ###############################################################################
    # AWS CLI parameters
    ###############################################################################
    aws_account_id             = get_env("AWS_ACCOUNT_ID", "090511222473")
    aws_profile                = get_env("AWS_PROFILE", "default")
    aws_region                 = get_env("AWS_REGION", "us-east-2")
    root_domain                = get_env("ROOT_DOMAIN", "smarter.sh")
    mysql_root_username        = get_env("MYSQL_ROOT_USERNAME", "root")
    mysql_root_password        = get_env("MYSQL_ROOT_PASSWORD", "SET-ME-PLEASE")

    shared_resource_prefix     = get_env("SHARED_RESOURCE_PREFIX", "smarter")
    shared_resource_identifier = get_env("SHARED_RESOURCE_IDENTIFIER", "am")
    api_subdomain              = get_env("API_SUBDOMAIN", "api")
    eks_cluster_name           = get_env("EKS_CLUSTER_NAME", "apps-hosting-service")
    mysql_host                 = get_env("MYSQL_HOST", "mysql.service.lawrencemcdaniel.com")
    mysql_port                 = get_env("MYSQL_PORT", "3306")
    tags = {
      "terraform"                 = "true",
      "project"                   = "Smarter Account Manager"
      "contact"                   = "Lawrence McDaniel - https://lawrencemcdaniel.com/"
      "am/root_domain"            = local.root_domain
      "am/eks_cluster_name"       = local.eks_cluster_name
      "am/mysql_host"             = local.mysql_host
    }

}

inputs = {
    aws_account_id             = local.aws_account_id
    aws_profile                = local.aws_profile
    aws_region                 = local.aws_region
    root_domain                = local.root_domain
    shared_resource_identifier = local.shared_resource_identifier
    api_subdomain              = local.api_subdomain
    eks_cluster_name           = local.eks_cluster_name
    mysql_root_username        = local.mysql_root_username
    mysql_root_password        = local.mysql_root_password
    mysql_host                 = local.mysql_host
    mysql_port                 = local.mysql_port
    tags                       = local.tags
}
