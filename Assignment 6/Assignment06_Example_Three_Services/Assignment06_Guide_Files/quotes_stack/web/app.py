# Quotes dashboard. Same pattern as practice_app.py from Assignment 5, except the
# connection settings come from environment variables instead of a CONFIG block.
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text

DB_HOST = os.environ.get("DB_HOST", "localhost")   # Compose sets this to "db"
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DB_NAME"]
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]

st.set_page_config(page_title="Quotes", layout="wide")


@st.cache_resource
def get_engine():
    return create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


@st.cache_data(ttl=60)
def run_query(sql, params=None):
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


st.title("Quotes about computing and data")

authors = run_query("SELECT authorname FROM authors ORDER BY authorname;")["authorname"].tolist()
chosen = st.sidebar.multiselect("Author", authors, default=authors)
if not chosen:
    st.warning("Pick at least one author.")
    st.stop()

FILTER = "FROM quotes q JOIN authors a ON q.authorid = a.authorid WHERE a.authorname = ANY(:authors)"
params = {"authors": chosen}

n = run_query("SELECT COUNT(*) AS n " + FILTER, params).loc[0, "n"]
st.metric("Quotes", int(n))

per_author = run_query("SELECT a.authorname, COUNT(*) AS quotes " + FILTER +
                       " GROUP BY a.authorname ORDER BY quotes DESC;", params)
fig = px.bar(per_author, x="authorname", y="quotes", title="Quotes per author",
             labels={"authorname": "", "quotes": "Quotes"})
st.plotly_chart(fig, width="stretch")

st.dataframe(run_query("SELECT a.authorname AS author, q.message AS quote, q.year " + FILTER +
                       " ORDER BY a.authorname, q.year;", params),
             width="stretch", hide_index=True)
