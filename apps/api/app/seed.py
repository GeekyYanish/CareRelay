from .database import initialize_database
from .store import Store


def main() -> None:
    initialize_database()
    Store().seed()
    print("CareRelay demo users seeded")


if __name__ == "__main__":
    main()

