if __package__:
    from .load import Carregador
else:
    from load import Carregador

__all__ = [
    "Carregador",
]
