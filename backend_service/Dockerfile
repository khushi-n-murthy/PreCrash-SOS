FROM python:3.11-slim

WORKDIR /app

COPY backend_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY core_config/ ./core_config/
COPY backend_service/ ./backend_service/
COPY safety_relay_module/ ./safety_relay_module/

EXPOSE 5050

CMD ["python", "backend_service/app.py"]
