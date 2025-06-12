from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
import uuid
from PyPDF2 import PdfMerger
import shutil

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    return render_template('uploading.html')

@app.route('/main', methods=['GET', 'POST'])
def main():
    if request.method == 'POST':
        uploaded_files = request.files.getlist('pdf_files')
        if not uploaded_files:
            return "PDFファイルを選択してください", 400

        pdf_list = []
        for file in uploaded_files:
            if file.filename == '':
                continue
            filename = secure_filename(file.filename)
            unique_id = str(uuid.uuid4())
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
            file.save(save_path)
            pdf_list.append({
                'id': unique_id,
                'filename': filename,
                'path': save_path
            })

        session['pdf_files'] = pdf_list
        return render_template('main.html', pdfs=pdf_list)
    else: # GET request
        pdfs = session.get('pdf_files', [])
        return render_template('main.html', pdfs=pdfs)

@app.route('/update_pdf_order', methods=['POST'])
def update_pdf_order():
    new_order_ids = request.json.get('order')
    if not new_order_ids:
        return jsonify({'status': 'error', 'message': 'No order provided'}), 400

    current_pdfs = {pdf['id']: pdf for pdf in session.get('pdf_files', [])}
    ordered_pdfs = []
    for pdf_id in new_order_ids:
        if pdf_id in current_pdfs:
            ordered_pdfs.append(current_pdfs[pdf_id])

    session['pdf_files'] = ordered_pdfs
    return jsonify({'status': 'success'})

@app.route('/merging')
def merging():
    return render_template('merging.html')

@app.route('/execute_merge', methods=['POST'])
def execute_merge():
    pdfs = session.get('pdf_files', [])
    if not pdfs:
        return jsonify({'status': 'error', 'message': 'No PDFs to merge'}), 400

    merger = PdfMerger()
    for pdf in pdfs:
        merger.append(pdf['path'])

    merged_path = os.path.join(app.config['UPLOAD_FOLDER'], f"merged_{uuid.uuid4().hex}.pdf")
    merger.write(merged_path)
    merger.close()

    session['merged_pdf'] = merged_path
    return jsonify({'status': 'success', 'redirect_url': url_for('preview')})

@app.route('/preview')
def preview():
    if 'merged_pdf' not in session or not os.path.exists(session['merged_pdf']):
        return redirect(url_for('index'))
    return render_template('preview.html')

@app.route('/download')
def download():
    merged_path = session.get('merged_pdf')
    if not merged_path or not os.path.exists(merged_path):
        return redirect(url_for('index'))

    as_attachment = request.args.get('download', 'false').lower() == 'true'
    return send_file(merged_path, as_attachment=as_attachment)

@app.route('/delete_pdf', methods=['POST'])
def delete_pdf():
    pdf_id = request.json.get('id')
    if not pdf_id:
        return jsonify({'status': 'error', 'message': 'PDF ID not provided'}), 400

    pdf_files = session.get('pdf_files', [])
    found = False
    updated_pdf_files = []
    for pdf in pdf_files:
        if pdf['id'] == pdf_id:
            try:
                os.remove(pdf['path'])
                found = True
            except Exception as e:
                print(f"Error deleting file {pdf['path']}: {e}")
            continue
        updated_pdf_files.append(pdf)

    session['pdf_files'] = updated_pdf_files

    if found:
        return jsonify({'status': 'success', 'message': 'PDF deleted successfully'})
    else:
        return jsonify({'status': 'error', 'message': 'PDF not found'}), 404

@app.route('/reset')
def reset():
    for pdf in session.get('pdf_files', []):
        try:
            os.remove(pdf['path'])
        except Exception:
            pass

    merged_pdf = session.get('merged_pdf')
    if merged_pdf:
        try:
            os.remove(merged_pdf)
        except Exception:
            pass

    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
