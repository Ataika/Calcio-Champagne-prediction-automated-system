FROM python:3.12-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY .streamlit ./.streamlit
COPY app/ .

RUN useradd --create-home --uid 10001 calcio
USER calcio

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/api/health', timeout=4)"

CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8501", "--no-server-header"]
