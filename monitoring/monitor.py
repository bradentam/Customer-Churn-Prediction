import pandas as pd
import io
import psycopg2
from datetime import datetime

from evidently.report import Report
from evidently import ColumnMapping
from evidently.metric_preset import DataDriftPreset

from evidently.test_suite import TestSuite
from evidently.test_preset import DataDriftTestPreset
from evidently.metrics import ColumnDriftMetric, DatasetDriftMetric, DatasetMissingValuesMetric

def create_db(conn_params, db_name):
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
        if len(cur.fetchall()) == 0:
            print(f'creating database {db_name}')
            cur.execute(f'CREATE DATABASE {db_name};')
        else:
            print(f'{db_name} database already created')
    conn_params['dbname'] = db_name


def create_table(conn_params, table_name):
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = True  
    
    create_table_statement = f"""
    create table {table_name}(
        timestamp timestamp,
        prediction_drift float,
        num_drifted_columns integer,
        share_missing_values float
    )
    """
    try:
        with conn.cursor() as cur:
            cur.execute(create_table_statement)
            print(f'table {table_name} created')
    except:
        print(f'table {table_name} already exists')
		

def insert_data(conn_params, table_name, data):
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = True 

    check_statement = f"""
    SELECT 1 FROM {table_name} WHERE timestamp = %s
    """

    insert_statement = f"""
    insert into {table_name}(
        timestamp,
        prediction_drift,
        num_drifted_columns
    )
    VALUES (%s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.execute(check_statement, (data[0],))
        if cur.fetchone():
            print(f'Data for {data[0]} already exists. Skipping insertion.')
        else:
            cur.execute(insert_statement, data)
            print(f'inserted data for {data[0]}')

def main():

    conn_params = {'host': 'localhost',
                   'port': '5432',
                   'user': 'postgres',
                   'password': 'admin'}  
    
    db_name = 'churn'
    table_name = 'monitor_metrics'

    create_db(conn_params, db_name)
    create_table(conn_params, table_name)

    month_end = (datetime.now() + pd.offsets.MonthEnd(0)).date()
    previous_month = (datetime.now() + pd.offsets.MonthEnd(-1)).date()

    ref_path = f'gs://scoring-bradentam/output/reference_df_{previous_month}.csv'
    curr_path = f'gs://scoring-bradentam/output/reference_df_{month_end}.csv'

    # ref_df = pd.read_csv('../data/scored_reference_df.csv')
    # curr_df = pd.read_csv('../data/scored_current_df.csv')
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
        DataDriftPreset(),
        DatasetDriftMetric(),
        DatasetMissingValuesMetric(),
    ]
    )
    report.run(reference_data = ref_df, current_data = curr_df,
    column_mapping=column_mapping)

    result = report.as_dict()
    
    prediction_drift = result['metrics'][0]['result']['drift_score']
    num_drifted_columns = result['metrics'][1]['result']['number_of_drifted_columns'] 

    data = (month_end, prediction_drift, num_drifted_columns)

    insert_data(conn_params, table_name, data)

if __name__ == '__main__':
	main()