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
    network_name = "test-vpc"
    routing_mode = "GLOBAL"

    subnets =[
        {
            subnet_name           = "private"
            subnet_ip             = "10.0.1.0/24"
            subnet_region         = "us-west1"
            subnet_private_access = "true"
        }
    ]
}

# following 3 resources required for private IP connection of postgres database
resource "google_compute_global_address" "private_ip_range" {
  project = var.project_id

  network = module.vpc.network_name

  name          = "test"
  purpose       = "VPC_PEERING"
  address       = "10.1.0.0"
  prefix_length = "24"
  address_type  = "INTERNAL"
}

resource "google_service_networking_connection" "private_service_connection" {
  network                 = module.vpc.network_id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]

  depends_on = [
    google_compute_global_address.private_ip_range,
    google_project_service.compute
  ]
}

resource "google_compute_network_peering_routes_config" "peering_routes" {
  project = var.project_id
  
  peering = google_service_networking_connection.private_service_connection.peering
  network = module.vpc.network_name

  import_custom_routes = true
  export_custom_routes = true

  depends_on = [google_service_networking_connection.private_service_connection]
}


resource "google_sql_database_instance" "pg-instance" {
  name             = "mlflow-db"
  database_version = "POSTGRES_14"
  region           = var.region

  settings {
    tier = "db-f1-micro"
    ip_configuration {
      ipv4_enabled    = false  # Disable public IP
      private_network = module.vpc.network_self_link #google_compute_network.default.id #google_compute_network.default.id # Private network must be specified
    }
  }
  
  depends_on = [google_compute_network_peering_routes_config.peering_routes]

  deletion_protection = false

}

resource "google_sql_database" "mlflow" {
  name     = var.db_name
  instance = google_sql_database_instance.pg-instance.name
}

resource "google_sql_user" "default" {
  name     = var.db_username
  instance = google_sql_database_instance.pg-instance.name
  password = var.db_password
}

resource "google_storage_bucket" "mlflow-artifacts" {
  name          = "mlflow-artifacts-braden_tam"
  location      = var.region
  force_destroy = true
}

resource "google_storage_bucket" "scoring-artifacts" {
  name          = "scoring-artifacts-braden_tam"
  location      = var.region
  force_destroy = true
}


resource "google_compute_instance" "mlflow_server" {
  name         = "mlflow-server"
  machine_type = "e2-medium"
  tags         = ["mlflow-server"]

  boot_disk {
    initialize_params {
      image = "deeplearning-platform-release/common-cpu-v20240708-debian-11" # Deep Learning VM image
      size  = 50 # Size in GB
      type  = "pd-ssd" # SSD disk type
    }
  }

  network_interface {
    network = "default"

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
  #   pip install mlflow psycopg2-binary
  #   echo mlflow installed
  #   nohup mlflow server \
  #     --host 0.0.0.0 \
  #     --port 5000 \
  #     --backend-store-uri postgresql://${var.db_username}:${var.db_password}@${google_sql_database_instance.pg-instance.ip_address[0].ip_address}:5432/${var.db_name} \
  #     --default-artifact-root gs://${google_storage_bucket.mlflow-artifacts.name}/ > mlflow.log 2>&1 &
  # EOT
}

resource "google_compute_firewall" "mlflow_firewall" {
  name    = "allow-mlflow"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = [22, 5000]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["mlflow-server"]

}

# nohup mlflow server \
#   --host 0.0.0.0 \
#   --port 5000 \
#   --backend-store-uri postgresql://mlflowuser:test123@10.1.0.5:5432/mlflow \
#   --default-artifact-root gs://mlflow-artifacts-braden_tam


# resource "google_compute_network" "default" {
#   name                    = var.network_name
#   auto_create_subnetworks = false

# resource "google_storage_bucket" "mlflow-artifacts" {
#   name          = "mlflow-artifacts-braden_tam"
#   location      = var.region
#   force_destroy = true

#   depends_on = [google_project_service.storage, google_project_service.resourcemanager]
# }

# resource "google_storage_bucket" "scoring-artifacts" {
#   name          = "scoring-artifacts-braden_tam"
#   location      = var.region
#   force_destroy = true

#   depends_on = [google_project_service.storage, google_project_service.resourcemanager]
# }

# data "google_compute_network" "default" {
#   name = "default"
# }

# resource "google_compute_network" "default" {
#   name                    = var.network_name
#   auto_create_subnetworks = false

#   lifecycle {
#     prevent_destroy = true
#   }
#   depends_on = [google_project_service.compute]
# }

# resource "google_compute_subnetwork" "default" {
#   name          = var.subnet_name
#   ip_cidr_range = var.ip_cidr_range
#   network       = google_compute_network.default.id
#   region        = var.region

#   private_ip_google_access = true

#   lifecycle {
#     create_before_destroy = true
#   }
#   depends_on = [google_project_service.compute]
# }

# resource "google_compute_global_address" "private_ip_range" {
#   name          = "private-ip-range"
#   purpose       = "VPC_PEERING"
#   address_type  = "INTERNAL"
#   prefix_length = 16
#   network       = google_compute_network.default.id
# }

# resource "google_service_networking_connection" "private_vpc_connection" {
#   network                 = google_compute_network.default.id
#   reserved_peering_ranges = [google_compute_global_address.private_ip_range.name]
#   service                 = "servicenetworking.googleapis.com"

#   depends_on = [
#     google_compute_global_address.private_ip_range,
#     google_project_service.compute
#   ]

#   lifecycle {
#     create_before_destroy = true
#   }
# }

# resource "google_sql_database_instance" "pg-instance" {
#   name             = "mlflow-db"
#   database_version = "POSTGRES_14"
#   region           = var.region

#   settings {
#     tier = "db-f1-micro"
#     ip_configuration {
#       ipv4_enabled    = false  # Disable public IP
#       private_network = google_compute_network.default.id #google_compute_network.default.id # Private network must be specified
#       # authorized_networks {
#       #   name  = "Your VPN"
#       #   value = var.vpn_to_access_db
#       # }
#     }
#   }
  
#   depends_on = [google_project_service.sqladmin, google_project_service.resourcemanager]

#   deletion_protection = false

# }

# resource "google_sql_database" "mlflow" {
#   name     = var.db_name
#   instance = google_sql_database_instance.pg-instance.name
# }

# resource "google_sql_user" "default" {
#   name     = var.db_username
#   instance = google_sql_database_instance.pg-instance.name
#   password = var.db_password
# }

# output "external-ip" {
#   value = google_sql_database_instance.pg-instance.ip_address[0].ip_address
# }

# resource "google_compute_instance" "mlflow_server" {
#   name         = "mlflow-server"
#   machine_type = "e2-medium"
#   tags         = ["mlflow-server"]

#   boot_disk {
#     initialize_params {
#       image = "deeplearning-platform-release/common-cpu-v20240708-debian-11" # Deep Learning VM image
#       size  = 50 # Size in GB
#       type  = "pd-ssd" # SSD disk type
#     }
#   }

#   network_interface {
#     network = "default"

#     access_config {
#       // Assigns an external IP address
#     }
#   }

#   service_account {
#     scopes = ["https://www.googleapis.com/auth/cloud-platform"]
#   }

#   metadata_startup_script = <<-EOT
#     #!/bin/bash
#     sudo apt update
#     echo pip3 installed
#     pip3 install mlflow google-cloud-storage psycopg2-binary
#     echo mlflow installed
#     nohup mlflow server \
#       --host 0.0.0.0 \
#       --port 5000 \
#       --backend-store-uri postgresql://${var.db_username}:${var.db_password}@${google_sql_database_instance.pg-instance.ip_address[0].ip_address}:5432/${var.db_name} \
#       --default-artifact-root gs://${google_storage_bucket.mlflow-artifacts.name}/ > mlflow.log 2>&1 &
#   EOT

#   depends_on = [google_project_service.compute, google_project_service.resourcemanager]
# }

# resource "google_compute_firewall" "mlflow_firewall" {
#   name    = "allow-mlflow"
#   network = "default"

#   allow {
#     protocol = "tcp"
#     ports    = [22, 5000]
#   }

#   source_ranges = ["0.0.0.0/0"]
#   target_tags   = ["mlflow-server"]

#   depends_on = [google_project_service.compute, google_project_service.resourcemanager]
# }

# mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri postgresql://mlflowuser:test123@/complete-energy-422622-u9:us-west1:mlflow-db/mlflow --default-artifact-root gs://mlflow-artifacts-braden_tam/
# mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri postgresql://mlflowuser:test123@10.65.80.3:5432/mlflow --default-artifact-root gs://mlflow-artifacts-braden_tam/
# mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri postgresql://test:test123@34.67.63.217:5432/mlflow --default-artifact-root gs://mlflow-artifacts-braden_tam/


# mlflow server \
# --host 0.0.0.0 \
# --port 5000 \
# --backend-store-uri postgresql://admin:admin@10.82.32.5:5432/mlflow \
# --default-artifact-root gs://mlflow-artifacts-bradentam/