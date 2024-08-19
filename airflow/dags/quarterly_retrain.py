from airflow.decorators import task, dag
import os
from dotenv import load_dotenv
from datetime import datetime
import mlflow
from mlflow.tracking import MlflowClient
from mlflow.entities import ViewType


@dag(schedule_interval='0 0 1 1,4,7,10 *', start_date=datetime(2023, 1, 1), catchup=False)
def quarterly_retrain():
    @task
    def transform_data(data_path, cat_features, num_features):
        import sys
        sys.path.append('/opt/airflow/modules/')
        from utils import read_and_clean_data, process_data, over_sample
        df = read_and_clean_data(data_path)
        X_train, X_val, y_train, y_val = process_data(df, cat_features, num_features, test_size=0.2)
        X_train, y_train = over_sample(X_train, y_train)

        data_path = f'gs://{data_bucket_name}'
        X_train.to_csv(f'{data_path}/X_train.csv', index=False)
        X_val.to_csv(f'{data_path}/X_val.csv', index=False)
        y_train.to_csv(f'{data_path}/y_train.csv', index=False)
        y_val.to_csv(f'{data_path}/y_val.csv', index=False)

    @task
    def run_models():
        import pandas as pd
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier
        from xgboost import XGBClassifier
        
        import sys
        sys.path.append('/opt/airflow/modules/')
        from ml_utils import run_model

        data_path = f'gs://{data_bucket_name}'
        X_train = pd.read_csv(f'{data_path}/X_train.csv')
        X_val = pd.read_csv(f'{data_path}/X_val.csv')
        y_train = pd.read_csv(f'{data_path}/y_train.csv')
        y_val = pd.read_csv(f'{data_path}/y_val.csv')

        run_model(LogisticRegression(), X_train, X_val, y_train, y_val)
        run_model(RandomForestClassifier(random_state = 42), X_train, X_val, y_train, y_val)
        run_model(XGBClassifier(), X_train, X_val, y_train, y_val)

    @task
    def optimize_and_register_best_classifier(client, experiment_name):
        import pandas as pd
        from hyperopt import fmin, tpe, Trials

        import sys
        sys.path.append('/opt/airflow/modules/')
        from ml_utils import find_best_classifier, hyperparameter_space, objective, register_best_model

        data_path = f'gs://{data_bucket_name}'
        X_train = pd.read_csv(f'{data_path}/X_train.csv')
        X_val = pd.read_csv(f'{data_path}/X_val.csv')
        y_train = pd.read_csv(f'{data_path}/y_train.csv')
        y_val = pd.read_csv(f'{data_path}/y_val.csv')

        model_type = find_best_classifier(client, experiment_name)
        search_space = hyperparameter_space(model_type)
        best_params = fmin(
            fn=lambda params: objective(params, model_type, X_train, X_val, y_train, y_val),
            space=search_space,
            algo=tpe.suggest,
            max_evals=50,
            trials=Trials()
        )
        register_best_model(client, experiment_name, model_type)

    load_dotenv()
    data_bucket_name = os.getenv('DATA_BUCKET_NAME')

    TRACKING_SERVER_HOST = 'mlflow' 
    TRACKING_URI = f'http://{TRACKING_SERVER_HOST}:5000'
    EXPERIMENT_NAME = 'churn_experiment'
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)
    client = MlflowClient(tracking_uri=TRACKING_URI)

    cat_features = ['gender', 'married', 'offer', 'phone_service', 'multiple_lines', 'internet_service', 
                'internet_type', 'online_security', 'online_backup', 'device_protection_plan',
                'premium_tech_support', 'streaming_tv', 'streaming_movies', 'streaming_music', 
                'unlimited_data', 'contract', 'paperless_billing', 'payment_method']

    num_features = ['age', 'number_of_dependents', 'tenure_in_months', 'number_of_referrals', 
                    'avg_monthly_long_distance_charges', 'avg_monthly_gb_download', 'monthly_charge', 
                    'total_charges', 'total_refunds', 'total_extra_data_charges', 
                    'total_long_distance_charges', 'total_revenue']
    
    # Define task dependencies
    data_path = f'gs://{data_bucket_name}/telecom_customer_churn.csv'
    transform_data(data_path, cat_features, num_features) >> run_models() >> optimize_and_register_best_classifier(client, EXPERIMENT_NAME)


dag_instance = quarterly_retrain()