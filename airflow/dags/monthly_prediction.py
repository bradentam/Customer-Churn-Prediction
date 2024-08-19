from airflow.decorators import task, dag

import os
from dotenv import load_dotenv
from datetime import datetime
import mlflow
from mlflow.tracking import MlflowClient

@dag(schedule_interval='@monthly', start_date=datetime(2023, 2, 2), catchup=True)
def monthly_prediction():
    @task
    def simulate_and_prepare_data(data_path, cat_features, num_features, n, **kwargs):
        import numpy as np
        import pandas as pd
        import sys
        sys.path.append('/opt/airflow/modules/')
        from utils import read_and_clean_data, ohe_and_scale

        seed = int(kwargs['logical_date'].timestamp())
        np.random.seed(seed)

        df = read_and_clean_data(data_path)
        sim_df = pd.DataFrame()
        df = df[cat_features + num_features]
        for col in df:
            sim_df[col] = np.random.choice(df[col].values, size=n)
        sim_transformed_df = ohe_and_scale(sim_df, cat_features, num_features)
        return {'sim_df': sim_df.to_dict(), 
                'sim_transformed_df': sim_transformed_df.to_dict()}
    
    @task
    def predict_and_save(client, data, **kwargs):
        import numpy as np
        import pandas as pd
        from datetime import timedelta
        import sys
        sys.path.append('/opt/airflow/modules/')
        from utils import load_model

        model = load_model(client, 'RandomForestClassifier')
        df = pd.DataFrame.from_dict(data['sim_df'])
        df_transformed = pd.DataFrame.from_dict(data['sim_transformed_df'])
        prediction = model.predict(df_transformed)
        df['prediction'] = prediction
        month_end = (kwargs['logical_date'].replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        output_path = f'gs://{scoring_bucket_name}/predictions_{month_end}.csv'
        df.to_csv(output_path, index=False)
        print(df['prediction'].value_counts())


    load_dotenv()
    scoring_bucket_name = os.getenv('SCORING_BUCKET_NAME')
    data_bucket_name = os.getenv('DATA_BUCKET_NAME')

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

    data_path = f'gs://{data_bucket_name}/telecom_customer_churn.csv'
    data = simulate_and_prepare_data(data_path, cat_features, num_features, 1000)
    predict_and_save(client, data)

dag_instance = monthly_prediction()