# One-shot loader: reads quotes.csv, loads it into authors and quotes, prints counts, exits.
# Every setting comes from an environment variable that docker-compose.yml passes in.
import os
import sys

import pandas as pd
import psycopg2

DB_PARAMS = {
    "host": os.environ["DB_HOST"],          # "db" inside Compose
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": os.environ["DB_NAME"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],  # never typed into the code
}
CSV_PATH = os.environ.get("CSV_PATH", "/data/quotes.csv")
TABLES = ["authors", "quotes"]


def counts(cur):
    result = {}
    for t in TABLES:
        cur.execute(f"SELECT COUNT(*) FROM {t};")
        result[t] = cur.fetchone()[0]
    return result


def main():
    df = pd.read_csv(CSV_PATH, dtype=str)
    for col in df.columns:
        df[col] = df[col].str.strip()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")

    bad = df["Author"].isna() | df["Quote"].isna()           # NOT NULL columns
    good = df[~bad]
    print(f"Rows read: {len(df)}   good: {len(good)}   rejected: {bad.sum()}")

    conn = psycopg2.connect(**DB_PARAMS)
    try:
        with conn:                                           # one transaction
            with conn.cursor() as cur:
                before = counts(cur)
                for name in good["Author"].unique():
                    cur.execute("INSERT INTO authors (authorname) VALUES (%s) "
                                "ON CONFLICT (authorname) DO NOTHING;", (name,))
                cur.execute("SELECT authorname, authorid FROM authors;")
                author_ids = dict(cur.fetchall())
                for _, r in good.iterrows():
                    year = None if pd.isna(r["Year"]) else int(r["Year"])
                    cur.execute("INSERT INTO quotes (authorid, message, year) VALUES (%s, %s, %s) "
                                "ON CONFLICT (message) DO NOTHING;",
                                (author_ids[r["Author"]], r["Quote"], year))
                after = counts(cur)
    finally:
        conn.close()

    for t in TABLES:
        print(f"{t:<10} before={before[t]:<5} after={after[t]:<5} added={after[t] - before[t]}")
    print("Seed finished.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SEED FAILED: {exc}", file=sys.stderr)
        sys.exit(1)                                          # non-zero exit: Compose will not start web
