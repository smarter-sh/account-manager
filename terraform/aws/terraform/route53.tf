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

# -----------------------------------------------------------------------------
# AWS SES domain identity verification records
# -----------------------------------------------------------------------------
resource "aws_route53_record" "aws_ses_domain_identity" {
  zone_id = data.aws_route53_zone.platform_domain.zone_id
  name    = "_amazonses.${local.environment_platform_domain}"
  type    = "TXT"
  ttl     = "600"
  records = [aws_ses_domain_identity.environment_platform_domain.verification_token]
}

resource "aws_route53_record" "environment_platform_domain_amazonses_dkim_record" {
  count   = 3
  zone_id = data.aws_route53_zone.platform_domain.zone_id
  name    = "${aws_ses_domain_dkim.environment_platform_domain.dkim_tokens[count.index]}._domainkey"
  type    = "CNAME"
  ttl     = "600"
  records = ["${aws_ses_domain_dkim.environment_platform_domain.dkim_tokens[count.index]}.dkim.amazonses.com"]
}

resource "aws_route53_record" "environment_platform_domain_amazonses_dmarc_record" {
  zone_id = data.aws_route53_zone.platform_domain.zone_id
  name    = "_dmarc.${local.environment_platform_domain}"
  type    = "TXT"
  ttl     = "600"
  records = ["v=DMARC1;p=quarantine;rua=mailto:my_dmarc_report@${var.root_domain}"]
}
