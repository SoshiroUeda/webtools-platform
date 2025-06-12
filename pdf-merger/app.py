from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify
from werkzeug.utils import secure_filename
import os
import tempfile
import uuid
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import shutil
from pdf2image import convert_from_path # For PDF to image conversion
from io import BytesIO # For image processing in memory

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.config['THUMBNAIL_FOLDER'] = os.path.join(tempfile.gettempdir(), 'pdf_thumbnails')

# Ensure thumbnail directory exists (exist_ok=True allows creation even if it exists)
if not os.path.exists(app.config['THUMBNAIL_FOLDER']):
    os.makedirs(app.config['THUMBNAIL_FOLDER'], exist_ok=True)

# Helper function to convert a PDF page to an image
def _convert_pdf_page_to_image(pdf_path, page_num, desired_thumbnail_path):
    """
    指定されたPDFのページを画像に変換し、指定されたパスに保存するヘルパー関数。
    desired_thumbnail_path は、最終的に保存したい画像ファイルのフルパス。
    """
    print(f"[DEBUG] _convert_pdf_page_to_image called for PDF: {pdf_path}, Page: {page_num + 1}, Desired path: {desired_thumbnail_path}")
    try:
        # pdf2image.convert_from_path を使用して特定のページを画像に変換
        # page_num は0ベースなので、pdftoppmの-f/-lオプションと同様に+1する
        images = convert_from_path(
            pdf_path,
            first_page=page_num + 1,
            last_page=page_num + 1,
            size=(200, None) # 幅を200pxにスケール (高さを自動調整)
        )

        if images:
            # 変換された画像（単一ページなのでリストの最初の要素）をPNGとして保存
            images[0].save(desired_thumbnail_path, format='PNG')
            print(f"[DEBUG] Thumbnail saved to {desired_thumbnail_path}")
            return desired_thumbnail_path
        else:
            print(f"[ERROR] pdf2image did not convert page {page_num + 1} from {pdf_path}")
            return None
    except Exception as e:
        print(f"[ERROR] An error occurred during PDF to image conversion using pdf2image: {e}")
        return None


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    return render_template('upload.html')

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
    print("[DEBUG] /edit_pdf route accessed.")
    all_pdfs_data = []
    pdfs_in_session = session.get('pdf_files', [])

    for pdf_data in pdfs_in_session:
        pdf_id = pdf_data['id']
        pdf_path = pdf_data['path']
        filename = pdf_data['filename']

        if not os.path.exists(pdf_path):
            print(f"[WARNING] PDF file not found at {pdf_path} for PDF ID {pdf_id}. Skipping.")
            continue

        try:
            reader = PdfReader(pdf_path)
            pages_data = []
            for i in range(len(reader.pages)):
                # Generate thumbnail and get its URL
                thumbnail_filename = f"{pdf_id}_page_{i}.png"
                thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)

                print(f"[DEBUG] Checking thumbnail for PDF {pdf_id}, page {i}: {thumbnail_path}")
                if not os.path.exists(thumbnail_path):
                    print(f"[DEBUG] Thumbnail not found. Attempting to generate for {pdf_path} page {i}.")
                    generated_path = _convert_pdf_page_to_image(pdf_path, i, thumbnail_path)
                    if generated_path and os.path.exists(generated_path): # Check if generation was successful
                        print(f"[DEBUG] Thumbnail generation successful for {pdf_id}, page {i}.")
                        pass
                    else:
                        print(f"[ERROR] Thumbnail generation failed or file not found after generation for {pdf_id}, page {i}.")
                        thumbnail_path = None # Indicate failure
                else:
                    print(f"[DEBUG] Thumbnail already exists for {pdf_id}, page {i}.")

                thumbnail_url = url_for('get_pdf_page_image', pdf_id=pdf_id, page_num=i) if thumbnail_path and os.path.exists(thumbnail_path) else None
                print(f"[DEBUG] Thumbnail URL for PDF {pdf_id}, page {i}: {thumbnail_url}")

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
            print(f"[ERROR] Error processing PDF {filename} (ID: {pdf_id}): {e}")
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
    print(f"[DEBUG] /get_pdf_page_image accessed for {pdf_id}, page {page_num}. Looking for: {thumbnail_path}")

    if os.path.exists(thumbnail_path):
        print(f"[DEBUG] Thumbnail found at {thumbnail_path}. Sending file.")
        return send_file(thumbnail_path, mimetype='image/png')
    else:
        print(f"[WARNING] Thumbnail not found at {thumbnail_path}. Attempting regeneration or returning 404.")
        # If for some reason thumbnail is missing, try to regenerate or return placeholder
        # Try to regenerate thumbnail if not found
        pdfs_in_session = session.get('pdf_files', [])
        target_pdf_path = None
        for pdf_data in pdfs_in_session:
            if pdf_data['id'] == pdf_id:
                target_pdf_path = pdf_data['path']
                break
        
        if target_pdf_path and os.path.exists(target_pdf_path):
            print(f"[DEBUG] Original PDF found at {target_pdf_path}. Attempting to regenerate thumbnail.")
            generated_path = _convert_pdf_page_to_image(target_pdf_path, page_num, thumbnail_path)
            if generated_path and os.path.exists(generated_path):
                print(f"[DEBUG] Thumbnail regenerated successfully for {pdf_id}, page {page_num}.")
                # If generation successful, and it's not already the correct name, rename it
                if generated_path != thumbnail_path: # This check is redundant after the fix, but harmless.
                    os.rename(generated_path, thumbnail_path)
                return send_file(thumbnail_path, mimetype='image/png')
            else:
                print(f"[ERROR] Regeneration failed for {pdf_id}, page {page_num}.")

        print(f"[ERROR] Image not found and could not be regenerated for {pdf_id}, page {page_num}.")
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
