import psycopg2
import os
from dotenv import load_dotenv

# Load env variables from the mobile backend project
load_dotenv("/Users/macbookpro/Downloads/bot_project/sentinel-predator-mobile/.env")

DATABASE_URL = os.getenv("DATABASE_URL")

def reload_postgrest_cache():
    try:
        print("Connecting to Supabase PostgreSQL db...")
        print(f"DATABASE_URL: {DATABASE_URL}")
        # Connect to DB
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        
        # Execute reload command for PostgREST
        with conn.cursor() as cur:
            cur.execute("NOTIFY pgrst, 'reload schema';")
            print("Successfully sent 'NOTIFY pgrst, reload schema' command!")
            print("The Supabase API schema cache should now be updated.")
            
        conn.close()
    except Exception as e:
        print(f"Failed to reload cache: {e}")

if __name__ == "__main__":
    reload_postgrest_cache()
