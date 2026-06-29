"""
routes/dataset_routes.py
FIXES:
  1. n_trials safe parse — no crash on empty/missing request body
  2. INVALID status does NOT permanently block training
  3. _read_file returns (df, final_path): multi-sheet Excel is merged,
     saved as flat _processed.csv, and THAT path is stored in Dataset.file_path
     so trainer.py always re-reads the correct flat file
  4. Column names normalised in all _read_file code paths
  5. /sync_clients endpoint to repopulate clients from completed datasets
"""
from __future__ import annotations
import os, re, uuid
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename

from extensions import db
from models import Dataset, MLModel
from security import current_user_id, current_company_id, manager_or_admin, admin_required
from services.audit_service import log_action
from services.preprocessing import validate_dataset as _validate

dataset_bp = Blueprint("datasets", __name__)


def _allowed(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", {"csv", "xlsx", "xls"})


def _norm_col(name: str) -> str:
    name = str(name).strip().upper()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^A-Z0-9_]", "", name)
    return name


# ── Upload ────────────────────────────────────────────────────────────────────

@dataset_bp.route("/upload", methods=["POST"])
@jwt_required()
@admin_required
def upload_dataset():
    cid = current_company_id()

    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni (champ 'file' requis)"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Nom de fichier vide"}), 400
    if not _allowed(file.filename):
        return jsonify({"error": "Format non supporté. Utilisez CSV ou Excel (.xlsx/.xls)"}), 400

    safe_name   = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    upload_dir  = Path(current_app.config["UPLOAD_FOLDER"]) / str(cid)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / unique_name
    file.save(str(file_path))
    file_size = file_path.stat().st_size

    # FIX 3: _read_file returns (df, final_path)
    # final_path = processed flat CSV for multi-sheet Excel, original path otherwise
    try:
        df, final_path = _read_file(str(file_path))
    except Exception as e:
        return jsonify({"error": f"Impossible de lire le fichier : {e}"}), 422

    validation = _validate(df, require_target=True)

    dataset = Dataset(
        company_id=cid,
        uploaded_by=current_user_id(),
        filename=safe_name,
        file_path=final_path,          # ← always the flat, normalised file
        file_size=file_size,
        nb_rows=len(df),
        nb_cols=len(df.columns),
        status="UPLOADED" if validation.is_valid else "INVALID",
        validation_report=validation.to_dict(),
    )
    db.session.add(dataset)
    db.session.commit()

    log_action(cid, current_user_id(), "UPLOAD_DATASET", "dataset", str(dataset.id),
               {"filename": safe_name, "rows": len(df)})

    return jsonify({"dataset": dataset.to_dict(), "validation": validation.to_dict()}), 201


# ── Train ─────────────────────────────────────────────────────────────────────

@dataset_bp.route("/<int:dataset_id>/train", methods=["POST"])
@jwt_required()
@admin_required
def start_training(dataset_id: int):
    dataset = _get_or_404(dataset_id)

    if dataset.status == "PROCESSING":
        return jsonify({"error": "Entraînement déjà en cours"}), 409

    # FIX 1: safe parse — never crashes on empty body
    body     = request.get_json(force=True, silent=True) or {}
    n_trials = int(body.get("n_trials", 20))

    # FIX 2: INVALID no longer hard-blocks — pipeline validates internally

    # In the student/dev setup there is usually no Redis/Celery worker.
    # Trying Celery first can make the HTTP request hang and the frontend shows
    # only "Impossible de démarrer".  Therefore local background training is the
    # default; set USE_CELERY=true only when Redis + worker are really running.
    use_celery = str(os.getenv("USE_CELERY", "false")).lower() in {"1", "true", "yes"}

    if use_celery:
        try:
            from celery_app import train_model_task
            task = train_model_task.delay(
                dataset_id=dataset.id,
                company_id=current_company_id(),
                file_path=dataset.resolved_file_path,
                n_trials=n_trials,
            )
            dataset.status            = "PROCESSING"
            dataset.celery_task_id    = task.id
            dataset.training_progress = 0
            dataset.error_message     = None
            db.session.commit()
            log_action(current_company_id(), current_user_id(), "START_TRAINING",
                       "dataset", str(dataset_id), {"task_id": task.id})
            return jsonify({"message": "Entraînement démarré", "task_id": task.id,
                            "dataset": dataset.to_dict()})
        except Exception as celery_err:
            current_app.logger.warning(f"Celery unavailable, fallback local thread: {celery_err}")

    app = current_app._get_current_object()
    import threading

    def _run_async():
        with app.app_context():
            try:
                from extensions import db as _db
                from models import Dataset as _D
                td = _db.session.get(_D, dataset_id)
                if td:
                    _run_training_sync(td, n_trials)
            except Exception as ex:
                app.logger.error(f"Training thread error: {ex}", exc_info=True)

    dataset.status            = "PROCESSING"
    dataset.training_progress = 0
    dataset.training_step     = "Démarrage"
    dataset.error_message     = None
    db.session.commit()
    threading.Thread(target=_run_async, daemon=True).start()
    log_action(current_company_id(), current_user_id(), "START_TRAINING_LOCAL",
               "dataset", str(dataset_id))
    return jsonify({"message": "Entraînement démarré en arrière-plan",
                    "dataset": dataset.to_dict()})


# ── Sync clients from completed dataset ──────────────────────────────────────

@dataset_bp.route("/<int:dataset_id>/sync_clients", methods=["POST"])
@jwt_required()
@admin_required
def sync_clients(dataset_id: int):
    """Repopulate Client records from a completed dataset without re-training."""
    dataset = _get_or_404(dataset_id)
    active_model = MLModel.query.filter_by(
        company_id=dataset.company_id, is_active=True).first()
    if not active_model:
        return jsonify({"error": "Aucun modèle actif."}), 409
    try:
        df, _ = _read_file(dataset.resolved_file_path)
    except Exception as e:
        return jsonify({"error": f"Lecture fichier: {e}"}), 422
    try:
        from services.trainer import _sync_clients_from_dataset
        _sync_clients_from_dataset(df, active_model, dataset.company_id)
        try:
            from extensions import cache
            cache.clear()
        except Exception:
            pass
        return jsonify({"message": f"Clients synchronisés ({len(df)} lignes)"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Status / List / Get / Delete ──────────────────────────────────────────────

@dataset_bp.route("/<int:dataset_id>/status", methods=["GET"])
@jwt_required()
@admin_required
def training_status(dataset_id: int):
    dataset = _get_or_404(dataset_id)
    result  = {"dataset": dataset.to_dict()}
    if dataset.celery_task_id:
        try:
            from celery_app import celery
            task = celery.AsyncResult(dataset.celery_task_id)
            result["task"] = {"id": task.id, "state": task.state,
                              "info": task.info if isinstance(task.info, dict) else {}}
        except Exception:
            pass
    return jsonify(result)


@dataset_bp.route("", methods=["GET"])
@jwt_required()
@admin_required
def list_datasets():
    cid = current_company_id()
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)
    pag = (Dataset.query.filter_by(company_id=cid)
           .order_by(Dataset.created_at.desc())
           .paginate(page=page, per_page=per_page, error_out=False))
    return jsonify({"datasets": [d.to_dict() for d in pag.items],
                    "total": pag.total, "pages": pag.pages, "page": page})


@dataset_bp.route("/<int:dataset_id>", methods=["GET"])
@jwt_required()
@admin_required
def get_dataset(dataset_id: int):
    dataset = _get_or_404(dataset_id)
    models  = MLModel.query.filter_by(dataset_id=dataset_id).order_by(MLModel.created_at.desc()).all()
    return jsonify({"dataset": dataset.to_dict(), "models": [m.to_dict() for m in models]})


@dataset_bp.route("/<int:dataset_id>", methods=["DELETE"])
@jwt_required()
@admin_required
def delete_dataset(dataset_id: int):
    dataset = _get_or_404(dataset_id)
    if dataset.status == "PROCESSING":
        return jsonify({"error": "Impossible de supprimer un dataset en cours d'entraînement"}), 409
    try:
        p = dataset.resolved_file_path
        if p and os.path.exists(p):
            os.remove(p)
    except Exception:
        pass
    db.session.delete(dataset)
    db.session.commit()
    log_action(current_company_id(), current_user_id(), "DELETE_DATASET", "dataset", str(dataset_id))
    return jsonify({"message": "Dataset supprimé"})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(dataset_id: int) -> Dataset:
    return Dataset.query.filter_by(
        id=dataset_id, company_id=current_company_id()
    ).first_or_404()


def _read_file(path: str) -> tuple[pd.DataFrame, str]:
    """
    Read a CSV or Excel file into a normalised DataFrame.
    Returns (df, final_path) where:
      - CSV / single-sheet Excel: columns normalised, original path returned
      - Multi-sheet Excel: sheets merged, CIBLE computed, saved as
        _processed.csv next to original, that CSV path returned

    CRITICAL: upload_dataset stores final_path in Dataset.file_path so
    trainer.py always re-reads the right flat file, not the raw Excel.
    """
    # ── CSV ───────────────────────────────────────────────────────────────
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
        df.columns = [_norm_col(c) for c in df.columns]
        return df, path

    # ── Excel: single sheet ───────────────────────────────────────────────
    xls = pd.ExcelFile(path)
    sheets = xls.sheet_names
    if len(sheets) < 2:
        df = pd.read_excel(path, sheet_name=sheets[0])
        df.columns = [_norm_col(c) for c in df.columns]
        return df, path

    # ── Excel: multi-sheet (raw factures + règlements) ────────────────────
    df_f = pd.read_excel(path, sheet_name=sheets[0])
    df_r = pd.read_excel(path, sheet_name=sheets[1])
    df_f.columns = df_f.columns.str.strip().str.upper()
    df_r.columns = df_r.columns.str.strip().str.upper()

    def fc(cols, patterns):
        for c in cols:
            n = str(c).strip().upper().replace("_", " ").replace("  ", " ")
            if any(p in n for p in patterns):
                return c
        return None

    cc_f = fc(df_f.columns, ["CODE CLIENT", "CODE_CLIENT", "CLIENT CODE", "CLIENT"])
    cc_r = fc(df_r.columns, ["CODE CLIENT", "CODE_CLIENT", "CLIENT CODE", "CLIENT"])
    if not cc_f or not cc_r:
        df = pd.read_excel(path, sheet_name=sheets[0])
        df.columns = [_norm_col(c) for c in df.columns]
        return df, path

    df_f = df_f.rename(columns={cc_f: "CODE CLIENT"})
    df_r = df_r.rename(columns={cc_r: "CODE CLIENT"})

    def rc(df, patterns, new):
        c = fc(df.columns, patterns)
        return df.rename(columns={c: new}) if c else df

    df_f = rc(df_f, ["MONTANT TTC", "MONTANT_TTC", "TOTAL TTC", "MONTANT", "TTC"], "MONTANT_TTC")
    df_f = rc(df_f, ["NATURE CLIENT", "NATURE_CLIENT", "NATURE"],                  "NATURE CLIENT")
    df_f = rc(df_f, ["GOUVERNORAT", "REGION", "VILLE", "GOV"],                     "GOUVERNORAT")
    df_f = rc(df_f, ["DATE FACTURE", "DATE_FACTURE", "DATE"],                       "DATE_FACTURE")
    df_r = rc(df_r, ["MONTANT REG", "MONTANT_REG", "MONTANT REGLEMENT", "REGLEMENT", "PAIEMENT"], "MONTANT REG")
    df_r = rc(df_r, ["DATE REG", "DATE_REG", "DATE PAIEMENT", "DATE_PAIEMENT", "DATE"],           "DATE")
    df_r = rc(df_r, ["DATE ECHEANCE", "DATE_ECHEANCE", "ECHEANCE"],                               "DATE ECHEANCE")
    df_r = rc(df_r, ["MODE", "TYPE", "PAIEMENT"],                                                 "MODE")

    if not all(c in df_f.columns for c in ["MONTANT_TTC", "DATE_FACTURE"]) or \
       not all(c in df_r.columns for c in ["MONTANT REG", "DATE", "DATE ECHEANCE"]):
        df = pd.read_excel(path, sheet_name=sheets[0])
        df.columns = [_norm_col(c) for c in df.columns]
        return df, path

    df_f["DATE_FACTURE"]   = pd.to_datetime(df_f["DATE_FACTURE"],   errors="coerce")
    df_r["DATE"]           = pd.to_datetime(df_r["DATE"],           errors="coerce")
    df_r["DATE ECHEANCE"]  = pd.to_datetime(df_r["DATE ECHEANCE"],  errors="coerce")
    df_r["RETARD_JOURS"]   = (df_r["DATE"] - df_r["DATE ECHEANCE"]).dt.days
    ref = df_f["DATE_FACTURE"].max()

    def fp(d):
        d = pd.to_datetime(d, errors="coerce").dropna().unique()
        if len(d) < 2: return 0.0
        return float(np.diff(np.sort(d)).astype("timedelta64[D]").astype(float).mean())

    def anc(d):
        d = pd.to_datetime(d, errors="coerce").dropna()
        return float((d.max() - d.min()).days) if len(d) else 0.0

    def jd(d):
        d = pd.to_datetime(d, errors="coerce").dropna()
        return float((ref - d.max()).days) if len(d) else 9999.0

    inv = (df_f.groupby("CODE CLIENT").agg(
        TOTAL_MONTANT_TTC          =("MONTANT_TTC",   "sum"),
        NB_FACTURES                =("MONTANT_TTC",   "count"),
        MONTANT_MOY_FACTURE        =("MONTANT_TTC",   "mean"),
        MONTANT_MAX_FACTURE        =("MONTANT_TTC",   "max"),
        NATURE_CLIENT              =("NATURE CLIENT", "first"),
        GOUVERNORAT                =("GOUVERNORAT",   "first"),
        FREQUENCE_ACHAT            =("DATE_FACTURE",  fp),
        ANCIENNETE_CLIENT          =("DATE_FACTURE",  anc),
        JOURS_DEPUIS_DERNIER_ACHAT =("DATE_FACTURE",  jd),
    ).reset_index())

    pay = (df_r.groupby("CODE CLIENT").agg(
        TOTAL_MONTANT_REG =("MONTANT REG",  "sum"),
        NB_REGLEMENTS     =("MONTANT REG",  "count"),
        MONTANT_MOY_REG   =("MONTANT REG",  "mean"),
        RETARD_MOYEN      =("RETARD_JOURS", "mean"),
        RETARD_MAX        =("RETARD_JOURS", "max"),
        NB_RETARDS        =("RETARD_JOURS", lambda x: (x > 0).sum()),
        NB_MODES_PAIEMENT =("MODE",         "nunique"),
        RETARD_STD        =("RETARD_JOURS", lambda x: x.std(ddof=0) if len(x) > 1 else 0.0),
    ).reset_index())

    df_r["_WR"] = df_r["RETARD_JOURS"] * df_r["MONTANT REG"]
    wp = (df_r.groupby("CODE CLIENT")
          .apply(lambda g: g["_WR"].sum() / g["MONTANT REG"].sum()
                 if g["MONTANT REG"].sum() != 0 else 0.0)
          .reset_index().rename(columns={0: "RETARD_PONDERE"}))
    pay = pay.merge(wp, on="CODE CLIENT", how="left")
    pay["RETARD_PONDERE"] = pay["RETARD_PONDERE"].fillna(0.0)
    pay["TAUX_RETARD"] = np.where(
        pay["NB_REGLEMENTS"] > 0,
        (pay["NB_RETARDS"] / pay["NB_REGLEMENTS"] * 100).round(2), 0.0)

    m = pd.merge(inv, pay, on="CODE CLIENT", how="outer")
    nc = m.select_dtypes(include=[np.number]).columns
    m[nc] = m[nc].fillna(0)
    for col in ["NATURE_CLIENT", "GOUVERNORAT"]:
        if col in m.columns:
            m[col] = m[col].fillna("INCONNU")

    m["RATIO_PAIEMENT"] = np.where(m["TOTAL_MONTANT_TTC"] > 0,
        (m["TOTAL_MONTANT_REG"] / m["TOTAL_MONTANT_TTC"]).round(4), 0.0)
    tca = m["TOTAL_MONTANT_TTC"].sum()
    m["PART_CA_CLIENT"] = np.where(tca > 0,
        (m["TOTAL_MONTANT_TTC"] / tca).round(6), 0.0)

    # Règle de création de la variable cible conforme au rapport PFE
    # et au fichier ML fourni : SOLVABLE/CIBLE = 1 si le client respecte
    # les critères de retard moyen, retard maximal et taux de retard.
    m["CIBLE"] = (
        (m["RETARD_MOYEN"] <= 0) &
        (m["RETARD_MAX"]   <= 30) &
        (m["TAUX_RETARD"]  <  20)
    ).astype(int)

    # Drop leakage columns before saving
    m.drop(columns=["RETARD_MOYEN", "RETARD_MAX", "TAUX_RETARD"], errors="ignore", inplace=True)
    m = m.rename(columns={"CODE CLIENT": "CODE_CLIENT"})
    m.columns = [_norm_col(c) for c in m.columns]

    # FIX 3: save as flat CSV and return NEW path
    # upload_dataset will store this path in Dataset.file_path
    flat_path = path.rsplit(".", 1)[0] + "_processed.csv"
    m.to_csv(flat_path, index=False, encoding="utf-8-sig")
    return m, flat_path


def _run_training_sync(dataset: Dataset, n_trials: int) -> None:
    from services.trainer import TrainingService

    def progress_cb(step: str, pct: int):
        dataset.training_progress = pct
        dataset.training_step     = step
        db.session.commit()

    dataset.status = "PROCESSING"
    db.session.commit()
    try:
        report = TrainingService.run(
            dataset=dataset,
            file_path=dataset.resolved_file_path,
            company_id=dataset.company_id,
            n_trials=n_trials,
            progress_callback=progress_cb,
        )
        dataset.status        = "COMPLETED" if report["success"] else "FAILED"
        dataset.error_message = report.get("error") if not report["success"] else None
    except Exception as e:
        dataset.status        = "FAILED"
        dataset.error_message = str(e)
        current_app.logger.error(f"Training failed for dataset {dataset.id}: {e}", exc_info=True)
    finally:
        dataset.training_progress = 100
        db.session.commit()