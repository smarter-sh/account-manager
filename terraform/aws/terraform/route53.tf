#------------------------------------------------------------------------------
# written by: Lawrence McDaniel
#             https://lawrencemcdaniel.com/
#
# date:   Dec-2025
#
# usage:  Smarter Account Manager AWS Route53 resources
#------------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# From Kubernetes shared infrastructure, managed by openedx_devops repo
# -----------------------------------------------------------------------------
data "kubernetes_service" "ingress_nginx_controller" {
  metadata {
    name      = "common-ingress-nginx-controller"
    namespace = "kube-system"
  }
}
data "aws_elb_hosted_zone_id" "main" {}

# -----------------------------------------------------------------------------
# root Domain: smarter.sh
# this is created manually in the AWS Route53 console
# -----------------------------------------------------------------------------
data "aws_route53_zone" "root_domain" {
  name = var.root_domain
}


# -----------------------------------------------------------------------------
# environment Domain: alpha.am.smarter.sh, beta.am.smarter.sh, etc.
# this is managed by smarter via a manage.py command that runs during deployments
# -----------------------------------------------------------------------------
data "aws_route53_zone" "platform_domain" {
  name    = local.platform_domain
}

# -----------------------------------------------------------------------------
# Account manager web console DNS A record
# -----------------------------------------------------------------------------
resource "aws_route53_record" "web_console" {
  zone_id = data.aws_route53_zone.platform_domain.zone_id
  name    = local.environment_platform_domain
  type    = "A"
  alias {
    name                   = data.kubernetes_service.ingress_nginx_controller.status[0].load_balancer[0].ingress[0].hostname
    zone_id                = data.aws_elb_hosted_zone_id.main.id
    evaluate_target_health = false
  }
}

# -----------------------------------------------------------------------------
# Account manager api DNS A record
# -----------------------------------------------------------------------------
resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.platform_domain.zone_id
  name    = local.environment_api_domain
  type    = "A"
  alias {
    name                   = data.kubernetes_service.ingress_nginx_controller.status[0].load_balancer[0].ingress[0].hostname
    zone_id                = data.aws_elb_hosted_zone_id.main.id
    evaluate_target_health = false
  }
}
