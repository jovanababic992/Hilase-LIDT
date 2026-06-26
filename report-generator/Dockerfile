FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends pandoc libmagic1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY admin/ ./admin/
COPY app/ ./app/
COPY assets/ ./assets/
COPY configs/ ./configs/
COPY data/ ./data/
COPY pdf/ ./pdf/
COPY services/ ./services/

EXPOSE 8501
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]