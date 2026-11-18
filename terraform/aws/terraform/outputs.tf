#------------------------------------------------------------------------------
# written by: Lawrence McDaniel
#             https://lawrencemcdaniel.com/
#
# date:   Dec-2025
#
# usage:  Smarter Account Manager outputs
#------------------------------------------------------------------------------

output "root_domain" {
  value = var.root_domain
}
output "platform_domain" {
  value = local.platform_domain
}
output "api_domain" {
  value = local.api_domain
}
output "environment_api_domain" {
  value = local.environment_api_domain
}
output "environment_platform_domain" {
  value = local.environment_platform_domain
}


output "mysql_host" {
  value = local.mysql_host
}

output "mysql_port" {
  value = var.mysql_port
}
