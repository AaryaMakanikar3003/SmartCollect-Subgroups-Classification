import os
from dotenv import load_dotenv

load_dotenv()  

DB_CONFIG = {
    "host": os.getenv("DATABASE_HOST"),
    "port": os.getenv("DATABASE_PORT"),
    "dbname": os.getenv("DATABASE_NAME"),
    "user": os.getenv("DATABASE_USER"),
    "password": os.getenv("DATABASE_PASSWORD"),
}

FUSION_DB_CONFIG = {
    "host": os.getenv("FUSION_DATABASE_HOST"),
    "port": os.getenv("FUSION_DATABASE_PORT"),
    "dbname": os.getenv("FUSION_DATABASE_NAME"),
    "user": os.getenv("FUSION_DATABASE_USER"),
    "password": os.getenv("FUSION_DATABASE_PASSWORD"),
}

ESAF_DB_CONFIG = {
    "host": os.getenv("ESAF_DATABASE_HOST"),
    "port": os.getenv("ESAF_DATABASE_PORT"),
    "dbname": os.getenv("ESAF_DATABASE_NAME"),
    "user": os.getenv("ESAF_DATABASE_USER"),
    "password": os.getenv("ESAF_DATABASE_PASSWORD"),
}

DB_SOURCES = {
    "default": DB_CONFIG,
    "fusion": FUSION_DB_CONFIG,
    "esaf": ESAF_DB_CONFIG,
}