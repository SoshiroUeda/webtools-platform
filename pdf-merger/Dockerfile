# Pythonの公式イメージをベースにする (軽量版)
FROM python:3.11-slim-buster

# 社内プロキシ環境の設定（必要に応じて。不要であれば削除）
ENV http_proxy=http://10.170.250.80:8080
ENV https_proxy=http://10.170.250.80:8080

# 作業ディレクトリを /app に設定
WORKDIR /app

# Pythonの依存関係ファイルをコピーしてインストールする
# このステップを早くすることで、requirements.txtが変更されない限りキャッシュが効き、
# アプリケーションコードの変更時のビルド時間を短縮できる
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Poppler-utilsとその他必要なシステムライブラリをインストールする
# PDFから画像を生成するために必要
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    poppler-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# アプリケーションコードをコンテナにコピー
# 依存関係のインストール後にコピーする
COPY . .

# Flaskアプリケーションがリッスンするポートを公開する
EXPOSE 5000

# Gunicornを使ってアプリケーションを起動する
# -b 0.0.0.0:5000: すべてのIPアドレスでポート5000をリッスン
# --workers 4: ワーカープロセス数 (CPUコア数 * 2 + 1 などで調整可能)
# app:app: app.py ファイル内の Flask アプリケーションインスタンスの名前（app.pyで`app = Flask(__name__)`と定義している場合）
CMD ["python", "-m", "gunicorn", "-b", "0.0.0.0:5000", "--workers", "4", "app:app"]