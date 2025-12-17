
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
    SMARTER_MYSQL_DATABASE = local.mysql_database
    SMARTER_MYSQL_USERNAME = local.mysql_username
    SMARTER_MYSQL_PASSWORD = random_password.mysql_am.result
    MYSQL_HOST             = var.mysql_host
    MYSQL_PORT             = var.mysql_port
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
    SMARTER_ADMIN_USERNAME = "admin"
    SMARTER_ADMIN_EMAIL    = "admin@${var.root_domain}"
    am_admin_password = random_password.am_admin_password.result
    SMARTER_LOGIN_URL      = "https://${local.environment_platform_domain}/login/"
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
