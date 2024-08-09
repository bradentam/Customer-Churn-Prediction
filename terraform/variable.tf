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

variable "db_instance_name" {
  description = "name for the db instance"
  type        = string
  default     = "mlflow-db"
}

variable "db_username" {
  description = "username for the postgres database"
  type        = string
  default     = "mlflowuser"
}

variable "db_password" {
  description = "password for the postgres database"
  type        = string
  default     = "admin"
}

variable "airflow_db_name" {
  description = "name for the airflow postgres database"
  type        = string
  default     = "airflow"
}

variable "mlflow_db_name" {
  description = "name for the mlflow postgres database"
  type        = string
  default     = "mlflow"
}

variable "grafana_db_name" {
  description = "name for the grafana postgres database"
  type        = string
  default     = "grafana"
}

variable "network_name" {
  description = "The name of the VPC network"
  type        = string
  default     = "mlflow-vpc"
}

variable "subnet_name" {
  description = "The name of the subnet"
  type        = string
  default     = "internal"
}

variable "subnet_ip_range" {
  description = "The CID IP range for subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "ip_peering_range" {
  description = "The IP range for VPC peering"
  type        = string
  default     = "10.1.0.0"
}

variable "ip_peering_name" {
  description = "name of the private ip range"
  type        = string
  default     = "mlflow-private"
}

variable "compute_instance_name" {
  description = "name for the compute instance"
  type        = string
  default     = "mlflow-server"
}

variable "mlflow_bucket_name" {
  description = "name of the mlflow bucket name"
  type        = string
  default     = "mlflow-artifacts-bt"
}

variable "scoring_bucket_name" {
  description = "name of the mlflow bucket name"
  type        = string
  default     = "scoring-artifacts-bt"
}