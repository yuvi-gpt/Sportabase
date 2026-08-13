import sqlite3


def connect_database(
    db_path,
) -> sqlite3.Connection:
    conn = sqlite3.connect(
        str(db_path),
        timeout=30,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA busy_timeout=30000;"
    )
    conn.execute(
        "PRAGMA journal_mode=WAL;"
    )
    conn.execute(
        "PRAGMA synchronous=NORMAL;"
    )
    conn.execute(
        "PRAGMA foreign_keys=ON;"
    )

    return conn
