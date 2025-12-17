#------------------------------------------------------------------------------
# written by: Lawrence McDaniel
#             https://lawrencemcdaniel.com/
#
# date:       Dec-2025
#
# usage:      Terraform variable declarations for Smarter Account Manager
#------------------------------------------------------------------------------
variable shared_resource_prefix {
  description = "A common prefix for resources created for this demo"
  type        = string
  default     = "smarter"
}

variable "shared_resource_identifier" {
  description = "A common identifier/prefix for resources created for this demo"
  type        = string
  default     = "am"
}

variable "aws_account_id" {
  description = "12-digit AWS account number"
  type        = string
}
variable "aws_region" {
  description = "A valid AWS data center region code"
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "A map of tags to add to all resources. Tags added to launch configuration or templates override these values."
  type        = map(string)
  default     = {}
}

variable "root_domain" {
  description = "a valid Internet domain name which you directly control using AWS Route53 in this account"
  type        = string
  default     = "smarter.sh"
}

variable "platform_subdomain" {
  description = "a valid Internet domain name which you directly control using AWS Route53 in this account"
  type        = string
  default     = "am"
}

variable "api_subdomain" {
  description = "a valid Internet domain name which you directly control using AWS Route53 in this account"
  type        = string
  default     = "api"
}

variable "environment" {
  description = "the environment name (e.g. local, alpha, beta, next, prod)"
  type        = string
  default     = "prod"
}

variable "eks_cluster_name" {
  description = "name of the existing EKS cluster"
  type        = string
  default     = "apps-hosting-service"
}

variable "mysql_host" {
  description = "hostname of the existing MySQL database"
  type        = string
  default     = "mysql.service.lawrencemcdaniel.com"
}

variable "mysql_port" {
  description = "port number of the existing MySQL database"
  type        = string
  default     = "3306"
}
