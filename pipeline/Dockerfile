FROM python:3.12-slim

WORKDIR /app

COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sql/champagne_queries.sql /sql/champagne_queries.sql
COPY pipeline/compute_predictions.py .
COPY pipeline/transfer_fee_model.py .
COPY pipeline/club_style_clustering.py .
COPY pipeline/feature_correlations.py .
COPY pipeline/power_ratings.py .
COPY pipeline/proxy_xg.py .
COPY pipeline/discipline_effect.py .
COPY pipeline/shap_analysis.py .

CMD ["python", "compute_predictions.py"]
