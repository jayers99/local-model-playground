# Synthetic example. Not real infrastructure. Demonstrates an overly-broad IAM role.

resource "google_service_account" "deploy" {
  account_id   = "app-deploy"
  display_name = "App deployment service account"
}

resource "google_project_iam_member" "deploy_editor" {
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}
