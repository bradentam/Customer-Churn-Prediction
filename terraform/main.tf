provider "google" {
  credentials = file(var.credentials_file)
  project     = var.project_id
  region      = var.region
  zone        = var.zone
}

# module containing resources to create vpc
module "vpc" {
    source  = "terraform-google-modules/network/google"
    version = "~> 9.1"

    project_id   = var.project_id
    network_name = var.network_name
    routing_mode = "REGIONAL"

    subnets =[
        {
            subnet_name           = var.subnet_name
            subnet_ip             = var.subnet_ip_range
            subnet_region         = var.region
        }
    ]
}

# following 3 resources required for private IP connection of postgres database
resource "google_compute_global_address" "private_ip_range" {
  project = var.project_id

  network = module.vpc.network_name

  name          = var.ip_peering_name
  purpose       = "VPC_PEERING"
  address       = var.ip_peering_range
  prefix_length = "24"
  address_type  = "INTERNAL"

  depends_on = [module.vpc]
}

resource "google_service_networking_connection" "private_service_connection" {
  network                 = module.vpc.network_id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]

  depends_on = [module.vpc,
                google_compute_global_address.private_ip_range]
}

resource "google_compute_network_peering_routes_config" "peering_routes" {
  project = var.project_id
  
  peering = google_service_networking_connection.private_service_connection.peering
  network = module.vpc.network_name

  import_custom_routes = false
  export_custom_routes = false

  depends_on = [module.vpc, 
                google_service_networking_connection.private_service_connection]
}


resource "google_sql_database_instance" "pg-instance" {
  name             = var.db_instance_name
  database_version = "POSTGRES_14"
  region           = var.region

  settings {
    tier = "db-f1-micro"
    ip_configuration {  
      ipv4_enabled    = false  # Disable public IP
      private_network = module.vpc.network_self_link #google_compute_network.default.id #google_compute_network.default.id # Private network must be specified
    }
  }
  
  depends_on = [module.vpc, 
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

resource "google_storage_bucket" "mlflow-artifacts" {
  name          = var.mlflow_bucket_name
  location      = var.region
  force_destroy = true
}

resource "google_storage_bucket" "scoring-artifacts" {
  name          = var.scoring_bucket_name
  location      = var.region
  force_destroy = true
}


resource "google_compute_instance" "mlflow_server" {
  name         = var.compute_instance_name
  machine_type = "e2-medium"
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

  # metadata_startup_script = <<-EOT
  #   #!/bin/bash
  #   sudo apt update
  #   pip install virtualenv
    
  #   # Create a virtual environment
  #   virtualenv mlflow_env

  #   # Activate the virtual environment
  #   source mlflow_env/bin/activate

  #   pip install mlflow psycopg2-binary
  #   echo mlflow installed
  #   nohup mlflow server \
  #     --host 0.0.0.0 \
  #     --port 5000 \
  #     --backend-store-uri postgresql://${var.db_username}:${var.db_password}@${google_sql_database_instance.pg-instance.ip_address[0].ip_address}:5432/${var.mlflow_db_name} \
  #     --default-artifact-root gs://${google_storage_bucket.mlflow-artifacts.name}/ > mlflow.log 2>&1 &
    
  #   echo "MLflow installed and server started" > /var/log/startup-script.log
  # EOT

  depends_on = [module.vpc, 
                google_compute_global_address.private_ip_range,
                google_service_networking_connection.private_service_connection,
                google_compute_network_peering_routes_config.peering_routes]
}

resource "google_compute_firewall" "mlflow_firewall" {
  name    = "allow-mlops"
  network = module.vpc.network_name

  allow {
    protocol = "tcp"
    ports    = [22, 5000]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["mlops-server"]

}