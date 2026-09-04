"""
Querent
----------
Upload a CSV, ask a question in plain English, get back a real SQL query
that actually runs against your data.

Pipeline:
  1. Pandas reads the CSV and loads it into an in-memory SQLite table.
  2. The table schema (columns + dtypes) is extracted.
  3. An LLM (Groq) is prompted with the schema + question and returns SQL
     as structured JSON.
  4. The returned SQL is validated (SELECT-only, no stacked statements,
     no destructive keywords) before it ever touches the database.
  5. pandas.read_sql actually executes it and shows the real result —
     the query isn't just trusted, it's verified.

Because this is a Streamlit app (Python running server-side), the API key
never reaches the browser — unlike a client-side JS app, there's no proxy
needed here for that part; Streamlit secrets/env vars keep it server-only
by default.
"""

import json
import os
import re
import sqlite3

import pandas as pd
import requests
import streamlit as st

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"

FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter",
    "create", "attach", "detach", "pragma", "replace", "vacuum",
]


def get_api_key() -> str:
    """Streamlit secrets when deployed, env var for local dev."""
    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY", "")


def load_csv_to_sqlite(uploaded_file):
    df = pd.read_csv(uploaded_file)
    conn = sqlite3.connect(":memory:")
    df.to_sql("data", conn, index=False, if_exists="replace")
    return df, conn


def extract_schema(df: pd.DataFrame) -> str:
    return ", ".join(f"{col} ({df[col].dtype})" for col in df.columns)


def build_prompt(schema: str, question: str) -> str:
    return f"""You are a SQL generator. The table is named "data" with these \
columns: {schema}.

Given the user's question, write a single SQLite SELECT query that answers \
it. Respond ONLY with valid JSON in exactly this shape, no markdown fences, \
no extra text:
{{"sql": "SELECT ...", "explanation": "one sentence explanation"}}

Only ever generate a SELECT statement. Never generate INSERT, UPDATE, \
DELETE, DROP, ALTER, or any other statement type.

User question: {question}"""


def call_groq(prompt: str, api_key: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = {
        "model": GROQ_MODEL,
        "temperature": 0.2,
        "max_tokens": 512,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = requests.post(GROQ_API_URL, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def is_safe_select(sql: str) -> bool:
    """Only a single, plain SELECT statement is allowed through."""
    cleaned = sql.strip().rstrip(";")
    if ";" in cleaned:
        return False  # no stacked statements
    if not cleaned:
        return False
    first_word = cleaned.split(None, 1)[0].lower()
    if first_word != "select":
        return False
    lowered = cleaned.lower()
    return not any(re.search(rf"\b{kw}\b", lowered) for kw in FORBIDDEN_KEYWORDS)


# ---------------------------------------------------------------- UI ----

st.set_page_config(page_title="Querent", layout="wide")
st.title("Querent")
st.caption(
    "Ask questions about your data in plain English. "
    "Pandas + SQLite + an LLM turn it into SQL and actually run it."
)

if "history" not in st.session_state:
    st.session_state.history = []

api_key = get_api_key()
if not api_key:
    st.warning(
        "No GROQ_API_KEY found. Add it to Streamlit secrets (deployed) "
        "or set it as an environment variable (local dev)."
    )

uploaded = st.file_uploader("Upload a CSV", type=["csv"])

if uploaded:
    df, conn = load_csv_to_sqlite(uploaded)
    schema = extract_schema(df)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Schema")
        st.code(schema, language="text")
    with col2:
        st.subheader("Preview")
        st.dataframe(df.head(10), use_container_width=True)

    question = st.text_input("Ask a question about this data")
    run = st.button("Run", disabled=not (question and api_key))

    if run:
        with st.spinner("Generating SQL..."):
            sql, explanation = None, ""
            try:
                raw = call_groq(build_prompt(schema, question), api_key)
                parsed = json.loads(raw)
                sql = parsed.get("sql", "")
                explanation = parsed.get("explanation", "")
            except Exception as e:
                st.error(f"Couldn't generate a query: {e}")

        if sql:
            if not is_safe_select(sql):
                st.error(
                    "Generated query failed the safety check "
                    "(only SELECT statements are allowed). Try rephrasing."
                )
            else:
                st.subheader("Generated SQL")
                st.code(sql, language="sql")
                if explanation:
                    st.caption(explanation)

                try:
                    result = pd.read_sql(sql, conn)
                    st.subheader("Result")
                    st.dataframe(result, use_container_width=True)

                    numeric_cols = result.select_dtypes(include="number").columns
                    if len(numeric_cols) >= 1 and len(result) > 1 and len(result.columns) >= 2:
                        st.subheader("Chart")
                        st.bar_chart(result.set_index(result.columns[0])[numeric_cols])

                    st.session_state.history.insert(
                        0, {"question": question, "sql": sql, "rows": len(result)}
                    )
                except Exception as e:
                    st.error(f"Query failed to run: {e}")

    if st.session_state.history:
        st.subheader("History")
        for item in st.session_state.history:
            short_sql = item["sql"][:80] + ("..." if len(item["sql"]) > 80 else "")
            st.markdown(f"- **{item['question']}** → `{short_sql}` ({item['rows']} rows)")
else:
    st.info("Upload a CSV to get started.")
