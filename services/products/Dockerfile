FROM python:3.13-slim

WORKDIR /app

# System deps for WeasyPrint (documents service) and aiomysql
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy common package
COPY common/ /app/common/
COPY config/ /app/config/

# Copy service
COPY services/products/app/ /app/app/

# Install deps
COPY services/products/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
