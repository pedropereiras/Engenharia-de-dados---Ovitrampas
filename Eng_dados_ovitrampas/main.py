from src.main import Pipeline


def main() -> None:
    """Executa o pipeline ETL completo e encerra a conexão com o banco."""
    Pipeline().executar().fechar()


if __name__ == "__main__":
    main()
