build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

build-resources:
	@echo "Initializing Terraform..."
	cd terraform && terraform init
	@echo "apply GCP resource provisioning..."
	cd terraform && terraform apply -auto-approve
	chmod 644 .env
	export $$(cat .env | xargs)

	@echo "copying files to VM..."
	gcloud compute scp Makefile ${VM_NAME}:~ --zone ${ZONE}
	gcloud compute scp docker-compose.yaml ${VM_NAME}:~ --zone ${ZONE}
	gcloud compute scp Dockerfile.airflow ${VM_NAME}:~ --zone ${ZONE}
	gcloud compute scp Dockerfile.mlflow ${VM_NAME}:~ --zone ${ZONE}
	gcloud compute scp .env ${VM_NAME}:~ --zone ${ZONE}
	gcloud compute scp terraform-key.json ${VM_NAME}:~ --zone ${ZONE}
	gcloud compute ssh --zone ${ZONE} ${VM_NAME} --project ${PROJECT_ID} \
	--command "sudo chmod 644 .env && sudo chmod 644 terraform-key.json" # converts .env to textfile and allows its to be executable
	gcloud compute scp requirements.txt ${VM_NAME}:~ --zone ${ZONE}
	gcloud compute ssh --zone ${ZONE} ${VM_NAME} --project ${PROJECT_ID} \
	--command "mkdir monitoring && cd monitoring && mkdir config dashboards"
	gcloud compute scp monitoring/config/grafana_dashboards.yaml ${VM_NAME}:~/monitoring/config --zone ${ZONE}
	gcloud compute scp monitoring/config/grafana_datasources.yaml ${VM_NAME}:~/monitoring/config --zone ${ZONE}
	gcloud compute scp monitoring/dashboards/monitor.json ${VM_NAME}:~/monitoring/dashboards --zone ${ZONE}
	gcloud compute ssh --zone ${ZONE} ${VM_NAME} --project ${PROJECT_ID} \
	--command "mkdir airflow && cd airflow && mkdir config dags logs modules plugins"
	gcloud compute scp airflow/dags/quarterly_retrain.py ${VM_NAME}:~/airflow/dags --zone ${ZONE}
	gcloud compute scp airflow/dags/monthly_prediction.py ${VM_NAME}:~/airflow/dags --zone ${ZONE}
	gcloud compute scp airflow/dags/monitor.py ${VM_NAME}:~/airflow/dags --zone ${ZONE}
	gcloud compute scp airflow/modules/utils.py ${VM_NAME}:~/airflow/modules --zone ${ZONE}
	gcloud compute scp airflow/modules/ml_utils.py ${VM_NAME}:~/airflow/modules --zone ${ZONE}
	@echo "files successfully copied to VM"

	gcloud compute ssh --zone ${ZONE} ${VM_NAME} --project ${PROJECT_ID} --command "make build up"

down-vm:
	gcloud compute ssh --zone ${ZONE} ${VM_NAME} --project ${PROJECT_ID} --command "docker-compose down"
clean-resources:
	@echo "cleaning GCP resources..."
	cd terraform && terraform destroy -auto-approve

.PHONY: