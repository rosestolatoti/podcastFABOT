from backend.database import Base, engine, init_db
from backend import models


def main():
    print("Inicializando banco de dados...")
    init_db()
    
    print("Tabelas criadas:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")
    
    print("\nBanco de dados pronto!")


if __name__ == "__main__":
    main()
