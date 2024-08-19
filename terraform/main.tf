terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "~> 4.85.0" 
      # version 5.0 has issues with terraform destroy of the private_service_connection 
      # https://github.com/hashicorp/terraform-provider-google/issues/16275
    }
  }
}

provider "google" {
  credentials = file(var.credentials_file)
  project     = var.project_id
  region      = var.region
  zone        = var.zone
}

resource "google_compute_network" "vpc_network" {
  name                    = var.network_name
  routing_mode            = "REGIONAL"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = var.subnet_name
  ip_cidr_range = var.subnet_ip_range
  region        = var.region
  network       = google_compute_network.vpc_network.id
}


# following 3 resources required for private IP connection of postgres database
resource "google_compute_global_address" "private_ip_range" {
  project = var.project_id

  network = var.network_name

  name          = var.ip_peering_name
  purpose       = "VPC_PEERING"
  address       = var.ip_peering_range
  prefix_length = "24"
  address_type  = "INTERNAL"

  depends_on = [google_compute_network.vpc_network]
}

resource "google_service_networking_connection" "private_service_connection" {
  network                 = google_compute_network.vpc_network.id 
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]

  depends_on = [google_compute_network.vpc_network,
                google_compute_global_address.private_ip_range]
}

resource "google_compute_network_peering_routes_config" "peering_routes" {
  project = var.project_id
  
  peering = google_service_networking_connection.private_service_connection.peering
  network = var.network_name

  import_custom_routes = false
  export_custom_routes = false

  depends_on = [google_compute_network.vpc_network,
                google_service_networking_connection.private_service_connection]
}


resource "google_sql_database_instance" "pg-instance" {
  name             = var.db_instance_name
  database_version = "POSTGRES_14"
  region           = var.region

  settings {
    tier = "db-g1-small"
    ip_configuration {  
      ipv4_enabled    = false  # Disable public IP
      private_network = google_compute_network.vpc_network.self_link
    }
    
    database_flags {
      name  = "max_connections"
      value = "100"
    }
  
  }

  depends_on = [google_compute_network.vpc_network, 
                google_compute_global_address.private_ip_range,
                google_service_networking_connection.private_service_connection,
                google_compute_network_peering_routes_config.peering_routes]

  deletion_protection = false

}

resource "google_sql_database" "airflow_db" {
  name     = var.airflow_db_name
  instance = google_sql_database_instance.pg-instance.name

  depends_on = [google_sql_database_instance.pg-instance]
}

resource "google_sql_database" "mlflow_db" {
  name     = var.mlflow_db_name
  instance = google_sql_database_instance.pg-instance.name

  depends_on = [google_sql_database_instance.pg-instance]
}

resource "google_sql_database" "grafana_db" {
  name     = var.grafana_db_name
  instance = google_sql_database_instance.pg-instance.name

  depends_on = [google_sql_database_instance.pg-instance]
}

resource "google_sql_user" "user" {
  name     = var.db_username
  instance = google_sql_database_instance.pg-instance.name
  password = var.db_password

  depends_on = [google_sql_database_instance.pg-instance]
}

resource "google_storage_bucket" "data" {
  name          = var.data_bucket
  location      = var.region
  force_destroy = true
}

resource "google_storage_bucket" "mlflow-artifacts" {
  name          = var.mlflow_bucket
  location      = var.region
  force_destroy = true
}

resource "google_storage_bucket" "scoring-artifacts" {
  name          = var.scoring_bucket
  location      = var.region
  force_destroy = true
}


resource "google_compute_instance" "mlops_server" {
  name         = var.compute_instance_name
  machine_type = "e2-standard-2"
  tags         = ["mlops-server"]

  boot_disk {
    initialize_params {
      image = "deeplearning-platform-release/common-cpu-v20240708-debian-11" # Deep Learning VM image
      size  = 50 # Size in GB
      type  = "pd-ssd" # SSD disk type
    }
  }

  network_interface {
    network    = "projects/${var.project_id}/global/networks/${var.network_name}"
    subnetwork = "projects/${var.project_id}/regions/${var.region}/subnetworks/${var.subnet_name}"

    access_config {
      // Assigns an external IP address
    }
  }

  service_account {
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    sudo apt update
    sudo apt install docker.io
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.15.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

  EOT

  depends_on = [google_compute_network.vpc_network, 
                google_compute_global_address.private_ip_range,
                google_service_networking_connection.private_service_connection,
                google_compute_network_peering_routes_config.peering_routes]
}

resource "google_compute_firewall" "mlflow_firewall" {
  name    = "allow-mlops"
  network = var.network_name

  allow {
    protocol = "tcp"
    ports    = [22, 3000, 5000, 8080, 8081, 8974]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["mlops-server"]

  depends_on = [google_compute_network.vpc_network, 
                google_compute_global_address.private_ip_range,
                google_service_networking_connection.private_service_connection,
                google_compute_network_peering_routes_config.peering_routes]
}

# produce .env file for environmental variables to read by other files
resource "local_file" "env_file" {
  content = <<-EOT
    PROJECT_ID=${var.project_id}
    ZONE=${var.zone}
    VM_NAME=${var.compute_instance_name}
    DB_USERNAME=${var.db_username}
    DB_PASSWORD=${var.db_password}
    AIRFLOW_DB_NAME=${var.airflow_db_name}
    MLFLOW_DB_NAME=${var.mlflow_db_name}
    GRAFANA_DB_NAME=${var.grafana_db_name}
    DB_HOST=${google_sql_database_instance.pg-instance.ip_address[0]["ip_address"]}
    MLFLOW_BUCKET_NAME=${var.mlflow_bucket}
    DATA_BUCKET_NAME=${var.data_bucket}
    SCORING_BUCKET_NAME=${var.scoring_bucket}
  EOT

  filename = "${path.module}/../.env"
}
