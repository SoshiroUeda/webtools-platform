# Pythonの公式イメージをベースにする
FROM python:3.11-slim

# 社内プロキシ環境の設定（必要に応じて）
ENV http_proxy=http://10.170.250.80:8080
ENV https_proxy=http://10.170.250.80:8080

# 作業ディレクトリを /app に設定
WORKDIR /app

# Pythonの依存関係ファイルをコピーしてインストールする
# これにより、requirements.txtだけが変更された場合にキャッシュが効く
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Popplerとその他必要なライブラリのインストール
# pip install の後に配置することで、キャッシュの恩恵を受けやすくする
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    poppler-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# アプリケーションコードをコンテナにコピー
# 依存関係のインストール後にコピーすることで、アプリコードの変更時のみ再コピーされる
COPY . .

# Flaskアプリケーションがリッスンするポートを公開する
EXPOSE 5000

# Gunicornを使ってアプリケーションを起動する
# -b 0.0.0.0:5000: すべてのIPアドレスでポート5000をリッスン
# --workers 4: ワーカープロセス数 (CPUコア数 * 2 + 1 などで調整)
# app:app: app.py ファイル内の Flask アプリケーションインスタンスの名前
CMD ["gunicorn", "-b", "0.0.0.0:5000", "--workers", "4", "app:app"]