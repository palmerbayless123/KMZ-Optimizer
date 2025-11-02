"""
Main Flask Application
Backend API for KMZ merge and generation system.

This application integrates all processing modules and provides REST API endpoints for:
- File uploads (CSV and KMZ)
- Processing job management
- KMZ generation with smart merging
- Status tracking and downloads

API Endpoints:
- POST /upload - Upload CSV and optional KMZ files
- POST /generate - Start processing job
- GET /status/<job_id> - Check processing status
- GET /download/<job_id> - Download generated files
- GET /health - Health check

Author: System
Date: November 2, 2025
Version: 1.0
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import uuid
import json
import logging
from datetime import datetime
import threading
import traceback
from typing import Dict, List, Optional

# Import processing modules
from csv_parser import parse_csv, validate_csv_file, get_csv_preview, filter_by_states
from kmz_parser import parse_kmz, validate_kmz_file, get_kmz_stats
from location_matcher import match_locations, generate_match_report
from data_merger import (
    merge_datasets, 
    generate_merge_summary, 
    prepare_kmz_metadata,
    group_locations_by_state
)
from county_lookup import CountyLookup, add_county_to_locations
from kmz_generator import generate_kmz, generate_state_kmz_files

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
MAX_CSV_SIZE_MB = 50
MAX_KMZ_SIZE_MB = 10
ALLOWED_CSV_EXTENSIONS = {'csv'}
ALLOWED_KMZ_EXTENSIONS = {'kmz'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CSV_SIZE_MB * 1024 * 1024

# Create folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Job storage (in production, use Redis or database)
jobs = {}
jobs_lock = threading.Lock()


def allowed_file(filename, extensions):
    """Check if file has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions


def create_job_id():
    """Generate unique job ID."""
    return str(uuid.uuid4())


def get_job(job_id):
    """Get job data safely."""
    with jobs_lock:
        return jobs.get(job_id)


def update_job(job_id, updates):
    """Update job data safely."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(updates)


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    
    Returns:
        JSON with status and timestamp
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0'
    })


@app.route('/upload', methods=['POST'])
def upload_files():
    """
    Upload CSV and optional KMZ files.
    
    Expected form data:
        - csv_files: One or more CSV files
        - kmz_file: Optional KMZ file
    
    Returns:
        JSON with job_id and file information
    """
    try:
        # Check if CSV files are present
        if 'csv_files' not in request.files:
            return jsonify({'error': 'No CSV files provided'}), 400
        
        csv_files = request.files.getlist('csv_files')
        kmz_file = request.files.get('kmz_file')
        
        if not csv_files or all(f.filename == '' for f in csv_files):
            return jsonify({'error': 'No CSV files selected'}), 400
        
        # Create job
        job_id = create_job_id()
        job_folder = os.path.join(UPLOAD_FOLDER, job_id)
        os.makedirs(job_folder, exist_ok=True)
        
        # Save CSV files
        csv_file_paths = []
        for csv_file in csv_files:
            if csv_file and allowed_file(csv_file.filename, ALLOWED_CSV_EXTENSIONS):
                filename = secure_filename(csv_file.filename)
                filepath = os.path.join(job_folder, filename)
                csv_file.save(filepath)
                
                # Validate CSV
                is_valid, error = validate_csv_file(filepath, MAX_CSV_SIZE_MB)
                if not is_valid:
                    return jsonify({'error': f'Invalid CSV {filename}: {error}'}), 400
                
                csv_file_paths.append(filepath)
            else:
                return jsonify({'error': f'Invalid file type: {csv_file.filename}'}), 400
        
        # Save KMZ file if provided
        kmz_file_path = None
        kmz_stats = None
        if kmz_file and kmz_file.filename:
            if allowed_file(kmz_file.filename, ALLOWED_KMZ_EXTENSIONS):
                filename = secure_filename(kmz_file.filename)
                kmz_file_path = os.path.join(job_folder, filename)
                kmz_file.save(kmz_file_path)
                
                # Validate KMZ
                is_valid, error = validate_kmz_file(kmz_file_path, MAX_KMZ_SIZE_MB)
                if not is_valid:
                    return jsonify({'error': f'Invalid KMZ: {error}'}), 400
                
                # Get KMZ stats
                kmz_stats = get_kmz_stats(kmz_file_path)
            else:
                return jsonify({'error': f'Invalid KMZ file type'}), 400
        
        # Create job record
        job = {
            'job_id': job_id,
            'status': 'uploaded',
            'csv_files': csv_file_paths,
            'kmz_file': kmz_file_path,
            'kmz_stats': kmz_stats,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        with jobs_lock:
            jobs[job_id] = job
        
        logger.info(f"Files uploaded for job {job_id}: "
                   f"{len(csv_file_paths)} CSV files, "
                   f"KMZ: {bool(kmz_file_path)}")
        
        # Prepare response
        response = {
            'job_id': job_id,
            'csv_count': len(csv_file_paths),
            'kmz_uploaded': bool(kmz_file_path),
            'status': 'uploaded',
            'timestamp': job['created_at']
        }
        
        if kmz_stats:
            response['kmz_stats'] = {
                'total_placemarks': kmz_stats['total_placemarks'],
                'proposed_count': kmz_stats['proposed_count'],
                'existing_count': kmz_stats['existing_count']
            }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@app.route('/generate', methods=['POST'])
def generate_kmz():
    """
    Start processing job to generate KMZ files.
    
    Expected JSON body:
        {
            "job_id": "...",
            "csv_state_selections": {
                "file1.csv": ["GA", "FL"],
                "file2.csv": ["GA", "SC"]
            },
            "merge_with_kmz": true,
            "match_threshold_meters": 200,
            "include_unmatched_proposed": true
        }
    
    Returns:
        JSON with processing status
    """
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        
        if not job_id:
            return jsonify({'error': 'job_id is required'}), 400
        
        job = get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        if job['status'] not in ['uploaded', 'failed']:
            return jsonify({'error': f'Job already {job["status"]}'}), 400
        
        # Get processing parameters
        csv_state_selections = data.get('csv_state_selections', {})
        merge_with_kmz = data.get('merge_with_kmz', True)
        match_threshold = data.get('match_threshold_meters', 200)
        include_unmatched_proposed = data.get('include_unmatched_proposed', True)
        
        # Update job status
        update_job(job_id, {
            'status': 'processing',
            'progress': 0,
            'updated_at': datetime.utcnow().isoformat(),
            'parameters': {
                'csv_state_selections': csv_state_selections,
                'merge_with_kmz': merge_with_kmz,
                'match_threshold': match_threshold,
                'include_unmatched_proposed': include_unmatched_proposed
            }
        })
        
        # Start processing in background thread
        thread = threading.Thread(
            target=process_job,
            args=(job_id,)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started processing job {job_id}")
        
        return jsonify({
            'job_id': job_id,
            'status': 'processing',
            'estimated_time_seconds': 120,
            'processing_started': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Generate error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': f'Failed to start processing: {str(e)}'}), 500


def process_job(job_id):
    """
    Background processing function for generating KMZ files.
    
    Args:
        job_id (str): Job ID to process
    """
    try:
        job = get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        logger.info(f"Processing job {job_id}")
        
        # Get parameters
        params = job.get('parameters', {})
        csv_state_selections = params.get('csv_state_selections', {})
        merge_with_kmz = params.get('merge_with_kmz', True)
        match_threshold = params.get('match_threshold', 200)
        
        # Step 1: Parse CSV files (10% progress)
        update_job(job_id, {'progress': 10, 'current_step': 'Parsing CSV files'})
        logger.info(f"[{job_id}] Parsing CSV files")
        
        csv_locations = []
        for csv_path in job['csv_files']:
            filename = os.path.basename(csv_path)
            locations = parse_csv(csv_path)
            
            # Apply state filter if specified
            if filename in csv_state_selections:
                locations = filter_by_states(locations, csv_state_selections[filename])
            
            csv_locations.extend(locations)
        
        logger.info(f"[{job_id}] Parsed {len(csv_locations)} CSV locations")
        
        # Step 2: Parse KMZ file if provided (20% progress)
        kmz_proposed = []
        kmz_existing = []
        if merge_with_kmz and job.get('kmz_file'):
            update_job(job_id, {'progress': 20, 'current_step': 'Parsing KMZ file'})
            logger.info(f"[{job_id}] Parsing KMZ file")
            
            kmz_proposed, kmz_existing = parse_kmz(job['kmz_file'])
            logger.info(f"[{job_id}] Parsed KMZ: {len(kmz_proposed)} proposed, "
                       f"{len(kmz_existing)} existing")
        
        # Step 3: Match locations (40% progress)
        matches = []
        if kmz_proposed:
            update_job(job_id, {'progress': 40, 'current_step': 'Matching locations'})
            logger.info(f"[{job_id}] Matching CSV and KMZ locations")
            
            matches, unmatched_csv, unmatched_kmz = match_locations(
                csv_locations, kmz_proposed, match_threshold
            )
            logger.info(f"[{job_id}] Found {len(matches)} matches")
        
        # Step 4: Merge datasets (60% progress)
        update_job(job_id, {'progress': 60, 'current_step': 'Merging datasets'})
        logger.info(f"[{job_id}] Merging datasets")
        
        final_locations, merge_metadata = merge_datasets(
            csv_locations, kmz_existing, kmz_proposed, matches
        )
        logger.info(f"[{job_id}] Merged to {len(final_locations)} total locations")
        
        # Step 5: Add county data (80% progress)
        update_job(job_id, {'progress': 80, 'current_step': 'Looking up counties'})
        logger.info(f"[{job_id}] Adding county data")
        
        county_lookup = CountyLookup(cache_file='county_cache.json')
        locations_with_data = [loc['data'] for loc in final_locations]
        enriched_locations = add_county_to_locations(locations_with_data, county_lookup)
        
        # Step 6: Generate KMZ files (90% progress)
        update_job(job_id, {'progress': 90, 'current_step': 'Generating KMZ files'})
        logger.info(f"[{job_id}] Generating KMZ output files")
        
        # Prepare metadata for KMZ generation
        kmz_metadata = prepare_kmz_metadata(final_locations)
        logger.info(f"[{job_id}] KMZ metadata prepared:")
        logger.info(f"  Date range: {kmz_metadata['date_range']}")
        logger.info(f"  Total ranked stores (overall): {kmz_metadata['total_ranked_stores']}")
        logger.info(f"  Total ranked stores US: {kmz_metadata['total_ranked_stores_us']}")
        logger.info(f"  Total stores US: {kmz_metadata['total_stores_us']}")
        logger.info(f"  States with data: {', '.join(kmz_metadata['state_store_counts'].keys())}")
        
        # Group locations by state
        states_dict = group_locations_by_state(final_locations)
        logger.info(f"[{job_id}] Grouped into {len(states_dict)} states")
        
        # Generate state-level KMZ files using actual KMZ generator
        output_folder = os.path.join(OUTPUT_FOLDER, job_id)
        os.makedirs(output_folder, exist_ok=True)
        
        generated_files = generate_state_kmz_files(
            enriched_locations,
            output_folder,
            kmz_metadata
        )
        
        logger.info(f"[{job_id}] Generated {len(generated_files)} KMZ files")

        
        # Step 7: Complete (100% progress)
        update_job(job_id, {
            'status': 'completed',
            'progress': 100,
            'current_step': 'Complete',
            'merge_stats': merge_metadata,
            'states_generated': list(generated_files.keys()),
            'download_url': f'/download/{job_id}',
            'completed_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        })
        
        logger.info(f"[{job_id}] Processing complete")
        
    except Exception as e:
        logger.error(f"[{job_id}] Processing error: {str(e)}\n{traceback.format_exc()}")
        update_job(job_id, {
            'status': 'failed',
            'error': str(e),
            'updated_at': datetime.utcnow().isoformat()
        })


@app.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    """
    Get processing status for a job.
    
    Args:
        job_id (str): Job ID
    
    Returns:
        JSON with job status and details
    """
    try:
        job = get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Prepare response (exclude internal details)
        response = {
            'job_id': job_id,
            'status': job['status'],
            'progress': job.get('progress', 0),
            'current_step': job.get('current_step'),
            'created_at': job['created_at'],
            'updated_at': job['updated_at']
        }
        
        if job['status'] == 'completed':
            response['merge_stats'] = job.get('merge_stats', {})
            response['states_generated'] = job.get('states_generated', [])
            response['download_url'] = job.get('download_url')
            response['completed_at'] = job.get('completed_at')
        
        if job['status'] == 'failed':
            response['error'] = job.get('error')
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Status error: {str(e)}")
        return jsonify({'error': 'Failed to get status'}), 500


@app.route('/download/<job_id>', methods=['GET'])
def download_files(job_id):
    """
    Download generated KMZ files as a ZIP archive.
    
    Args:
        job_id (str): Job ID
    
    Returns:
        ZIP file containing all generated KMZ files
    """
    try:
        job = get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        if job['status'] != 'completed':
            return jsonify({'error': 'Job not completed yet'}), 400
        
        output_folder = os.path.join(OUTPUT_FOLDER, job_id)
        if not os.path.exists(output_folder):
            return jsonify({'error': 'Output files not found'}), 404
        
        # Create ZIP file
        import zipfile
        zip_path = os.path.join(OUTPUT_FOLDER, f'{job_id}.zip')
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename in os.listdir(output_folder):
                filepath = os.path.join(output_folder, filename)
                zipf.write(filepath, filename)
        
        logger.info(f"Serving download for job {job_id}")
        
        return send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'kmz_files_{job_id}.zip'
        )
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': 'Download failed'}), 500


@app.route('/jobs', methods=['GET'])
def list_jobs():
    """
    List all jobs (for debugging/admin).
    
    Returns:
        JSON with list of all jobs
    """
    try:
        with jobs_lock:
            job_list = [
                {
                    'job_id': job_id,
                    'status': job['status'],
                    'created_at': job['created_at'],
                    'updated_at': job['updated_at']
                }
                for job_id, job in jobs.items()
            ]
        
        return jsonify({'jobs': job_list, 'total': len(job_list)}), 200
        
    except Exception as e:
        logger.error(f"List jobs error: {str(e)}")
        return jsonify({'error': 'Failed to list jobs'}), 500


# Error handlers
@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error."""
    return jsonify({'error': f'File too large. Maximum size: {MAX_CSV_SIZE_MB}MB'}), 413


@app.errorhandler(404)
def not_found(error):
    """Handle not found error."""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server error."""
    logger.error(f"Internal error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("KMZ MERGE & GENERATION API")
    print("=" * 80)
    print(f"\nStarting Flask server...")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print(f"Max CSV size: {MAX_CSV_SIZE_MB}MB")
    print(f"Max KMZ size: {MAX_KMZ_SIZE_MB}MB")
    print("\nAPI Endpoints:")
    print("  POST   /upload         - Upload CSV and KMZ files")
    print("  POST   /generate       - Start processing job")
    print("  GET    /status/<id>    - Check job status")
    print("  GET    /download/<id>  - Download generated files")
    print("  GET    /jobs           - List all jobs")
    print("  GET    /health         - Health check")
    print("\n" + "=" * 80 + "\n")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
