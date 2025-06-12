# 🛠 Webtools Platform

このリポジトリは、社内向けの様々なWebツールを **モノレポ** 形式で集約し、Docker上で動作させることを目的とした開発基盤です。各ツールは独立したアプリケーションとしてフォルダ単位で追加され、共通の `docker-compose.yml` によって一括管理されます。

---

## 📁 ディレクトリ構成

```
webtools-platform/
├── docker-compose.yml         # 全アプリのサービスを統合管理
├── README.md                  # 本ドキュメント
├── pdf-splitter/              # PDF分割ツール
│   ├── app/                   # Flask等のアプリ本体
│   ├── Dockerfile
│   ├── requirements.txt
│   └── config/
├── qr-generator/              # QRコード生成ツール（例）
│   ├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── config/
└── reverse-proxy/             # nginxなどのリバースプロキシ（必要時）
    ├── nginx.conf
    └── Dockerfile
```

---

## 🚀 アプリ開発の手順

1. アプリ用フォルダを作成（例：`qr-generator/`）
2. 以下のファイルを配置：
   - `app.py`（Flask等）
   - `Dockerfile`
   - `requirements.txt`
3. `docker-compose.yml` にサービス定義を追記（ポートの重複に注意）

---

## ⚙️ docker-compose.yml の例

```yaml
services:
  pdf-splitter:
    build: ./pdf-splitter
    ports:
      - "5001:5000"
    environment:
      HTTP_PROXY: http://10.170.250.80:8080
      HTTPS_PROXY: http://10.170.250.80:8080
      NO_PROXY: localhost,127.0.0.1
    volumes:
      - ./pdf-splitter:/app
    restart: always
```

### ➕ サービス追加例（qr-generator）

```yaml
  qr-generator:
    build: ./qr-generator
    ports:
      - "5002:5000"
    environment:
      HTTP_PROXY: http://10.170.250.80:8080
      HTTPS_PROXY: http://10.170.250.80:8080
      NO_PROXY: localhost,127.0.0.1
    volumes:
      - ./qr-generator:/app
    restart: always
```

---

## 🧪 起動手順

1. 初回ビルド
   ```bash
   docker compose build
   ```

2. コンテナ起動
   ```bash
   docker compose up -d
   ```

3. ログ確認（任意）
   ```bash
   docker compose logs -f <サービス名>
   ```

---

## 🌐 アクセス方法

各アプリは固定IPとポート番号によりアクセス可能です。

| アプリ名       | URL                             |
|----------------|----------------------------------|
| pdf-splitter   | http://10.170.175.20:5001        |
| qr-generator   | http://10.170.175.20:5002（予定）|

---

## 🔁 Git運用ルール

- **ブランチ命名**: `feature/<アプリ名>`（例：`feature/pdf-splitter-ui`）
- **コミット規約**: Conventional Commits を推奨
  - 例：`feat: add file upload to pdf-splitter`
- **プルリクエスト**: 新アプリ追加時は必ずPRを作成し、コードレビューを受ける

---

## 💡 開発Tips

- キャッシュを使わずに再ビルドしたい場合：
  ```bash
  docker compose build --no-cache
  ```

- Flaskアプリのホットリロードを有効にしたい場合、`app.py` 内で `debug=True` を指定

---

## 📬 お問い合わせ

このリポジトリや運用方法に関して不明な点があれば、ICTチーム（または@上田颯史郎）までご連絡ください。
