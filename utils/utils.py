import pandas as pd
import numpy as np
from imblearn.over_sampling import SMOTE
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split
import mlflow

def fill_missing_values(df):
    phone_only_cols = ['internet_type', 'online_security', 'online_backup', 'device_protection_plan', 
                   'premium_tech_support', 'streaming_tv', 'streaming_movies', 
                   'streaming_music', 'unlimited_data']
    
    df['offer'] = df['offer'].fillna('none')
    df[phone_only_cols] = df[phone_only_cols].fillna('No')
    df['avg_monthly_gb_download'] = df['avg_monthly_gb_download'].fillna(0)

    # internet only columns
    df['avg_monthly_long_distance_charges'] = df['avg_monthly_long_distance_charges'].fillna(0)
    df['multiple_lines'] = df['multiple_lines'].fillna('No')     

    return df           

def read_and_clean_data(file):
    df = pd.read_csv(file)
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    df = df[df['customer_status'].isin(['Stayed', 'Churned'])]
    df['customer_status'] = np.where(df['customer_status'] == 'Churned', 1, 0)

    df = fill_missing_values(df)

    return df               

def ohe_and_scale(df, cat_features, num_features):
    ohe = OneHotEncoder(sparse_output=False)
    df_encoded = ohe.fit_transform(df[cat_features])

    scl = StandardScaler()
    df_scaled = scl.fit_transform(df[num_features])

    # Combine transformed features
    df_processed = pd.concat([pd.DataFrame(df_scaled, columns=num_features), 
                                pd.DataFrame(df_encoded, columns=ohe.get_feature_names_out())], axis=1)
    df_processed.columns = df_processed.columns.str.lower().str.replace(' ', '_')

    return df_processed


def process_data(df, cat_features, num_features, test_size=0.2):
    X = df[cat_features + num_features]
    y = df['customer_status']

    # Split the data
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=test_size, random_state=42)
    X_val.to_csv('../data/telecom_customer_churn_val.csv', index=False)
    X_train_processed = ohe_and_scale(X_train, cat_features, num_features)
    X_val_processed = ohe_and_scale(X_val, cat_features, num_features)

    return X_train_processed, X_val_processed, y_train, y_val

def over_sample(X_train, y_train, random_state=42):
    smote = SMOTE(random_state=random_state)

    return smote.fit_resample(X_train, y_train)

def load_model(client, model_name, model_version):
    try:
        registered_models = client.search_model_versions(f"name='{model_name}'")
        for registered_model in registered_models:
            if registered_model.version == model_version:
                registered_model_uri = registered_model.source
        print(registered_model_uri)
        model = mlflow.pyfunc.load_model(registered_model_uri)
        print(f'{model_name} version {model_version} loaded')
        return model
    except:
        print('no registered model found')
