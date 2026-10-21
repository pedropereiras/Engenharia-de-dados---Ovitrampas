"""Módulo de carregamento: suporta SQLite (padrão) e Neon (Postgres)."""

from load import Carregador  # reexporta para manter compatibilidade

__all__ = [
    "Carregador",
]
