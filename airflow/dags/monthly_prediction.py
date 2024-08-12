from airflow.decorators import task, dag
from airflow.sensors.external_task import ExternalTaskSensor

import pandas as pd
import numpy as np
import mlflow
from datetime import datetime, timedelta
from mlflow.tracking import MlflowClient
from sklearn.model_selection import train_test_split
from google.cloud import storage

from sklearn.metrics import roc_auc_score, average_precision_score, f1_score

import sys
sys.path.append('/opt/airflow/modules/')
import utils


@dag(schedule_interval='@monthly', start_date=datetime(2024, 2, 1), catchup=True)
def monthly_prediction():
    
    wait_for_retrain = ExternalTaskSensor(
        task_id='wait_for_retrain',
        external_dag_id='quarterly_retrain',  
        external_task_id='optimize_and_register_best_classifier',  
        execution_date_fn=lambda exec_date: exec_date.replace(day=1) - timedelta(days=1),
        allowed_states=['success'],
        failed_states=['failed', 'skipped'],
        mode='reschedule', 
        timeout=600,
    )

    @task
    def simulate_and_prepare_data(data_path, cat_features, num_features, n):
        seed = int(datetime.now().timestamp()) % 10000
        np.random.seed(seed)

        df = utils.read_and_clean_data(data_path)
        sim_df = pd.DataFrame()
        df = df[cat_features + num_features]
        for col in df:
            sim_df[col] = np.random.choice(df[col].values, size=n)
        sim_transformed_df = utils.ohe_and_scale(sim_df, cat_features, num_features)
        print(sim_df['offer'].value_counts())
        return {'sim_df': sim_df.to_dict(), 
                'sim_transformed_df': sim_transformed_df.to_dict()}
    
    @task
    def predict_and_save(client, data, **kwargs):
        model = utils.load_model(client, 'RandomForestClassifier')
        df = pd.DataFrame.from_dict(data['sim_df'])
        df_transformed = pd.DataFrame.from_dict(data['sim_transformed_df'])
        prediction = model.predict(df_transformed)
        df['prediction'] = prediction
        month_end = (kwargs['logical_date'].replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        output_path = f'gs://scoring-artifacts-bt/predictions_{month_end}.csv'
        df.to_csv(output_path, index=False)
        print(df['prediction'].value_counts())


    TRACKING_SERVER_HOST = 'mlflow'
    TRACKING_URI = f'http://{TRACKING_SERVER_HOST}:5000'
    client = MlflowClient(tracking_uri=TRACKING_URI)

    cat_features = ['gender', 'married', 'offer', 'phone_service', 'multiple_lines', 'internet_service', 
                'internet_type', 'online_security', 'online_backup', 'device_protection_plan',
                'premium_tech_support', 'streaming_tv', 'streaming_movies', 'streaming_music', 
                'unlimited_data', 'contract', 'paperless_billing', 'payment_method']

    num_features = ['age', 'number_of_dependents', 'tenure_in_months', 'number_of_referrals', 
                    'avg_monthly_long_distance_charges', 'avg_monthly_gb_download', 'monthly_charge', 
                    'total_charges', 'total_refunds', 'total_extra_data_charges', 
                    'total_long_distance_charges', 'total_revenue']
    
    wait_for_retrain
    data_path = f'gs://churn-data-bt/telecom_customer_churn.csv'
    data = simulate_and_prepare_data(data_path, cat_features, num_features, 1000)
    predict_and_save(client, data)



dag_instance = monthly_prediction()