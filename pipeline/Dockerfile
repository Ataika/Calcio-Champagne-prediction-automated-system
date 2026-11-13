FROM python:3.12-slim

WORKDIR /app

COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sql/champagne_queries.sql /sql/champagne_queries.sql
# Every analysis module; new ones are picked up by the registry in
# compute_predictions.py without touching this file.
COPY pipeline/*.py .

CMD ["python", "compute_predictions.py"]
