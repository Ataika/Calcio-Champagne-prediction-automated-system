FROM python:3.12-slim

WORKDIR /app

COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sql/champagne_queries.sql /sql/champagne_queries.sql
COPY pipeline/compute_predictions.py .
COPY pipeline/transfer_fee_model.py .

CMD ["python", "compute_predictions.py"]
