from flask import Flask, render_template, request, redirect, url_for, send_file, session, render_template_string
from werkzeug.utils import secure_filename  # ※未使用でも一応残しておく
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_bytes
from io import BytesIO
import os
import zipfile
import tempfile
import uuid
import base64
import re  # ← 追加

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

def split_pdf_by_points(reader, split_points, base_name):
    split_files = []
    start = 0
    for i, end in enumerate(split_points):
        if end <= start:
            continue  # 不正な範囲をスキップ
        writer = PdfWriter()
        for j in range(start, end):
            writer.add_page(reader.pages[j])
        output = BytesIO()
        writer.write(output)
        output.seek(0)
        filename = f"{base_name}-part-{i+1}.pdf"
        split_files.append((filename, output))
        start = end
    return split_files


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preview', methods=['POST'])
def preview():
    file = request.files.get('file')
    if not file or file.filename == '':
        return "PDFファイルを選択してください", 400

    # 日本語ファイル名を安全に扱うため、危険文字だけ除去
    original_name = file.filename
    name_without_ext, ext = os.path.splitext(original_name)
    safe_name = re.sub(r'[\/\\\0\r\n]', '', name_without_ext)
    filename = f"{safe_name}{ext}"

    unique_id = str(uuid.uuid4())
    temp_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
    file.save(temp_pdf_path)

    session['temp_pdf_path'] = temp_pdf_path
    session['filename'] = filename
    session['pdf_id'] = unique_id

    with open(temp_pdf_path, 'rb') as f:
        images = convert_from_bytes(f.read())

    encoded_images = []
    for i, img in enumerate(images):
        buf = BytesIO()
        img.save(buf, format='PNG')
        encoded = base64.b64encode(buf.getvalue()).decode('utf-8')
        encoded_images.append({'index': i, 'data': encoded})

    return render_template('preview.html', images=encoded_images, total=len(encoded_images))

@app.route('/confirm', methods=['POST'])
def confirm():
    split_points = request.form.get('split_points', '')
    split_points = [int(i) for i in split_points.split(',') if i.isdigit()]
    split_points = sorted(set(split_points))
    session['split_points'] = split_points

    temp_pdf_path = session.get('temp_pdf_path')
    if not temp_pdf_path or not os.path.exists(temp_pdf_path):
        return "PDFファイルが見つかりません。", 400

    with open(temp_pdf_path, 'rb') as f:
        reader = PdfReader(BytesIO(f.read()))
        total_pages = len(reader.pages)

    ranges = []
    prev = 0
    split_points.append(total_pages)
    for i, point in enumerate(split_points):
        ranges.append((i + 1, prev + 1, point))
        prev = point

    filename = os.path.splitext(session.get('filename', 'output'))[0]

    html = render_template_string('''
    <div class="popup-content" style="background: #fff; padding: 24px; border-radius: 12px; text-align: left; box-shadow: 0 0 20px rgba(0,0,0,0.2); max-width: 500px;">
      <h2 style="margin-bottom: 16px; color: #333;">分割ファイルを保存する</h2>
      <p style="margin-bottom: 16px;">元のファイルを分割し、以下の名前で保存します：</p>
      <ul style="list-style: none; padding: 0; margin-bottom: 24px;">
        {% for i, start, end in ranges %}
          <li style="margin-bottom: 8px;">📄 <strong>{{ filename }}-part-{{ i }}.pdf</strong>（{{ start }} ～ {{ end }} ページ）</li>
        {% endfor %}
      </ul>
      <form action="{{ url_for('download') }}" method="post" style="display:inline;">
        <button type="submit" style="padding: 10px 20px; font-size: 16px; background-color: #0078D4; color: #fff; border: none; border-radius: 6px; cursor: pointer;">保存</button>
      </form>
      <button onclick="document.getElementById('popupOverlay').style.display='none';" style="margin-left: 12px; padding: 10px 20px; font-size: 16px; background-color: #ccc; border: none; border-radius: 6px; cursor: pointer;">キャンセル</button>
    </div>
    ''', ranges=ranges, filename=filename)

    return html

@app.route('/download', methods=['POST'])
def download():
    split_points = session.get('split_points', [])
    temp_pdf_path = session.get('temp_pdf_path')
    if not temp_pdf_path or not os.path.exists(temp_pdf_path):
        return "PDFファイルが見つかりません。", 400

    with open(temp_pdf_path, 'rb') as f:
        file_data = f.read()
    reader = PdfReader(BytesIO(file_data))

    base_name = os.path.splitext(session.get('filename', 'output'))[0]
    split_files = split_pdf_by_points(reader, split_points, base_name)

    zip_stream = BytesIO()
    with zipfile.ZipFile(zip_stream, 'w') as zipf:
        for name, file_stream in split_files:
            zipf.writestr(name, file_stream.read())
    zip_stream.seek(0)

    zip_filename = f"{base_name}-split.zip"
    return send_file(zip_stream, as_attachment=True, download_name=zip_filename, mimetype='application/zip')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
