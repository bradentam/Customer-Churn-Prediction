# Customer Churn Prediction

### Overview

- motivation
- infrastructure visual

### Problem Description

- help identify what factors contribute to customer churn so comapny X can invest more into improving certain areas of the business

### Dataset

- [Kaggle](https://www.kaggle.com/datasets/shilongzhuang/telecom-customer-churn-by-maven-analytics?resource=download)
- example table of column description
### Folder Structure


### Infrastructure

- terraform
- GCP
- MLFlow (experiment tracking and model registry)
- Orchestration
- testing (pytest), docker-compose (integration-testing)
- Docker for deployment
- Grafana/Prmetheus/Evidently AI (model monitoring)

### Virtual Machine

- sign up for GCP
- install [Google Cloud CLI](https://cloud.google.com/sdk/docs/install-sdk)
- create service account with owner and editor roles and create json key
https://dudeblogstech.medium.com/creating-a-google-cloud-vm-with-terraform-a-step-by-step-guide-c5d72c2003f8

```gcloud config set project customer-churn-mlops```

```gcloud iam service-accounts create gcp-terraform --display-name "Terraform service account" ```

```gcloud projects add-iam-policy-binding customer-churn-mlops --member="serviceAccount:gcp-terraform@customer-churn-mlops.iam.gserviceaccount.com" --role="roles/owner"```

```gcloud iam service-accounts keys create ~/terraform-key.json --iam-account=gcp-terraform@customer-churn-mlops.iam.gserviceaccount.com```

- set environmental variable in terminal to allow credentials to be used
```export GOOGLE_APPLICATION_CREDENTIALS='/path/to/credentials.json'```

- run terraform init, plan, apply
    - this will create all the resources required (VM, postgres, gcs)

MLFlow
- access by entering "external_ip_address:5000" into your web browser
- the external IP address can be found by using the following command
```gcloud compute instances list```


### EDA

### Modelling / Training


### Performance


### Monitoring


### Project Replication

- prerequisites

### Further Improvements
