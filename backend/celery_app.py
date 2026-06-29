"""
celery_app.py
Celery worker initialisation and async task definitions.
"""
from __future__ import annotations

import os
from celery import Celery
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def make_celery(app=None) -> Celery:
    """Create and configure the Celery instance."""
    broker  = os.getenv("CELERY_BROKER_URL",  "redis://localhost:6379/0")
    backend = os.getenv("CELERY_RESULT_BACKEND", broker)

    celery = Celery(
        "solvai",
        broker=broker,
        backend=backend,
        include=["celery_app"],
    )
    celery.conf.update(
        task_serializer          = "json",
        result_serializer        = "json",
        accept_content           = ["json"],
        timezone                 = "Africa/Tunis",
        enable_utc               = True,
        task_track_started       = True,
        task_acks_late           = True,
        worker_prefetch_multiplier = 1,
        result_expires           = 86400,   # 24h
        task_soft_time_limit     = 3600,
        task_time_limit          = 3900,
    )

    if app is not None:
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        celery.Task = ContextTask

    return celery


# Standalone Celery instance (used when running `celery -A celery_app worker`)
celery = make_celery()


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery.task(bind=True, name="tasks.train_model")
def train_model_task(
    self,
    dataset_id: int,
    company_id: int,
    file_path: str,
    n_trials: int = 20,
):
    """
    Background task: run full ML training pipeline for an uploaded dataset.
    Updates Dataset and MLModel records throughout.
    """
    from app import create_app
    app = create_app()

    with app.app_context():
        from extensions import db
        from models import Dataset, MLModel
        from services.trainer import TrainingService

        dataset = Dataset.query.get(dataset_id)
        if not dataset:
            logger.error(f"Dataset {dataset_id} not found")
            return {"error": "Dataset not found"}

        dataset.status = "PROCESSING"
        db.session.commit()

        def progress_cb(step: str, pct: int):
            self.update_state(
                state="PROGRESS",
                meta={"step": step, "percent": pct, "dataset_id": dataset_id},
            )
            dataset.training_progress = pct
            dataset.training_step     = step
            db.session.commit()

        try:
            report = TrainingService.run(
                dataset=dataset,
                file_path=file_path,
                company_id=company_id,
                n_trials=n_trials,
                progress_callback=progress_cb,
            )

            if report["success"]:
                dataset.status = "COMPLETED"
                logger.info(f"Training completed for dataset {dataset_id}")
            else:
                dataset.status   = "FAILED"
                dataset.error_message = report.get("error", "Unknown error")
                logger.error(f"Training failed: {report.get('error')}")

            db.session.commit()
            return report

        except Exception as exc:
            logger.exception(f"train_model_task crashed: {exc}")
            dataset.status        = "FAILED"
            dataset.error_message = str(exc)
            db.session.commit()
            self.update_state(state="FAILURE", meta={"error": str(exc)})
            raise


@celery.task(name="tasks.compute_alerts")
def compute_alerts_task(company_id: int):
    """Periodic task: re-evaluate alerts for all clients of a company."""
    from app import create_app
    app = create_app()
    with app.app_context():
        from services.client_service import ClientService
        from models import Client
        from extensions import db
        from services.prediction_service import PredictionService

        if not PredictionService.is_model_ready():
            logger.warning("No active model — skipping alerts compute")
            return

        clients = Client.query.filter_by(company_id=company_id, statut="ACTIF").all()
        for client in clients:
            try:
                # Re-score using stored features if available
                if client.last_features:
                    result = PredictionService.predict(client.last_features)
                    ClientService.update_from_prediction(client, result)
                    ClientService.check_and_create_alerts(client, result)
            except Exception as e:
                logger.warning(f"Alert compute failed for client {client.id}: {e}")
        db.session.commit()
        logger.info(f"Alerts computed for company {company_id} — {len(clients)} clients")


@celery.task(name="tasks.cleanup_exports")
def cleanup_exports_task():
    """Periodic task: remove export files older than 24h."""
    import os, time
    export_dir = os.getenv("EXPORT_FOLDER", "exports")
    cutoff = time.time() - 86400
    removed = 0
    for fname in os.listdir(export_dir):
        fpath = os.path.join(export_dir, fname)
        if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
            os.remove(fpath)
            removed += 1
    logger.info(f"Cleaned {removed} expired export files")
    return {"removed": removed}


# ── Celery Beat schedule ──────────────────────────────────────────────────────

celery.conf.beat_schedule = {
    "cleanup-exports-daily": {
        "task": "tasks.cleanup_exports",
        "schedule": 86400,   # every 24h
    },
}
