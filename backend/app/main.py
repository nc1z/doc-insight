from fastapi import FastAPI

app = FastAPI(title="Doc Insight API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
