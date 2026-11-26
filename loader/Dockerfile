FROM python:3.12-slim

WORKDIR /app

COPY loader/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sql/schema.sql /sql/schema.sql
COPY sql/team_name_map.sql /sql/team_name_map.sql
COPY loader/load_data.py .
COPY loader/get_data.py loader/sources.json ./

CMD ["python", "load_data.py"]
