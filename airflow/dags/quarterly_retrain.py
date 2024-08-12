from airflow.decorators import task, dag
from datetime import timedelta, datetime

import mlflow
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, roc_auc_score, average_precision_score

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from mlflow.tracking import MlflowClient
from mlflow.entities import ViewType

from hyperopt import fmin, tpe, hp, Trials, STATUS_OK

import sys
sys.path.append('/opt/airflow/modules/')
import utils

def run_model(model, X_train, X_val, y_train, y_val):
    with mlflow.start_run():
        mlflow.set_tag('developer','Braden')
        mlflow.set_tag('model_type', type(model).__name__)
        print(f'training {type(model).__name__}')
        model.fit(X_train, y_train)
        y_pred = model.predict(X_val)
        mlflow.sklearn.log_model(model, artifact_path='models')

        pr_auc = average_precision_score(y_val, model.predict_proba(X_val)[:, 1])
        roc_auc = roc_auc_score(y_val, model.predict_proba(X_val)[:, 1])
        f1 = f1_score(y_val, y_pred)
        mlflow.log_metric('pr_auc', pr_auc)
        mlflow.log_metric('roc_auc', roc_auc)
        mlflow.log_metric('f1_score', f1)

def find_best_classifier(client, experiment_name):
    best_run = client.search_runs(
        experiment_ids=client.get_experiment_by_name(experiment_name).experiment_id,
        run_view_type=ViewType.ACTIVE_ONLY,
        max_results=1,
        order_by=['metrics.pr_auc DESC']
    )[0]

    model_type = best_run.data.tags['model_type']

    return model_type

def hyperparameter_space(model_type):
    """Define hyperparameter space based on the model."""
    if model_type == 'RandomForestClassifier':
        return {
            'n_estimators': hp.choice('n_estimators', [50, 100, 200]),
            'max_depth': hp.choice('max_depth', [3, 5, 7, 10]),
            'min_samples_split': hp.uniform('min_samples_split', 0.1, 1.0),
            'min_samples_leaf': hp.uniform('min_samples_leaf', 0.1, 0.5)
        }
    elif model_type == 'LogisticRegression':
        return {
            'C': hp.loguniform('C', -4, 4),
            'solver': hp.choice('solver', ['newton-cg', 'lbfgs', 'liblinear']),
            'penalty': hp.choice('penalty', ['l1', 'l2', 'elasticnet', None])
            }
    elif model_type == 'XGBClassifier':
        return {
            'n_estimators': hp.choice('n_estimators', [50, 100, 200, 300]),
            'max_depth': hp.quniform('max_depth', 3, 10, 1),
            'learning_rate': hp.uniform('learning_rate', 0.01, 0.3),
            'gamma': hp.uniform('gamma', 0, 0.5),
            'min_child_weight': hp.quniform('min_child_weight', 1, 10, 1),
            'subsample': hp.uniform('subsample', 0.6, 1.0),
            'colsample_bytree': hp.uniform('colsample_bytree', 0.6, 1.0)
        }
    
def objective(params, model_type, X_train, X_val, y_train, y_val):
    with mlflow.start_run(nested=True):
        if model_type == 'LogisticRegression':
            model = LogisticRegression(**params)
        elif model_type == 'RandomForestClassifier':
            model = RandomForestClassifier(**params)
        elif model_type == 'XGBClassifier':
            params['max_depth'] = int(params['max_depth'])
            params['min_child_weight'] = int(params['min_child_weight'])
            model = XGBClassifier(**params)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_val)

        pr_auc = average_precision_score(y_val, model.predict_proba(X_val)[:, 1])
        roc_auc = roc_auc_score(y_val, model.predict_proba(X_val)[:, 1])
        f1 = f1_score(y_val, y_pred)

        # Log parameters and metrics
        mlflow.set_tag('developer','Braden')
        mlflow.set_tag('model_type', type(model).__name__)
        mlflow.log_params(params)
        mlflow.log_metric('pr_auc', pr_auc)
        mlflow.log_metric('roc_auc', roc_auc)
        mlflow.log_metric('f1_score', f1)
        # Log the model
        mlflow.sklearn.log_model(model, 'models')

            
        return {'loss': -pr_auc, 'status': STATUS_OK}
    
def register_best_model(client, experiment_name, model_type):
    best_run = client.search_runs(
        experiment_ids=client.get_experiment_by_name(experiment_name).experiment_id,
        run_view_type=ViewType.ACTIVE_ONLY,
        max_results=1,
        order_by=['metrics.pr_auc DESC']
    )[0]

    run_id = best_run.info.run_id

    mlflow.register_model(
        model_uri=f"runs:/{run_id}/models",
        name=model_type
    )


@dag(schedule_interval='0 0 1 1,4,7,10 *', start_date=datetime(2023, 1, 1), catchup=False)
def quarterly_retrain():
    @task
    def load_transform_data(data_path, cat_features, num_features):
        df = utils.read_and_clean_data(data_path)
        X_train, X_val, y_train, y_val = utils.process_data(df, cat_features, num_features, test_size=0.2)
        X_train, y_train = utils.over_sample(X_train, y_train)
        return {
            "X_train": X_train.to_dict(),
            "X_val": X_val.to_dict(),
            "y_train": y_train.to_dict(),
            "y_val": y_val.to_dict()
        }

    @task
    def run_models(data):
        X_train = pd.DataFrame.from_dict(data['X_train'])
        X_val = pd.DataFrame.from_dict(data['X_val'])
        y_train = pd.Series(data['y_train'])
        y_val = pd.Series(data['y_val'])
        
        run_model(LogisticRegression(), X_train, X_val, y_train, y_val)
        run_model(RandomForestClassifier(random_state = 42), X_train, X_val, y_train, y_val)
        run_model(XGBClassifier(), X_train, X_val, y_train, y_val)

    @task
    def optimize_and_register_best_classifier(client, experiment_name, data):
        X_train = pd.DataFrame.from_dict(data['X_train'])
        X_val = pd.DataFrame.from_dict(data['X_val'])
        y_train = pd.Series(data['y_train'])
        y_val = pd.Series(data['y_val'])
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
    data_path = f'gs://churn-data-bt/telecom_customer_churn.csv'
    data = load_transform_data(data_path, cat_features, num_features)
    models = run_models(data)
    models >> optimize_and_register_best_classifier(client, EXPERIMENT_NAME, data)


dag_instance = quarterly_retrain()