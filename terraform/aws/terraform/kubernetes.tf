#------------------------------------------------------------------------------
# written by: Lawrence McDaniel
#             https://lawrencemcdaniel.com/
#
# date:   Dec-2025
#
# usage:  AWS EKS Kubernetes resources
#------------------------------------------------------------------------------

resource "kubernetes_namespace" "am" {
  metadata {
    name = local.environment_namespace
  }
}
