FROM python:3.11-slim

WORKDIR /app

# 빌드에 필요한 패키지 설치
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl \
      build-essential \
      python3-dev \
      default-libmysqlclient-dev \
      libssl-dev \
      libffi-dev \
      rustc \
      cargo \
 && rm -rf /var/lib/apt/lists/*

COPY . /app
RUN pip install --no-cache-dir -r requirements.txt cryptography

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]