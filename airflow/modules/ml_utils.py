
import mlflow
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, roc_auc_score, average_precision_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

from mlflow.entities import ViewType
from hyperopt import hp, STATUS_OK

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