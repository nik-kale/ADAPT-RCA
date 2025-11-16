"""
Simple web dashboard for ADAPT-RCA.
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional

from ..constants import WEB_UPLOAD_MAX_SIZE_MB, WEB_ALLOWED_EXTENSIONS
from ..utils import PathValidationError

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize uploaded filename to prevent path traversal attacks.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename

    Raises:
        ValueError: If filename is invalid
    """
    if not filename:
        raise ValueError("Filename cannot be empty")

    # Remove path components
    filename = os.path.basename(filename)

    # Remove any remaining path separators
    filename = filename.replace("/", "").replace("\\", "")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Limit to alphanumeric, dots, dashes, underscores
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

    # Prevent hidden files
    if filename.startswith('.'):
        filename = '_' + filename[1:]

    # Ensure we still have a filename
    if not filename or filename == '_':
        raise ValueError("Invalid filename after sanitization")

    # Limit length
    if len(filename) > 255:
        # Keep extension
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext

    return filename


def validate_upload(file, max_size_mb: int = WEB_UPLOAD_MAX_SIZE_MB) -> None:
    """
    Validate uploaded file.

    Args:
        file: Flask file upload object
        max_size_mb: Maximum file size in MB

    Raises:
        ValueError: If validation fails
    """
    # Check filename
    if not file.filename:
        raise ValueError("No filename provided")

    # Sanitize and check extension
    safe_filename = sanitize_filename(file.filename)
    ext = Path(safe_filename).suffix.lower()

    if ext not in WEB_ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(WEB_ALLOWED_EXTENSIONS))
        raise ValueError(
            f"File type '{ext}' not allowed. Allowed types: {allowed}"
        )

    # Check file size (read first chunk to get size)
    # Note: This reads the file into memory, but for web uploads that's acceptable
    file.seek(0, os.SEEK_END)
    size_bytes = file.tell()
    file.seek(0)  # Reset to beginning

    max_size_bytes = max_size_mb * 1024 * 1024
    if size_bytes > max_size_bytes:
        size_mb = size_bytes / (1024 * 1024)
        raise ValueError(
            f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)"
        )

    # Basic MIME type validation (if available)
    if hasattr(file, 'content_type') and file.content_type:
        # Allow text and JSON types
        allowed_mime_prefixes = ('text/', 'application/json', 'application/x-json')
        if not any(file.content_type.startswith(prefix) for prefix in allowed_mime_prefixes):
            logger.warning(f"Unexpected MIME type: {file.content_type}")

    logger.debug(f"Upload validation passed: {safe_filename} ({size_bytes} bytes)")


def create_app(debug: bool = False):
    """
    Create Flask application for ADAPT-RCA dashboard.

    Args:
        debug: Enable debug mode

    Returns:
        Flask app instance

    Raises:
        ImportError: If Flask is not installed
    """
    try:
        from flask import Flask, render_template_string, request, jsonify
    except ImportError:
        raise ImportError(
            "Flask not installed. Install with: pip install 'adapt-rca[web]'"
        )

    app = Flask(__name__)
    app.config['DEBUG'] = debug
    app.config['MAX_CONTENT_LENGTH'] = WEB_UPLOAD_MAX_SIZE_MB * 1024 * 1024  # Max upload size

    # HTML template
    INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>ADAPT-RCA Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .upload-section {
            margin: 30px 0;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 4px;
        }
        button {
            background: #4CAF50;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background: #45a049;
        }
        #results {
            margin-top: 30px;
        }
        .error {
            color: #f44336;
            padding: 10px;
            background: #ffebee;
            border-radius: 4px;
        }
        .success {
            color: #4CAF50;
            padding: 10px;
            background: #e8f5e9;
            border-radius: 4px;
        }
        pre {
            background: #f4f4f4;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 ADAPT-RCA Dashboard</h1>
        <p>Adaptive Diagnostic Agent for Proactive Troubleshooting – Root Cause Analyzer</p>

        <div class="upload-section">
            <h2>Upload Log File</h2>
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" name="file" id="fileInput" accept=".jsonl,.json,.csv,.log,.txt">
                <br><br>
                <label>
                    Format:
                    <select name="format" id="formatSelect">
                        <option value="auto">Auto-detect</option>
                        <option value="jsonl">JSONL</option>
                        <option value="csv">CSV</option>
                        <option value="syslog">Syslog</option>
                        <option value="generic">Generic Text</option>
                    </select>
                </label>
                <br><br>
                <button type="submit">Analyze</button>
            </form>
        </div>

        <div id="results"></div>
    </div>

    <script>
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(e.target);
            const resultsDiv = document.getElementById('results');

            resultsDiv.innerHTML = '<p>Analyzing...</p>';

            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (response.ok) {
                    displayResults(data);
                } else {
                    resultsDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                }
            } catch (error) {
                resultsDiv.innerHTML = `<div class="error">Error: ${error.message}</div>`;
            }
        });

        function displayResults(data) {
            const resultsDiv = document.getElementById('results');

            let html = '<div class="success"><h2>Analysis Complete</h2></div>';
            html += '<h3>Summary</h3>';
            html += `<p>${data.incident_summary}</p>`;

            html += '<h3>Root Causes</h3><ul>';
            data.probable_root_causes.forEach(rc => {
                html += `<li>${rc}</li>`;
            });
            html += '</ul>';

            html += '<h3>Recommended Actions</h3><ul>';
            data.recommended_actions.forEach(action => {
                html += `<li>${action}</li>`;
            });
            html += '</ul>';

            if (data.causal_graph && data.causal_graph.root_causes) {
                html += '<h3>Causal Graph - Root Causes</h3><ul>';
                data.causal_graph.root_causes.forEach(rc => {
                    html += `<li><strong>${rc}</strong></li>`;
                });
                html += '</ul>';
            }

            html += '<h3>Full Results (JSON)</h3>';
            html += `<pre>${JSON.stringify(data, null, 2)}</pre>`;

            resultsDiv.innerHTML = html;
        }
    </script>
</body>
</html>
    """

    @app.route('/')
    def index():
        """Render the main dashboard page."""
        return render_template_string(INDEX_TEMPLATE)

    @app.route('/analyze', methods=['POST'])
    def analyze():
        """Analyze uploaded log file."""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            # Validate upload (size, extension, filename)
            try:
                validate_upload(file)
            except ValueError as e:
                return jsonify({'error': f'Upload validation failed: {e}'}), 400

            # Sanitize filename
            safe_filename = sanitize_filename(file.filename)
            ext = Path(safe_filename).suffix

            log_format = request.form.get('format', 'auto')

            # Save uploaded file temporarily with sanitized name
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix='adapt_rca_') as tmp:
                # Save with size limit check
                file.save(tmp.name)
                tmp_path = Path(tmp.name)

            try:
                # Determine loader based on format
                if log_format == 'jsonl' or (log_format == 'auto' and file.filename.endswith('.jsonl')):
                    from ..ingestion.file_loader import load_jsonl
                    raw_events = list(load_jsonl(tmp_path))
                elif log_format == 'csv' or (log_format == 'auto' and file.filename.endswith('.csv')):
                    from ..ingestion.csv_loader import load_csv
                    raw_events = list(load_csv(tmp_path))
                else:
                    from ..ingestion.text_loader import load_text_log
                    raw_events = list(load_text_log(tmp_path, log_format=log_format))

                # Analyze
                from ..parsing.log_parser import normalize_event
                from ..reasoning.agent import analyze_incident

                events = [normalize_event(e) for e in raw_events]
                result = analyze_incident(events)

                return jsonify(result)

            finally:
                # Clean up temp file
                tmp_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    @app.route('/health')
    def health():
        """Health check endpoint."""
        return jsonify({'status': 'ok'})

    return app


def run_dashboard(host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
    """
    Run the web dashboard.

    Args:
        host: Host to bind to
        port: Port to listen on
        debug: Enable debug mode
    """
    app = create_app(debug=debug)
    logger.info(f"Starting ADAPT-RCA dashboard on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
