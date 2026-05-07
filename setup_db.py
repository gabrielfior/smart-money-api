import os
import psycopg2

# Connect via Supabase pooler using env var
conn = psycopg2.connect(
    host="aws-1-us-east-2.pooler.supabase.com",
    port="6543",
    database="postgres",
    user="postgres.jkadmzolzhvizxtveexa",
    password=os.environ.get("SUPABASE_DB_PASSWORD")
)

cursor = conn.cursor()

# Add provider column to existing tables
cursor.execute("""
ALTER TABLE events ADD COLUMN IF NOT EXISTS provider TEXT DEFAULT 'polymarket';
ALTER TABLE markets ADD COLUMN IF NOT EXISTS provider TEXT DEFAULT 'polymarket';

CREATE INDEX IF NOT EXISTS idx_events_provider ON events(provider);
CREATE INDEX IF NOT EXISTS idx_markets_provider ON markets(provider);
""")

conn.commit()
print("✅ Added 'provider' column to events and markets tables")

# Verify
cursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'events' ORDER BY ordinal_position;")
columns = cursor.fetchall()
print("\nEvents table:")
for col in columns:
    print(f"  - {col[0]}: {col[1]}")

cursor.close()
conn.close()
