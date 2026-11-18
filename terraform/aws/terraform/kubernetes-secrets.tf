#------------------------------------------------------------------------------
# written by: Lawrence McDaniel
#             https://lawrencemcdaniel.com/
#
# date:   Dec-2025
#
# usage:  AWS EKS secrets Kubernetes resources
#------------------------------------------------------------------------------

# The shared MariaDB server (the smarter Helm chart's) and its root account, which
# the chart's init job creates Account Manager's database and user as. The deploy
# action (.github/actions/deploy/action.yml) reads these keys.
resource "kubernetes_secret" "mysql_root" {
  metadata {
    name      = "mysql-root"
    namespace = local.environment_namespace
  }

  data = {
    MYSQL_ROOT_USERNAME   = var.mysql_root_username
    MYSQL_ROOT_PASSWORD   = var.mysql_root_password
    MYSQL_HOST            = local.mysql_host
    MYSQL_PORT            = var.mysql_port
  }

  depends_on = [kubernetes_namespace.am]
}

# Account Manager's own database and user on the shared server. The chart's init
# job creates both; the deploy action reads these keys.
resource "random_password" "mysql_am" {
  length           = 16
  special          = true
  override_special = "_%@"
  keepers = {
    version = "1"
  }
}

resource "kubernetes_secret" "mysql_am" {
  metadata {
    name      = "mysql-am"
    namespace = local.environment_namespace
  }

  data = {
    AM_MYSQL_DATABASE = local.mysql_database
    AM_MYSQL_USER     = local.mysql_username
    AM_MYSQL_PASSWORD = random_password.mysql_am.result
  }

  depends_on = [kubernetes_namespace.am]
}

resource "random_password" "am_admin_password" {
  length           = 16
  special          = true
  override_special = "_%@"
  keepers = {
    version = "1"
  }
}

resource "kubernetes_secret" "am_admin_password" {
  metadata {
    name      = "am-admin"
    namespace = local.environment_namespace
  }

  data = {
    AM_ADMIN_USERNAME = "admin"
    AM_ADMIN_EMAIL    = "admin@${var.root_domain}"
    AM_ADMIN_PASSWORD = random_password.am_admin_password.result
    AM_LOGIN_URL      = "https://${local.environment_platform_domain}/login/"
  }

  depends_on = [kubernetes_namespace.am]
}


resource "random_password" "django_secret_key" {
  length           = 16
  special          = true
  override_special = "_%@"
  keepers = {
    version = "1"
  }
}

resource "kubernetes_secret" "django_secret_key" {
  metadata {
    name      = "am-django-secret-key"
    namespace = local.environment_namespace
  }

  data = {
    SECRET_KEY = random_password.django_secret_key.result
  }

  depends_on = [kubernetes_namespace.am]
}
