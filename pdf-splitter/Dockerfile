FROM python:3.11-slim

# 社内プロキシ環境の設定（必要な場合）
ENV http_proxy=http://10.170.250.80:8080
ENV https_proxy=http://10.170.250.80:8080

WORKDIR /app

# Poppler と必要なライブラリのインストールを追加
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    poppler-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# アプリケーションコードのコピー
COPY . /app

# Python ライブラリのインストール
RUN pip install --no-cache-dir -r requirements.txt

# Flask アプリの環境変数
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

CMD ["flask", "run"]
