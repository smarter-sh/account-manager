
# 1. namespace
resource "kubernetes_namespace" "am" {
  metadata {
    name = local.environment_namespace
  }
}
