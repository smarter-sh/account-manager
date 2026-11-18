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

variable "smarter_namespace_base" {
  description = "base name of the Smarter platform's Kubernetes namespace, to which the environment is appended (e.g. smarter-ubc -> smarter-ubc-alpha). Its smarter-mariadb Service is the shared MariaDB server."
  type        = string
  default     = "smarter-ubc"
}

variable "mysql_host" {
  description = "host of the shared MariaDB server, the smarter Helm chart's. Empty: its in-cluster name, smarter-mariadb.<smarter_namespace_base>-<environment>.svc.cluster.local"
  type        = string
  default     = ""
}

variable "mysql_port" {
  description = "port number of the shared MariaDB server"
  type        = string
  default     = "3306"
}

variable "mysql_root_username" {
  description = "username of the shared MariaDB server's root user (the smarter Helm chart's MariaDB)"
  type        = string
  default     = "root"
}

variable "mysql_root_password" {
  description = "password of the shared MariaDB server's root user: the same as the root password in the Smarter platform's mysql-root secret"
  type        = string
}
