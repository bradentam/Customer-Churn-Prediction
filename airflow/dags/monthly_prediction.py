from airflow.decorators import task, dag
from airflow.operators.python_operator import PythonOperator
import sys
import pandas as pd
import numpy as np
import mlflow
from datetime import datetime
from mlflow.tracking import MlflowClient
from sklearn.model_selection import train_test_split
from google.cloud import storage

from sklearn.metrics import roc_auc_score, average_precision_score, f1_score

import sys
sys.path.append('/opt/airflow/modules/')
import utils


@dag(schedule_interval='@monthly', start_date=datetime(2023, 1, 1), catchup=False)
def monthly_prediction():
    @task
    def simulate_and_prepare_data(data_path, cat_features, num_features, n):
        df = utils.read_and_clean_data(data_path)
        sim_df = pd.DataFrame()
        df = df[cat_features + num_features]
        for col in df:
            sim_df[col] = np.random.choice(df[col].values, size=n)
        sim_transformed_df = utils.ohe_and_scale(sim_df, cat_features, num_features)
        return {'sim_df': sim_df.to_dict(), 
                'sim_transformed_df': sim_transformed_df.to_dict()}
    
    @task
    def predict_and_save(client, data):
        model = utils.load_model(client, 'RandomForestClassifier', '1')
        df = pd.DataFrame.from_dict(data['sim_df'])
        df_transformed = pd.DataFrame.from_dict(data['sim_transformed_df'])
        prediction = model.predict(df_transformed)
        df['prediction'] = prediction
        month_end = 'test'#(datetime.now() + pd.offsets.MonthEnd(0)).date()
        output_path = f'gs://scoring-artifacts-bt/predictions_{month_end}.csv'
        df.to_csv(output_path, index=False)


    TRACKING_SERVER_HOST = 'mlflow' #'127.0.0.1'
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
    
    data_path = f'gs://churn-data-bt/telecom_customer_churn.csv'
    # df = utils.read_and_clean_data(data_path)
    sim_df = simulate_and_prepare_data(data_path, cat_features, num_features, 1000)
    # sim_df_transformed = utils.ohe_and_scale(sim_df, cat_features, num_features)
    predict_and_save(client, sim_df)



dag_instance = monthly_prediction()