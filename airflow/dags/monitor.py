from airflow.decorators import task, dag
from airflow.sensors.external_task import ExternalTaskSensor
import os
from dotenv import load_dotenv
import sys

from datetime import datetime

@dag(schedule_interval='@monthly', start_date=datetime(2023, 3, 2), catchup=True)
def monthly_monitor():
    
    wait_for_data = ExternalTaskSensor(
        task_id='wait_for_data',
        external_dag_id='monthly_prediction',  
        external_task_id='predict_and_save',  
        allowed_states=['success'],
        failed_states=['failed', 'skipped'],
        mode='poke', 
        timeout=600
    )

    def connect_to_db(conn_params):
        import psycopg2
        import sys
        try:
            rs_conn = psycopg2.connect(**conn_params)
            return rs_conn
        except Exception as e:
            print(f"Unable to connect to database. error {e}")
            sys.exit(1)

    @task
    def create_db(conn_params, db_name):
        conn = connect_to_db(conn_params)
        with conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
            if len(cur.fetchall()) == 0:
                print(f'creating database {db_name}')
                cur.execute(f'CREATE DATABASE {db_name};')
            else:
                print(f'{db_name} database already created')
        conn.commit()
    
    @task
    def create_table(conn_params, table_name):
        conn = connect_to_db(conn_params)
        
        create_table_statement = f"""
        create table {table_name}(
            timestamp timestamp,
            prediction_drift float,
            num_drifted_columns integer,
            share_of_drifted_columns float
        )
        """
        try:
            with conn.cursor() as cur:
                cur.execute(create_table_statement)
                print(f'table {table_name} created')
            conn.commit()
        except:
            print(f'table {table_name} already exists')

    @task 
    def prep_data(**kwargs):
        import pandas as pd
        from datetime import timedelta

        from evidently import ColumnMapping
        from evidently.report import Report
        from evidently.metrics import ColumnDriftMetric
        from evidently.metric_preset import DataDriftPreset


        month_end = (kwargs['logical_date'].replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        previous_month = (pd.to_datetime(month_end) + pd.offsets.MonthEnd(-1)).strftime("%Y-%m-%d")

        ref_path = f'gs://{scoring_bucket_name}/predictions_{previous_month}.csv'
        curr_path = f'gs://{scoring_bucket_name}/predictions_{month_end}.csv'
        
        ref_df = pd.read_csv(ref_path)
        curr_df = pd.read_csv(curr_path)

        cat_features = ['gender', 'married', 'offer', 'phone_service', 'multiple_lines', 'internet_service', 
                        'internet_type', 'online_security', 'online_backup', 'device_protection_plan',
                        'premium_tech_support', 'streaming_tv', 'streaming_movies', 'streaming_music', 
                        'unlimited_data', 'contract', 'paperless_billing', 'payment_method']

        num_features = ['age', 'number_of_dependents', 'tenure_in_months', 'number_of_referrals', 
                        'avg_monthly_long_distance_charges', 'avg_monthly_gb_download', 'monthly_charge', 
                        'total_charges', 'total_refunds', 'total_extra_data_charges', 
                        'total_long_distance_charges', 'total_revenue']
        
        column_mapping = ColumnMapping(
            prediction='prediction',
            numerical_features=num_features,
            categorical_features=cat_features,
            target=None
        )

        report = Report(metrics=[
            ColumnDriftMetric(column_name='prediction'),
            DataDriftPreset()
        ]
        )
        report.run(reference_data = ref_df, current_data = curr_df,
        column_mapping=column_mapping)

        result = report.as_dict()
        
        prediction_drift = result['metrics'][0]['result']['drift_score']
        num_drifted_col = result['metrics'][1]['result']['number_of_drifted_columns'] 
        share_of_drifted_cols = result['metrics'][1]['result']['share_of_drifted_columns'] 

        data = (month_end, prediction_drift, num_drifted_col, share_of_drifted_cols)

        return data
    
    @task
    def insert_data(conn_params, table_name, data):
        conn = connect_to_db(conn_params)

        check_statement = f"""
        SELECT 1 FROM {table_name} WHERE timestamp = %s
        """

        insert_statement = f"""
        insert into {table_name}(
            timestamp,
            prediction_drift,
            num_drifted_columns,
            share_of_drifted_columns
        )
        VALUES (%s, %s, %s, %s)
        """
        with conn.cursor() as cur:
            cur.execute(check_statement, (data[0],))
            if cur.fetchone():
                print(f'Data for {data[0]} already exists. Skipping insertion.')
            else:
                cur.execute(insert_statement, data)
                print(f'inserted data for {data[0]}')
        conn.commit()
                

    load_dotenv()
    scoring_bucket_name = os.getenv('SCORING_BUCKET_NAME')
    db_host = os.getenv('DB_HOST')
    db_username = os.getenv('DB_USERNAME')
    db_password = os.getenv('DB_PASSWORD')
    db_name = os.getenv('GRAFANA_DB_NAME')

    conn_params = {'host': db_host,
                   'port': '5432',
                   'user': db_username,
                   'password': db_password,
                   'dbname': db_name}  

    table_name = 'monitor_metrics'
    
    wait_for_data
    create_db(conn_params, db_name)
    create_table(conn_params, table_name)
    data = prep_data()
    insert_data(conn_params, table_name, data)


dag_instance = monthly_monitor()