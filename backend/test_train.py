import os
import sys

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db
from models import Dataset

def test():
    app = create_app()
    with app.app_context():
        print("Flask app context pushed successfully.")
        
        # 1. Check database connection and get dataset
        dataset = Dataset.query.order_by(Dataset.id.desc()).first()
        if not dataset:
            print("ERROR: No datasets found in the database. Please upload a dataset first.")
            return
            
        print(f"Found dataset: ID={dataset.id}, Filename={dataset.filename}, Status={dataset.status}, File Path={dataset.file_path}")
        
        # 2. Try importing celery_app
        print("\nTesting Celery import...")
        try:
            from celery_app import train_model_task
            print("SUCCESS: celery_app and train_model_task imported successfully.")
        except Exception as e:
            print(f"NOTICE: Celery import failed (normal if not installed): {e}")
            
        # 3. Try importing ML trainer and pipeline
        print("\nTesting ML trainer and pipeline imports...")
        try:
            from services.trainer import TrainingService
            from services.ml_pipeline import run_training_pipeline
            print("SUCCESS: ML trainer and pipeline services imported successfully.")
        except Exception as e:
            print(f"ERROR: ML pipeline imports failed: {e}")
            import traceback
            traceback.print_exc()
            return
            
        # 4. Try running a dry run of the training fallback (1 trial for speed)
        print("\nTesting synchronous training fallback...")
        try:
            print(f"Running fallback training on dataset {dataset.id} with 1 trial...")
            from routes.dataset_routes import _run_training_sync
            _run_training_sync(dataset, n_trials=1)
            print(f"SUCCESS: Fallback training completed. New status: {dataset.status}, Error: {dataset.error_message}")
        except Exception as e:
            print(f"ERROR: Training fallback failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test()
