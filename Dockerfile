FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl sqlmap \
        libxml2-dev libxslt1-dev \
        python3-dev gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN mkdir -p /app/data

ENV PORT=3000
EXPOSE 3000
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]