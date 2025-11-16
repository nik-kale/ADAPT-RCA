"""
Simple web dashboard for ADAPT-RCA.
"""
import logging
import os
import re
import secrets
from pathlib import Path
from typing import Optional
from collections import defaultdict
from datetime import datetime, timedelta

from ..constants import WEB_UPLOAD_MAX_SIZE_MB, WEB_ALLOWED_EXTENSIONS
from ..utils import PathValidationError
from ..security import sanitize_for_logging, sanitize_api_error

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


# Simple in-memory rate limiter
class RateLimiter:
    """Simple in-memory rate limiter for API endpoints."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """
        Check if request from client is allowed.

        Args:
            client_id: Unique identifier for client (e.g., IP address)

        Returns:
            True if request is allowed, False if rate limited
        """
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Remove old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > cutoff
        ]

        # Check if under limit
        if len(self.requests[client_id]) >= self.max_requests:
            return False

        # Record this request
        self.requests[client_id].append(now)
        return True


# Global rate limiter instance
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)


def _determine_log_format(filename: str, format_param: str) -> tuple[str, str]:
    """
    Determine log format and file extension.

    Args:
        filename: Original filename
        format_param: Format parameter from request ('auto', 'jsonl', etc.)

    Returns:
        Tuple of (log_format, file_extension)
    """
    from pathlib import Path
    ext = Path(filename).suffix
    log_format = format_param

    if format_param == 'auto':
        # Auto-detect based on extension
        if filename.endswith('.jsonl'):
            log_format = 'jsonl'
        elif filename.endswith('.csv'):
            log_format = 'csv'
        else:
            log_format = 'generic'

    return log_format, ext


def _load_events_from_file(file_path: Path, log_format: str, filename: str):
    """
    Load events from file based on format.

    Args:
        file_path: Path to the temporary file
        log_format: Log format ('jsonl', 'csv', 'syslog', etc.)
        filename: Original filename for format detection

    Returns:
        List of raw events

    Raises:
        ValueError: If log format is unsupported or loading fails
    """
    try:
        if log_format == 'jsonl' or (log_format == 'auto' and filename.endswith('.jsonl')):
            from ..ingestion.file_loader import load_jsonl
            return list(load_jsonl(file_path))
        elif log_format == 'csv' or (log_format == 'auto' and filename.endswith('.csv')):
            from ..ingestion.csv_loader import load_csv
            return list(load_csv(file_path))
        else:
            from ..ingestion.text_loader import load_text_log
            return list(load_text_log(file_path, log_format=log_format))
    except Exception as e:
        raise ValueError(f"Failed to load events from file: {e}") from e


def _process_and_analyze(raw_events: list) -> dict:
    """
    Process raw events and perform root cause analysis.

    Args:
        raw_events: List of raw event dictionaries

    Returns:
        Analysis result dictionary

    Raises:
        ValueError: If analysis fails
    """
    from ..parsing.log_parser import normalize_event
    from ..reasoning.agent import analyze_incident

    if not raw_events:
        raise ValueError("No events found in file")

    # Normalize events
    events = [normalize_event(e) for e in raw_events]

    # Perform analysis
    result = analyze_incident(events)

    return result


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

    # Security configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

    # Security headers
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'"
        return response

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
        # Rate limiting
        client_id = request.remote_addr or 'unknown'
        if not rate_limiter.is_allowed(client_id):
            logger.warning(f"Rate limit exceeded for client: {sanitize_for_logging(client_id)}")
            return jsonify({
                'error': 'Rate limit exceeded. Please try again later.',
                'retry_after': 60
            }), 429

        try:
            # Validate file upload
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

            # Sanitize filename and determine format
            safe_filename = sanitize_filename(file.filename)
            log_format = request.form.get('format', 'auto')
            _, ext = _determine_log_format(safe_filename, log_format)

            # Save uploaded file temporarily
            import tempfile
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext, prefix='adapt_rca_') as tmp:
                    file.save(tmp.name)
                    tmp_path = Path(tmp.name)

                # Load events from file
                raw_events = _load_events_from_file(tmp_path, log_format, file.filename)

                # Process and analyze
                result = _process_and_analyze(raw_events)

                return jsonify(result)

            finally:
                # Clean up temp file
                if tmp_path:
                    tmp_path.unlink(missing_ok=True)

        except ValueError as e:
            # Client errors (400)
            sanitized_error = sanitize_api_error(e)
            logger.warning(f"Client error: {sanitize_for_logging(str(e))}")
            return jsonify({'error': sanitized_error}), 400

        except Exception as e:
            # Server errors (500)
            sanitized_error = sanitize_api_error(e)
            logger.error(f"Analysis error: {sanitize_for_logging(str(e))}", exc_info=True)
            return jsonify({'error': sanitized_error}), 500

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
