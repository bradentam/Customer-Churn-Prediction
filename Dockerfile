FROM python:3.10-slim-buster

RUN apt-get update && apt-get install -y curl

COPY requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt

ENV BACKEND_STORE_URI sqlite:///mlflow.db
#postgresql+psycopg2://airflow:airflow@postgres:5432/airflow
#sqlite:///mlflow.db
ENV ARTIFACT_ROOT /mlflow/artifacts


CMD mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri $BACKEND_STORE_URI --default-artifact-root $ARTIFACT_ROOT