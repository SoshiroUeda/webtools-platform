from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
import uuid
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import shutil
from PIL import Image # For image processing
import subprocess # For running poppler-utils commands

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['THUMBNAIL_FOLDER'] = os.path.join(tempfile.gettempdir(), 'pdf_thumbnails')

# Ensure thumbnail directory exists
if not os.path.exists(app.config['THUMBNAIL_FOLDER']):
    os.makedirs(app.config['THUMBNAIL_FOLDER'])

# Helper function to convert a PDF page to an image
def _convert_pdf_page_to_image(pdf_path, page_num, output_path):
    try:
        # poppler-utilsのpdftoppmコマンドを使用
        # -png: PNG形式で出力
        # -f <ページ番号>: 開始ページ
        # -l <ページ番号>: 終了ページ
        # -scale-to-width 200: 幅を200pxにスケール (適宜調整)
        # <入力PDF> <出力パス接頭辞>
        command = [
            "pdftoppm",
            "-png",
            "-f", str(page_num + 1), # pdftoppmは1ベースのページ番号
            "-l", str(page_num + 1),
            "-scale-to-width", "200", # Thumbnail width
            pdf_path,
            output_path.replace(".png", "") # pdftoppm adds page number, so remove .png suffix
        ]
        subprocess.run(command, check=True, capture_output=True)
        # pdftoppm will create output_path-1.png for single page
        return f"{output_path.replace(".png", "")}-{page_num + 1}.png"
    except subprocess.CalledProcessError as e:
        print(f"Error converting PDF page to image: {e.stderr.decode()}")
        return None
    except FileNotFoundError:
        print("pdftoppm not found. Please install poppler-utils.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during PDF to image conversion: {e}")
        return None


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

@app.route('/edit_pdf') # No longer takes pdf_id as argument
def edit_pdf():
    all_pdfs_data = []
    pdfs_in_session = session.get('pdf_files', [])

    for pdf_data in pdfs_in_session:
        pdf_id = pdf_data['id']
        pdf_path = pdf_data['path']
        filename = pdf_data['filename']

        if not os.path.exists(pdf_path):
            print(f"Warning: PDF file not found at {pdf_path}")
            continue

        try:
            reader = PdfReader(pdf_path)
            pages_data = []
            for i in range(len(reader.pages)):
                # Generate thumbnail and get its URL
                thumbnail_filename = f"{pdf_id}_page_{i}.png"
                thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)

                if not os.path.exists(thumbnail_path):
                    # Only generate if not already exists
                    generated_path = _convert_pdf_page_to_image(pdf_path, i, thumbnail_path)
                    if generated_path and os.path.exists(generated_path): # Check if generation was successful
                        os.rename(generated_path, thumbnail_path) # Rename to desired filename
                    else:
                        thumbnail_path = None # Indicate failure

                thumbnail_url = url_for('get_pdf_page_image', pdf_id=pdf_id, page_num=i) if thumbnail_path else None

                pages_data.append({
                    'page_number': i + 1,
                    'original_pdf_id': pdf_id, # Keep track of original PDF
                    'original_page_index': i, # Keep track of original page index
                    'thumbnail_url': thumbnail_url
                })
            all_pdfs_data.append({
                'id': pdf_id,
                'filename': filename,
                'pages': pages_data
            })
        except Exception as e:
            print(f"Error processing PDF {filename}: {e}")
            continue

    # Store current page order in session for persistence across reloads
    # This will be a flat list of dictionaries, each representing a page with its original pdf_id and page_index
    flat_page_list = []
    for pdf_data in all_pdfs_data:
        for page in pdf_data['pages']:
            flat_page_list.append({
                'pdf_id': page['original_pdf_id'],
                'page_index': page['original_page_index']
            })
    session['current_page_order'] = flat_page_list

    return render_template('edit.html', all_pdfs_data=all_pdfs_data)


@app.route('/get_pdf_page_image/<pdf_id>/<int:page_num>')
def get_pdf_page_image(pdf_id, page_num):
    thumbnail_filename = f"{pdf_id}_page_{page_num}.png"
    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)

    if os.path.exists(thumbnail_path):
        return send_file(thumbnail_path, mimetype='image/png')
    else:
        # If for some reason thumbnail is missing, try to regenerate or return placeholder
        # For now, return 404
        return "Image not found", 404


@app.route('/update_pdf_page_order/<pdf_id>', methods=['POST'])
def update_pdf_page_order(pdf_id):
    # This endpoint needs to be updated to handle global page order, not just for a single PDF
    # For now, it will remain as is but noted for future change.
    new_order = request.json.get('order') # This will be a list of original_index
    if not new_order:
        return jsonify({'status': 'error', 'message': 'No page order provided'}), 400

    pdfs = session.get('pdf_files', [])
    target_pdf = None
    for pdf in pdfs:
        if pdf['id'] == pdf_id:
            target_pdf = pdf
            break

    if not target_pdf or not os.path.exists(target_pdf['path']):
        return jsonify({'status': 'error', 'message': 'Target PDF not found'}), 404

    try:
        reader = PdfReader(target_pdf['path'])
        writer = PdfWriter()

        for original_index in new_order:
            writer.add_page(reader.pages[original_index])
        
        # Overwrite the original file with the reordered pages
        with open(target_pdf['path'], 'wb') as f:
            writer.write(f)

        return jsonify({'status': 'success', 'message': 'Page order updated successfully'})

    except Exception as e:
        print(f"Error updating page order for {target_pdf['path']}: {e}")
        return jsonify({'status': 'error', 'message': f'Error updating page order: {e}'}), 500

@app.route('/update_global_page_order', methods=['POST'])
def update_global_page_order():
    new_global_order = request.json.get('order') # List of {pdf_id, page_index}
    if not new_global_order:
        return jsonify({'status': 'error', 'message': 'No global page order provided'}), 400
    
    session['current_page_order'] = new_global_order
    return jsonify({'status': 'success', 'message': 'Global page order updated successfully'})

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
    global_page_order = session.get('current_page_order', [])
    if not global_page_order:
        return jsonify({'status': 'error', 'message': 'No pages to merge. Please upload PDFs and edit their order.'}), 400

    # Reconstruct pdf_files dictionary for easy lookup by pdf_id
    pdfs_in_session = {pdf['id']: pdf for pdf in session.get('pdf_files', [])}

    merger = PdfMerger()
    for page_info in global_page_order:
        pdf_id = page_info['pdf_id']
        page_index = page_info['page_index']
        
        if pdf_id not in pdfs_in_session or not os.path.exists(pdfs_in_session[pdf_id]['path']):
            print(f"Warning: Original PDF for page {page_index + 1} of {pdf_id} not found. Skipping.")
            continue

        try:
            reader = PdfReader(pdfs_in_session[pdf_id]['path'])
            merger.append(reader, pages=(page_index, page_index + 1)) # Append only this specific page
        except Exception as e:
            print(f"Error appending page {page_index + 1} from {pdfs_in_session[pdf_id]['filename']}: {e}")
            # Depending on desired behavior, you might want to return an error or skip this page
            continue

    if not merger.pages: # Check if any pages were actually added to the merger
        return jsonify({'status': 'error', 'message': 'No valid pages were found to merge.'}), 400

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
