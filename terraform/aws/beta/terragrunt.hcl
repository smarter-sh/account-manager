#------------------------------------------------------------------------------
# written by: Lawrence McDaniel
#             https://www.linkedin.com/in/lawrencemcdaniel/
#
# date: Dec-2025
#
# usage: create a new smarter Account Manager environment
#------------------------------------------------------------------------------
locals {
  global_vars = read_terragrunt_config(find_in_parent_folders("global.hcl"))

  # environment vars
  environment           = "beta"
  platform_subdomain    = "${local.environment}.${local.global_vars.locals.shared_resource_identifier}"
  api_subdomain         = "${local.environment}.${local.global_vars.locals.api_subdomain}.${local.global_vars.locals.shared_resource_identifier}"
}

# Terragrunt will copy the Terraform configurations specified by the source parameter, along with any files in the
# working directory, into a temporary folder, and execute your Terraform commands in that folder.

terraform {
  source = "..//terraform"
}

# Include all settings from the root terragrunt.hcl file
include {
  path = find_in_parent_folders()
}

# These are the variables we have to pass in to use the module specified in the terragrunt configuration above
inputs = merge(
  local.global_vars.locals,
  {
    environment           = local.environment
    platform_subdomain    = local.platform_subdomain
    api_subdomain         = local.api_subdomain
  }
)
