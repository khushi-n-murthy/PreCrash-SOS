FROM python:3.11-slim

WORKDIR /app

COPY data_ml_engine/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY core_config/ ./core_config/
COPY data_ml_engine/ ./data_ml_engine/

EXPOSE 8001

CMD ["python", "data_ml_engine/pipeline/ml_api_server.py"]