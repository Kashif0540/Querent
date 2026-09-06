# Querent

Ask a question about your data in plain English, get back a real SQL query, and see it actually run — no trusting the model's output blindly.

## What it does

1. Upload a CSV.
2. Pandas reads it and loads it into an in-memory SQLite table.
3. The table's schema (column names + dtypes) is extracted automatically.
4. You type a question like "top 5 by revenue." An LLM (Groq, GPT-OSS 120B) is given the schema and the question, and returns SQL as structured JSON.
5. The returned SQL is validated — SELECT-only, no stacked statements, no destructive keywords (`DROP`, `DELETE`, `ALTER`, etc.) — before it ever touches the database.
6. `pandas.read_sql` actually executes it and shows the real result, plus a chart when the result is numeric.

## Background

Built after finishing the AI Foundations with Python Workshop (Averon Globals) — the course covered Python, NumPy, Pandas, data handling, and AI/ML foundations. This project applies those directly: Pandas for loading and querying the data, an LLM for the English → SQL step, and the same "validate before you trust it" principle used throughout the training's data-handling material.

## Tech stack

- Python, Pandas, SQLite (in-memory, via the standard library)
- Streamlit for the UI
- Groq (GPT-OSS 120B) for English → SQL generation

## Running locally

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here    # macOS/Linux
# set GROQ_API_KEY=your_key_here     # Windows
streamlit run app.py
```

## Deployment (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and pick this repo, with `app.py` as the entry point.
3. In the app's **Settings → Secrets**, add:
   ```toml
   GROQ_API_KEY = "your_key_here"
   ```
4. Deploy. Because Streamlit runs Python server-side, the key is never sent to the browser — there's no client-side exposure risk.

## License

MIT
