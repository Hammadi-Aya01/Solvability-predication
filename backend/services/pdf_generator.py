"""
services/pdf_generator.py
Re-exports PDF generation from utils/pdf_generator.py.
"""
from utils.pdf_generator import generate_client_report

__all__ = ["generate_client_report"]
