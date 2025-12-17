#------------------------------------------------------------------------------
# written by: Lawrence McDaniel
#             https://lawrencemcdaniel.com/
#
# date:   Dec-2025
#
# usage:  AWS EKS ingress Kubernetes resources
#------------------------------------------------------------------------------




resource "kubernetes_manifest" "platform_ingress" {
  manifest = yamldecode(templatefile("${path.module}/templates/ingress.yaml.tpl", {
    cluster_issuer        = local.environment_platform_domain
    domain                = local.environment_platform_domain
    environment_namespace = local.environment_namespace
    service_name          = "account-manager"
  }))

  depends_on = [
    data.aws_route53_zone.platform_domain
  ]
}


resource "kubernetes_manifest" "api_ingress" {
  manifest = yamldecode(templatefile("${path.module}/templates/ingress.yaml.tpl", {
    cluster_issuer        = local.environment_api_domain
    domain                = local.environment_api_domain
    environment_namespace = local.environment_namespace
    service_name          = "account-manager"
  }))

  depends_on = [
    data.aws_route53_zone.platform_domain
  ]
}
