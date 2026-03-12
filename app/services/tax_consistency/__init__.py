"""
Módulo Tax Consistency Engine.

Responsável por detectar divergências tributárias entre o cálculo do motor
e os valores declarados no XML da NF-e (ex.: ICMS-ST, base de cálculo, etc.).
"""

from app.services.tax_consistency.tax_consistency_engine import TaxConsistencyEngine

__all__ = ["TaxConsistencyEngine"]
