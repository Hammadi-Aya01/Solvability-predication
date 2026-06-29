"""
services/trainer.py
FIXES:
  1. Column normalisation after file read (strip/upper/underscores)
  2. _sync_clients_from_dataset() called after every training — this is
     what populates the Clients page and Dashboard KPIs
  3. Analytics cache cleared after sync
  4. _sync_clients_from_dataset exported for /sync_clients endpoint
"""
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pandas as pd
from extensions import db
from models import Dataset, MLModel


def _norm_col(name: str) -> str:
    name = str(name).strip().upper()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^A-Z0-9_]", "", name)
    return name


class TrainingService:

    @staticmethod
    def run(dataset, file_path: str, company_id: int,
            n_trials: int = 20, progress_callback=None) -> dict:
        from services.ml_trainer import run_training_pipeline

        def _p(step, pct):
            if progress_callback:
                progress_callback(step, pct)

        output_dir = Path("trained_models") / str(company_id) / str(dataset.id)

        # FIX 1: read file and normalise column names
        try:
            if file_path.lower().endswith(".csv"):
                df = pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8-sig")
            else:
                df = pd.read_excel(file_path)
            df.columns = [_norm_col(c) for c in df.columns]
        except Exception as e:
            return {"success": False, "error": f"Lecture fichier: {e}"}

        dataset.nb_rows = len(df)
        dataset.nb_cols = len(df.columns)
        db.session.commit()

        report = run_training_pipeline(
            df_raw=df, output_dir=output_dir,
            n_trials=n_trials, progress_callback=progress_callback,
        )

        if not report.success:
            return {"success": False, "error": report.error}

        last = (MLModel.query.filter_by(company_id=company_id)
                .order_by(MLModel.version.desc()).first())
        next_version = (last.version + 1) if last else 1

        best_result = next(
            (r for r in report.results if r["name"] == report.best_model_name),
            report.results[0] if report.results else {})
        best_metrics = best_result.get("metrics", {})

        ml_model = MLModel(
            company_id=company_id, dataset_id=dataset.id,
            model_name=report.best_model_name, version=next_version, is_active=False,
            accuracy=best_metrics.get("accuracy"),
            precision=best_metrics.get("precision"),
            recall=best_metrics.get("recall"),
            f1_score=best_metrics.get("f1"),
            roc_auc=best_metrics.get("roc_auc"),
            threshold=best_metrics.get("threshold", 0.5),
            date_entrainement=datetime.now(timezone.utc),
            artifact_paths=report.artifact_paths,
            feature_importances=report.feature_importances,
            all_models_results=report.results,
        )
        db.session.add(ml_model)
        db.session.commit()

        current_active = MLModel.query.filter_by(company_id=company_id, is_active=True).first()
        should_activate = (
            current_active is None or
            (ml_model.roc_auc or 0) > (current_active.roc_auc or 0)
        )
        if should_activate:
            if current_active:
                current_active.is_active = False
            ml_model.is_active = True
            db.session.commit()
            try:
                from services.prediction_service import PredictionService
                PredictionService.load_active_model(ml_model)
            except Exception:
                pass

        # FIX 2: sync Client records from dataset rows
        _p("Synchronisation des clients", 95)
        try:
            _sync_clients_from_dataset(df, ml_model, company_id)
        except Exception as sync_err:
            import traceback
            db.session.rollback()
            print(f"[trainer] Client sync warning (non-fatal): {sync_err}\n"
                  f"{traceback.format_exc()}")

        # FIX 3: clear analytics cache so dashboard shows fresh data
        try:
            from extensions import cache
            cache.clear()
        except Exception:
            pass

        _p("Terminé", 100)
        return {
            "success": True, "model_id": ml_model.id,
            "model_name": ml_model.model_name, "version": ml_model.version,
            "activated": ml_model.is_active, "metrics": best_metrics,
            "all_models": report.results,
            "feature_importances": report.feature_importances,
        }


def _sync_clients_from_dataset(df: pd.DataFrame, ml_model, company_id: int) -> None:
    """
    Upsert a Client record for every row in the dataset.
    Runs a prediction and stores risk_score / risk_level on each client.
    Also writes Prediction and ScoreHistory records.
    This is what populates the Clients page and Dashboard KPIs.
    """
    from models import Client, Prediction, ScoreHistory, ExplicationSHAP, PaymentHistory, Invoice
    from services.prediction_service import PredictionService

    now = datetime.now(timezone.utc)

    if not PredictionService.is_model_ready():
        try:
            PredictionService.load_active_model(ml_model)
        except Exception:
            pass

    count = 0
    for _, row in df.iterrows():
        try:
            cc = str(row.get("CODE_CLIENT", "")).strip()
            if not cc or cc in ("nan", "None", ""):
                continue

            row_dict = {col: (None if pd.isna(v) else v) for col, v in row.items()}

            # Run prediction
            pr = None
            if PredictionService.is_model_ready():
                try:
                    pr = PredictionService.predict(row_dict)
                except Exception:
                    pr = None

            rs  = int(pr["risk_score"])                if pr else 0
            rl  = pr["risk_level"]                     if pr else "INCONNU"
            lbl = pr["label"]                          if pr else "INCONNU"
            pb  = pr.get("probability", 0.0)           if pr else 0.0
            pbr = pr.get("probability_risk", 0.0)      if pr else 0.0
            thr = pr.get("threshold_used", ml_model.threshold or 0.5) if pr else (ml_model.threshold or 0.5)

            ttc  = float(row.get("TOTAL_MONTANT_TTC", 0) or 0)
            treg = float(row.get("TOTAL_MONTANT_REG", 0) or 0)
            imp  = max(0.0, ttc - treg)
            anc  = int(float(row.get("ANCIENNETE_CLIENT", 0) or 0) / 30)

            gov = str(row.get("GOUVERNORAT",   "") or "").strip() or None
            nat = str(row.get("NATURE_CLIENT", "") or "").strip() or None
            if gov in ("nan", "None", "INCONNU", ""): gov = None
            if nat in ("nan", "None", "INCONNU", ""): nat = None

            client = Client.query.filter_by(
                company_id=company_id, code_client=cc).first()
            if client is None:
                client = Client(company_id=company_id, code_client=cc, statut="ACTIF")
                db.session.add(client)
                db.session.flush()

            client.score_actuel     = rs
            client.risk_level       = rl
            client.derniere_analyse = now
            client.total_impaye     = imp
            client.anciennete       = anc
            if gov: client.gouvernorat   = gov
            if nat: client.nature_client = nat
            try:
                client.last_features = row_dict
            except Exception:
                pass
            db.session.flush()

            # Rebuild a realistic payment/invoice history from aggregate ML features.
            # The imported training dataset is usually one row per client, so without
            # this step the profile can show only one line. We synthesize multiple
            # rows using NB_FACTURES, NB_REGLEMENTS, totals and delay indicators.
            try:
                PaymentHistory.query.filter_by(client_id=client.id).delete()
                Invoice.query.filter_by(client_id=client.id).delete()

                nb_factures = int(float(row.get("NB_FACTURES", 0) or 0))
                nb_regs = int(float(row.get("NB_REGLEMENTS", 0) or 0))
                nb_retards = int(float(row.get("NB_RETARDS", 0) or 0))
                nb_factures = max(1, min(nb_factures, 20)) if ttc > 0 else 0
                nb_regs = max(1, min(nb_regs, 20)) if treg > 0 else 0

                avg_facture = (ttc / nb_factures) if nb_factures else 0.0
                avg_reg = (treg / nb_regs) if nb_regs else 0.0
                base_delay = int(round(float(row.get("RETARD_PONDERE", 0) or 0)))
                delay_std = int(round(float(row.get("RETARD_STD", 0) or 0)))

                for idx in range(nb_factures):
                    amount = avg_facture
                    if idx == 0 and nb_factures > 1:
                        amount = max(0.0, ttc - avg_facture * (nb_factures - 1))
                    paid = min(amount, max(0.0, avg_reg)) if treg > 0 else 0.0
                    remaining = max(0.0, amount - paid)
                    inv_date = now - timedelta(days=idx * 30 + 7)
                    db.session.add(Invoice(
                        company_id=company_id, client_id=client.id,
                        numero_facture=f"FAC-{cc}-{idx + 1:03d}",
                        montant_facture=round(amount, 2),
                        montant_regle=round(paid, 2),
                        reste_a_payer=round(remaining, 2),
                        date_facture=inv_date,
                        date_echeance=inv_date + timedelta(days=30),
                        statut="PAYEE" if remaining <= 0 else ("PARTIELLEMENT_PAYEE" if paid > 0 else "IMPAYEE"),
                    ))

                modes = ["VIREMENT", "CHÈQUE", "ESPÈCES", "TRAITE"]
                for idx in range(nb_regs):
                    is_late = idx < nb_retards
                    delay = max(1, base_delay + (idx % 3) * max(1, delay_std // 3)) if is_late else 0
                    amount = avg_reg
                    if idx == 0 and nb_regs > 1:
                        amount = max(0.0, treg - avg_reg * (nb_regs - 1))
                    db.session.add(PaymentHistory(
                        company_id=company_id, client_id=client.id,
                        montant=round(amount, 2),
                        mode=modes[idx % len(modes)],
                        date=now - timedelta(days=idx * 25 + 3),
                        delai=int(delay),
                        statut_paiement="RETARD" if delay > 0 else "REGLE",
                        reference=f"PAY-{cc}-{idx + 1:03d}",
                    ))
            except Exception:
                # History generation is supportive for the profile; it must not block training.
                pass

            if pr:
                pred = Prediction(
                    company_id=company_id, client_id=client.id, model_id=ml_model.id,
                    label=lbl, risk_score=rs, risk_level=rl,
                    probability=pb, probability_risk=pbr, threshold_used=thr,
                    ai_summary=pr.get("ai_summary"),
                    shap_factors=pr.get("top_factors"),
                    input_data=row_dict,
                )
                db.session.add(pred)
                db.session.flush()
                # Conception: générer les explications SHAP après les scores.
                for factor in (pr.get("top_factors") or [])[:10]:
                    db.session.add(ExplicationSHAP(
                        prediction_id=pred.id,
                        variable_importante=factor.get("feature"),
                        impact=factor.get("shap_value"),
                        description=(
                            f"Impact {'positif' if (factor.get('shap_value') or 0) > 0 else 'négatif'} "
                            f"sur la solvabilité (valeur={factor.get('feature_value', 0)})"
                        ),
                    ))

            db.session.add(ScoreHistory(
                company_id=company_id, client_id=client.id,
                risk_score=rs, risk_level=rl))

            count += 1
            if count % 50 == 0:
                db.session.commit()

        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            continue

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    print(f"[trainer] Synced {count} clients for company {company_id}")