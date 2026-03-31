FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy common package
COPY common/ /app/common/
COPY config/ /app/config/

# Copy service
COPY services/chatbot/app/ /app/app/

# Copy email templates
COPY resources/ /app/resources/

# Install deps
COPY services/chatbot/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app

EXPOSE 8007

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
