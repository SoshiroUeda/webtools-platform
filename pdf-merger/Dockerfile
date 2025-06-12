FROM python:3.11-slim

# 社内プロキシ環境の設定（必要に応じて）
ENV http_proxy=http://10.170.250.80:8080
ENV https_proxy=http://10.170.250.80:8080

# 作業ディレクトリを /app に設定
WORKDIR /app

# Popplerとその他必要なライブラリのインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    poppler-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# アプリケーションコードをコピー
COPY . /app

# Python依存パッケージのインストール
RUN pip install --no-cache-dir -r requirements.txt

# Flask起動設定
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# アプリケーション起動
CMD ["flask", "run"]

