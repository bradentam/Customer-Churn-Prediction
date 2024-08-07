variable "project_id" {
  description = "id for project"
  type        = string
  default     = "customer-churn-mlops"
}

variable "region" {
  description = "Region"
  type        = string
  default     = "us-west1"
}

variable "zone" {
  description = "zone"
  type        = string
  default     = "us-west1-a"
}

variable "credentials_file" {
  description = "path to credentials file"
  type        = string
  default     = "/Users/bradentam/terraform-key.json"
}

variable "db_username" {
  description = "username for the postgres database"
  type        = string
  default     = "mlflowuser"
}

variable "db_password" {
  description = "password for the postgres database"
  type        = string
  default     = "test123"
}

variable "db_name" {
  description = "name for the postgres database"
  type        = string
  default     = "mlflow"
}

variable "network_name" {
  description = "The name of the VPC network"
  type        = string
  default     = "main"
}

variable "subnet_name" {
  description = "The name of the subnet"
  type        = string
  default     = "default-subnet"
}

variable "ip_cidr_range" {
  description = "The IP CIDR range for the subnet"
  type        = string
  default     = "10.0.0.0/16"
}

variable "vpn_to_access_db" {
  default     = "0.0.0.0/0"
  description = "VPN that will be used to connect to DB, while using 0.0.0.0/0 the application will be available from any IP (it will be accessible from the internet)."
}