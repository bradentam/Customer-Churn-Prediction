# enables APIs
resource "google_project_service" "resourcemanager" {
  project = var.project_id
  service = "cloudresourcemanager.googleapis.com"
  disable_on_destroy = false
}
resource "google_project_service" "compute" {
  project = var.project_id
  service = "compute.googleapis.com"
  disable_on_destroy = false
}
resource "google_project_service" "storage" {
  project = var.project_id
  service = "storage.googleapis.com"
  disable_on_destroy = false
}
resource "google_project_service" "sqladmin" {
  project = var.project_id
  service = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "servicenetworking" {
  project = var.project_id
  service = "servicenetworking.googleapis.com"
  disable_on_destroy = false
}

# allows time for gcp APIs to be enabled before creating other resources
resource "time_sleep" "wait_for_resource" {
  depends_on = [google_project_service.compute,
                google_project_service.resourcemanager,
                google_project_service.servicenetworking,
                google_project_service.sqladmin,
                google_project_service.storage]

  create_duration = "60s"
} 