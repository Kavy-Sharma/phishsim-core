import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password=os.getenv("DB_PASSWORD"),
    database="phishsim_db"
)
cursor = db.cursor()
try:
    cursor.execute("ALTER TABLE campaigns MODIFY COLUMN status VARCHAR(50) DEFAULT 'draft'")
    db.commit()
    print("Successfully updated campaigns table status column.")
except Exception as e:
    print(f"Error: {e}")
