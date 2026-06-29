"""
utils/pdf_generator.py
Generate PDF credit reports using ReportLab.
Full implementation based on project source.
"""
from __future__ import annotations

import io
from datetime import datetime


def generate_client_report(profile: dict) -> bytes:
    """Generate a PDF credit report for a client. Returns raw PDF bytes."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table,
            TableStyle, HRFlowable,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise RuntimeError("reportlab non installé. pip install reportlab")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles     = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2",  parent=styles["Title"],   fontSize=18, spaceAfter=6)
    h2_style    = ParagraphStyle("H2",      parent=styles["Heading2"], fontSize=12, spaceAfter=4)
    body_style  = ParagraphStyle("Body",    parent=styles["Normal"],   fontSize=10, spaceAfter=3)
    small_style = ParagraphStyle("Small",   parent=styles["Normal"],   fontSize=8,  textColor=colors.grey)

    client  = profile.get("client", {})
    stats   = profile.get("payment_stats", {})
    factors = (profile.get("last_predictions") or [{}])[0].get("shap_factors") or []
    summary = (profile.get("last_predictions") or [{}])[0].get("ai_summary", "")

    risk_level = client.get("risk_level", "INCONNU")
    risk_color = {"FAIBLE": colors.green, "MOYEN": colors.orange, "ÉLEVÉ": colors.red}.get(risk_level, colors.grey)

    elements = []

    # Header
    elements.append(Paragraph("SolvAI — Rapport Crédit Client", title_style))
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", small_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1e3a5f")))
    elements.append(Spacer(1, 0.4*cm))

    # Client info
    elements.append(Paragraph("Informations Client", h2_style))
    info_data = [
        ["Code client", client.get("code_client", "—"), "Nom",      client.get("nom", "—")],
        ["Gouvernorat", client.get("gouvernorat", "—"), "Nature",   client.get("nature_client", "—")],
        ["Statut",      client.get("statut", "—"),      "Email",    client.get("email", "—")],
    ]
    info_table = Table(info_data, colWidths=[3*cm, 5*cm, 3*cm, 5*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
        ("FONTNAME",   (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1),  "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING",    (0, 0), (-1, -1), 5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.4*cm))

    # Risk score
    elements.append(Paragraph("Score de Risque", h2_style))
    score      = client.get("score_actuel", 0)
    score_data = [
        ["Score actuel",    f"{score}/100",                        "Niveau",  risk_level],
        ["Dernière analyse", _fmt_date(client.get("derniere_analyse")), "Modèle", "Actif"],
    ]
    score_table = Table(score_data, colWidths=[3*cm, 5*cm, 3*cm, 5*cm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), risk_color),
        ("TEXTCOLOR",  (1, 0), (1, 0), colors.white),
        ("BACKGROUND", (3, 0), (3, 0), risk_color),
        ("TEXTCOLOR",  (3, 0), (3, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica"),
        ("FONTNAME",   (1, 0), (1, 0),   "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING",    (0, 0), (-1, -1), 6),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 0.3*cm))

    # AI Summary
    if summary:
        elements.append(Paragraph("Analyse IA", h2_style))
        elements.append(Paragraph(summary, body_style))
        elements.append(Spacer(1, 0.3*cm))

    # SHAP Factors
    if factors:
        elements.append(Paragraph("Principaux Facteurs de Risque (SHAP)", h2_style))
        factor_rows = [["Facteur", "Valeur", "Impact SHAP", "Direction"]]
        for f in factors[:8]:
            direction = "↑ Aggravant" if f.get("impact") == "positif" else "↓ Atténuant"
            factor_rows.append([
                f.get("feature", ""),
                str(round(f.get("feature_value", 0), 2)),
                str(round(f.get("shap_value", 0), 4)),
                direction,
            ])
        ft = Table(factor_rows, colWidths=[5.5*cm, 3*cm, 3*cm, 4.5*cm])
        ft.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR",      (0, 0), (-1, 0), colors.white),
            ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("GRID",           (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("PADDING",        (0, 0), (-1, -1), 5),
        ]))
        elements.append(ft)
        elements.append(Spacer(1, 0.3*cm))

    # Payment stats
    if stats:
        elements.append(Paragraph("Statistiques de Paiement", h2_style))
        pay_data = [
            ["Total réglé",        f"{stats.get('total_regle', 0):,.0f} TND",
             "Total facturé",       f"{stats.get('total_factures', 0):,.0f} TND"],
            ["Délai moyen (jours)", str(stats.get("avg_delai", 0)),
             "Nb retards",          str(stats.get("nb_retards", 0))],
            ["Total impayé",        f"{stats.get('total_impaye', 0):,.0f} TND",
             "Taux recouvrement",   f"{stats.get('taux_recouvrement', 0):.1f}%"],
        ]
        pt = Table(pay_data, colWidths=[3.5*cm, 4.5*cm, 3.5*cm, 4.5*cm])
        pt.setStyle(TableStyle([
            ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 9),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("PADDING",    (0, 0), (-1, -1), 5),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
        ]))
        elements.append(pt)

    # Footer
    elements.append(Spacer(1, 1*cm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    elements.append(Paragraph(
        "Ce rapport est généré automatiquement par SolvAI. "
        "Les scores sont indicatifs et doivent être complétés par l'analyse humaine.",
        small_style,
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()


def _fmt_date(iso_str: str | None) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(iso_str)
