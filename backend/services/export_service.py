"""
services/export_service.py
Export service: thin wrapper around utils/export helpers.
"""
from __future__ import annotations


class ExportService:

    @staticmethod
    def clients_to_excel(clients: list[dict]) -> bytes:
        from utils.export import export_clients_excel
        return export_clients_excel(clients)

    @staticmethod
    def clients_to_csv(clients: list[dict]) -> str:
        from utils.export import export_clients_csv
        return export_clients_csv(clients)

    @staticmethod
    def predictions_to_excel(predictions: list[dict]) -> bytes:
        from utils.export import export_predictions_excel
        return export_predictions_excel(predictions)

    @staticmethod
    def bulk_results_to_excel(results: list[dict]) -> bytes:
        from utils.export import export_bulk_results_excel
        return export_bulk_results_excel(results)
