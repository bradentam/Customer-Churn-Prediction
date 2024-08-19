# Customer Churn Prediction

## Overview

This project was completed for the [MLOps Zoomcamp Course](https://github.com/DataTalksClub/mlops-zoomcamp/tree/main). The main goal was to create a complete MLOps workflow that includes experiment tracking and model registry, monitoring, workflow orchestration, containerized deployment on the cloud in a virtual machine (VM), and provisioning of infrastructure through IaC (infrastructure as code).

![image info](./images/architecture.png)

## Problem Description

Customer churn is a large part of every company as retaining existing customers is crucial for maintaining revenue and growth. It's essential to understand what leads a customer to leave and what preventative measures we can put in place. The goal is to train a classification model using various metrics to predict whether a customer is likely to leave. 

The dataset used for training is from a Telecommunications company collected found from [Kaggle](https://www.kaggle.com/datasets/shilongzhuang/telecom-customer-churn-by-maven-analytics?resource=download). More information about the dataset is available at the link.

In this example, we can get an understanding of churned customers in terms of age, how long the person has been a customer, the type of plan they have with the company, how many lines they have, etc.
   
## Technologies used

- `Terraform`: infrastructure as code (IaC)
- `GCP`: cloud infrastructure (VPC, VM, SQL, GCS)
- `MLFlow`: experiment tracking and model registry
- `Airflow`: orchestration
- `Docker`: deployment
- `Grafana`/`Evidently AI`: model and data monitoring

## Pre-requesites

- download docker and make
- setup GCP

### Setting up the GCP environment:

1. sign up for GCP and create a project
2. install [Google Cloud CLI](https://cloud.google.com/sdk/docs/install-sdk) and configure
3. create service account with owner and editor roles and create json key
4. open command shell and insert the following prompts (don't forget to replace `<INSERT_PROJECT_NAME>`): 

    ```shell
    gcloud config set project <INSERT_PROJECT_NAME>
    ```
    - Configures the CLI to the project
    <br>

    ```shell
    gcloud iam service-accounts create gcp-terraform --display-name "Terraform service account" 
    ```
    - Creates a service account to allow terraform to provision resources
    <br>

    ```shell
    gcloud projects add-iam-policy-binding <INSERT_PROJECT_NAME> --member="serviceAccount:gcp-terraform@<INSERT_PROJECT_NAME>.iam.gserviceaccount.com" --role="roles/owner"
    ```
    - Configures the service account role to owner
    <br>

    ```shell
    gcloud iam service-accounts keys create terraform-key.json --iam-account=gcp-terraform@<INSERT_PROJECT_NAME>.iam.gserviceaccount.com
    ```
    - Creates json key
    <br>

    ```shell
    export GOOGLE_APPLICATION_CREDENTIALS='/path/to/credentials.json'
    ```
    - Sets environmental variable in terminal to allow credentials to be used
    <br>


## Installation: Deploying with Docker on the GCP VM

1. Open a terminal where you would like to clone this repository and run:

    ```shell
    git clone https://github.com/bradentam/Customer-Churn-Prediction.git
    ```

2. In the terraform folder, configure the `variable.tf` file with your own specifications.

3. To build the GCP resources and deploy docker-compose on the VM, go to the root of the directory and run:

    ```shell
    make build-resources
    ```

    This command will do the following:
    - Apply terraform code
        - `terraform init`: Initializes the terraform files
        - `terraform apply`: Creates all the resources required for this project (VPC, VM, SQL database, GCS)
        - The terraform code will also produce a `.env` file which will be used by the docker-compose.yaml and other files to read in environmental variables to properly configure the connections to the cloud resources
    - Copy required files to the VM and build the docker-compose file

3. Download and upload the `telecom_customer_churn.csv` file to your GCS `data_bucket` specified in `variable.tf`.

4. After the VM is created, you can view the Airflow, MLflow, and Grafana UIs by entering the following in your web browser.  

    | **Service** | **URL**        | 
    |---------|--------------------|
    | Airflow | <EXTERNAL_IP>:8081 | 
    | MLflow  | <EXTERNAL_IP>:5000 | 
    | Grafana | <EXTERNAL_IP>:3000 | 

The external IP address can be found by using the following command:

```shell
gcloud compute instances list
```

After following these steps, you should have everything deployed on the cloud!


### Airflow:
The DAGs can be turned on in the UI. The username and password is `airflow`. 
![image info](./images/airflow.png)

#### Quarterly Retrain:

>> The quarterly retrain DAG will read and process the data and train 3 models (`LogisticRegression`, `RandomForestClassifier`, and `XGBClassfier`). Once all the models are done training, it will optimize the best performing model based off precision recall area under the curve (PR AUC). PR AUC is used as we want to optimize the model with respect to churned customers without being affected by the large number of non-churned cases. The best performing model is then registered to the model registry. This DAG runs quarterly, however in the real world, the training frequency would be set based off numerous factors such as market factors, customer behaviour, and model performance.

#### Monthly Prediction:

>> The monthly prediction DAG will simulate monthly data, however in the real world, there would be new data unlabeled data that needs to be predicted. The registered model is loaded and used to predict the simulated data, which is saved on GCS.

#### Monthly Monitor:

>> The monthly monitor DAG will use evidently to generate metrics about data and model drift which will be uploaded to the postgres database for the Grafana dashboard.

### MLflow:
After running the `quarterly_retrain.py` DAG, you'll be able to view the experiments and registered models in MLflow.
![image info](./images/mlflow_experiments.png)  

![image info](./images/mlflow_registry.png)

### Grafana:
After running the `monthly_prediction.py` and `monitor.py` DAGs, the monitoring metrics can be viewed in the Grafana dashboard. The username and password is `admin`. 
![image info](./images/grafana.png)

## Clean up

To stop docker on the VM, run:

```shell
make down-vm
```

To clean up GCP resources, run:

```shell
make clean-resources
```

*Note: you may need to run `make clean-resources` several times to successfully destroy all resources*
