# test_db_connection.py

from db_connection import get_db_connection

def test_connection():
    conn = get_db_connection()
    if conn:
        print("Database connection successful!")
        conn.close()
    else:
        print("Failed to connect to the database.")

if __name__ == '__main__':
    test_connection()
