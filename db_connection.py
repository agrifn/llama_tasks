# db_connection.py

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

# Load environment variables from the .env file
load_dotenv()

def get_db_connection():
    try:
        connection = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        return connection
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

def get_db_cursor(connection):
    return connection.cursor(cursor_factory=RealDictCursor)
