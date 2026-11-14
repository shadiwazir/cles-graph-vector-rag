FROM python:3.12-slim
# The stock MLflow image has no PostgreSQL driver.
RUN pip install --no-cache-dir "mlflow==3.18.0" "psycopg2-binary>=2.9"
