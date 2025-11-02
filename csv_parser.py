"""
CSV Parser Module
Parse and validate Placer.ai Ranking Index CSV files.

This module handles:
- Reading CSV files with proper encoding detection
- Validating CSV structure and required columns
- Cleaning and normalizing data
- Filtering by state selections
- Handling multiple CSV files
- Error handling and reporting

Expected CSV Structure (Placer.ai Ranking Index):
- Rank, Id, Type, Property Name, Store Id, Chain Id, Chain Name
- Latitude, Longitude, Sub Category, Category, Category Group
- Address, City, State, State Code, Country, Country Code, Zip Code
- DMA Name, DMA Code, CBSA Name, CBSA Code
- Visits, sq ft, Visits / sq ft

Author: System
Date: November 2, 2025
Version: 1.0
"""

import csv
import logging
from typing import List, Dict, Set, Optional, Tuple
import chardet

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Required columns in Placer.ai CSV
REQUIRED_COLUMNS = [
    'Rank',
    'Property Name',
    'Latitude',
    'Longitude',
    'City',
    'State',
    'State Code',
    'Zip Code'
]

# Optional but commonly used columns
OPTIONAL_COLUMNS = [
    'Id',
    'Store Id',
    'Chain Id',
    'Chain Name',
    'Address',
    'Visits',
    'sq ft',
    'Visits / sq ft',
    'Type',
    'Category',
    'Country',
    'Country Code'
]


def parse_csv(csv_file_path, encoding='utf-8-sig'):
    """
    Parse a Placer.ai CSV file and return location data.
    
    Args:
        csv_file_path (str): Path to the CSV file
        encoding (str): File encoding (default: 'utf-8-sig' for Excel CSVs with BOM)
    
    Returns:
        list: List of dicts, each representing a location with all CSV columns
    
    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV structure is invalid or required columns missing
    """
    logger.info(f"Parsing CSV file: {csv_file_path}")
    
    # Detect encoding if not specified or if default fails
    if encoding == 'auto':
        encoding = detect_encoding(csv_file_path)
        logger.info(f"Detected encoding: {encoding}")
    
    locations = []
    
    try:
        with open(csv_file_path, 'r', encoding=encoding, errors='replace') as csvfile:
            # Use csv.DictReader to automatically parse headers
            reader = csv.DictReader(csvfile)
            
            # Validate headers
            if not reader.fieldnames:
                raise ValueError("CSV file appears to be empty or has no headers")
            
            validate_csv_headers(reader.fieldnames)
            
            # Read all rows
            row_count = 0
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
                try:
                    # Clean and validate row
                    cleaned_row = clean_csv_row(row)
                    
                    # Skip empty rows
                    if not cleaned_row.get('Property Name'):
                        logger.debug(f"Skipping empty row {row_num}")
                        continue
                    
                    # Add row number for debugging
                    cleaned_row['_row_number'] = row_num
                    
                    locations.append(cleaned_row)
                    row_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error parsing row {row_num}: {str(e)}")
                    continue
        
        logger.info(f"Successfully parsed {row_count} locations from CSV")
        
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error: {str(e)}. Try 'auto' encoding detection.")
        raise ValueError(f"Unable to read CSV file with encoding {encoding}. "
                        f"File may be in a different encoding.")
    
    except Exception as e:
        logger.error(f"Error parsing CSV: {str(e)}")
        raise
    
    return locations


def validate_csv_headers(headers):
    """
    Validate that CSV has all required columns.
    
    Args:
        headers (list): List of column names from CSV
    
    Raises:
        ValueError: If required columns are missing
    """
    headers_set = set(headers)
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in headers_set]
    
    if missing_columns:
        raise ValueError(
            f"CSV is missing required columns: {', '.join(missing_columns)}. "
            f"This does not appear to be a valid Placer.ai Ranking Index export."
        )
    
    logger.debug(f"CSV validation passed. Found {len(headers)} columns.")


def clean_csv_row(row):
    """
    Clean and normalize a CSV row.
    
    - Strip whitespace from string fields
    - Convert numeric fields to proper types
    - Handle empty/null values
    - Normalize state codes to uppercase
    
    Args:
        row (dict): Raw CSV row
    
    Returns:
        dict: Cleaned row
    """
    cleaned = {}
    
    for key, value in row.items():
        # Strip whitespace
        if isinstance(value, str):
            value = value.strip()
        
        # Handle empty values
        if value == '' or value is None:
            cleaned[key] = None
            continue
        
        # Convert specific fields to appropriate types
        if key == 'Rank':
            try:
                cleaned[key] = int(value)
            except (ValueError, TypeError):
                cleaned[key] = None
        
        elif key in ['Latitude', 'Longitude', 'Visits', 'sq ft', 'Visits / sq ft']:
            try:
                cleaned[key] = float(value)
            except (ValueError, TypeError):
                cleaned[key] = None
        
        elif key == 'State Code':
            # Normalize to uppercase
            cleaned[key] = value.upper()
        
        else:
            cleaned[key] = value
    
    return cleaned


def detect_encoding(file_path):
    """
    Detect the encoding of a CSV file.
    
    Args:
        file_path (str): Path to the CSV file
    
    Returns:
        str: Detected encoding (e.g., 'utf-8', 'utf-8-sig', 'iso-8859-1')
    """
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)  # Read first 10KB for detection
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        
        # Handle UTF-8 with BOM (common in Excel exports)
        if encoding and encoding.lower().startswith('utf-8'):
            encoding = 'utf-8-sig'
        
        return encoding or 'utf-8'


def filter_by_states(locations, selected_states):
    """
    Filter locations to only include selected states.
    
    Args:
        locations (list): List of location dicts
        selected_states (list or set): List of state codes (e.g., ['GA', 'FL'])
    
    Returns:
        list: Filtered locations
    """
    if not selected_states:
        return locations
    
    # Normalize state codes to uppercase
    selected_states_upper = {state.upper() for state in selected_states}
    
    filtered = [
        loc for loc in locations 
        if loc.get('State Code', '').upper() in selected_states_upper
    ]
    
    logger.info(f"Filtered {len(locations)} locations to {len(filtered)} "
                f"for states: {', '.join(sorted(selected_states_upper))}")
    
    return filtered


def get_available_states(locations):
    """
    Get list of unique states present in locations.
    
    Args:
        locations (list): List of location dicts
    
    Returns:
        list: Sorted list of unique state codes
    """
    states = {loc.get('State Code') for loc in locations if loc.get('State Code')}
    return sorted(list(states))


def parse_multiple_csv_files(csv_file_paths, state_selections=None):
    """
    Parse multiple CSV files and optionally filter by state selections.
    
    Args:
        csv_file_paths (list): List of paths to CSV files
        state_selections (dict): Optional dict mapping filename -> list of states
            Example: {'retailer1.csv': ['GA', 'FL'], 'retailer2.csv': ['GA', 'SC']}
    
    Returns:
        dict: Dictionary with keys:
            - all_locations (list): All parsed locations
            - by_file (dict): Locations grouped by source file
            - by_state (dict): Locations grouped by state
            - stats (dict): Statistics about parsing
    """
    all_locations = []
    by_file = {}
    by_state = {}
    stats = {
        'total_files': len(csv_file_paths),
        'files_processed': 0,
        'files_failed': 0,
        'total_locations': 0,
        'errors': []
    }
    
    for csv_path in csv_file_paths:
        try:
            # Get filename for state selection lookup
            import os
            filename = os.path.basename(csv_path)
            
            # Parse CSV
            locations = parse_csv(csv_path)
            
            # Apply state filter if specified for this file
            if state_selections and filename in state_selections:
                selected_states = state_selections[filename]
                locations = filter_by_states(locations, selected_states)
            
            # Add source file to each location
            for loc in locations:
                loc['_source_file'] = filename
            
            # Store by file
            by_file[filename] = locations
            
            # Group by state
            for loc in locations:
                state = loc.get('State Code', 'Unknown')
                if state not in by_state:
                    by_state[state] = []
                by_state[state].append(loc)
            
            # Add to all locations
            all_locations.extend(locations)
            
            stats['files_processed'] += 1
            logger.info(f"Successfully processed {filename}: {len(locations)} locations")
            
        except Exception as e:
            stats['files_failed'] += 1
            error_msg = f"Failed to process {csv_path}: {str(e)}"
            stats['errors'].append(error_msg)
            logger.error(error_msg)
    
    stats['total_locations'] = len(all_locations)
    
    return {
        'all_locations': all_locations,
        'by_file': by_file,
        'by_state': by_state,
        'stats': stats
    }


def validate_csv_file(csv_file_path, max_size_mb=50):
    """
    Validate that a file is a valid CSV and meets requirements.
    
    Args:
        csv_file_path (str): Path to the CSV file
        max_size_mb (int): Maximum file size in megabytes (default: 50MB)
    
    Returns:
        tuple: (is_valid, error_message)
            - is_valid (bool): True if file is valid
            - error_message (str): Error description if invalid, None if valid
    """
    import os
    
    # Check if file exists
    if not os.path.exists(csv_file_path):
        return False, "File does not exist"
    
    # Check file extension
    if not csv_file_path.lower().endswith('.csv'):
        return False, "File is not a CSV file (must have .csv extension)"
    
    # Check file size
    file_size_mb = os.path.getsize(csv_file_path) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        return False, f"File size ({file_size_mb:.1f}MB) exceeds maximum ({max_size_mb}MB)"
    
    # Try to parse first few rows
    try:
        locations = parse_csv(csv_file_path)
        
        if len(locations) == 0:
            return False, "CSV file contains no valid location data"
        
        # Check for required data in first location
        first_loc = locations[0]
        if not first_loc.get('Latitude') or not first_loc.get('Longitude'):
            return False, "CSV locations are missing coordinate data"
        
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error parsing CSV: {str(e)}"
    
    return True, None


def get_csv_preview(csv_file_path, num_rows=5):
    """
    Get a preview of CSV data for display to user.
    
    Args:
        csv_file_path (str): Path to the CSV file
        num_rows (int): Number of rows to preview (default: 5)
    
    Returns:
        dict: Preview data including:
            - total_locations (int): Total number of locations in file
            - states (list): List of unique states
            - preview_locations (list): First N locations
            - columns (list): List of column names
    """
    try:
        locations = parse_csv(csv_file_path)
        
        return {
            'total_locations': len(locations),
            'states': get_available_states(locations),
            'preview_locations': locations[:num_rows],
            'columns': list(locations[0].keys()) if locations else [],
            'has_metrics': any(loc.get('Visits') for loc in locations[:10])
        }
        
    except Exception as e:
        logger.error(f"Error getting CSV preview: {str(e)}")
        return {
            'total_locations': 0,
            'states': [],
            'preview_locations': [],
            'columns': [],
            'error': str(e)
        }


def export_to_csv(locations, output_path, columns=None):
    """
    Export locations back to CSV format.
    
    Args:
        locations (list): List of location dicts
        output_path (str): Path for output CSV file
        columns (list): Optional list of columns to include (None = all)
    
    Returns:
        str: Path to created file
    """
    if not locations:
        raise ValueError("No locations to export")
    
    # Determine columns to export
    if columns is None:
        # Use all columns from first location
        columns = list(locations[0].keys())
    
    # Remove internal columns (starting with _)
    columns = [col for col in columns if not col.startswith('_')]
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(locations)
    
    logger.info(f"Exported {len(locations)} locations to {output_path}")
    
    return output_path


# Example usage and testing
if __name__ == "__main__":
    import sys
    import os
    
    if len(sys.argv) < 2:
        print("Usage: python csv_parser.py <path_to_csv_file>")
        print("\nExample:")
        print("  python csv_parser.py placer_ai_export.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    
    print("\n" + "=" * 80)
    print("CSV PARSER TEST")
    print("=" * 80 + "\n")
    
    # Validate file
    print("1. Validating CSV file...")
    is_valid, error = validate_csv_file(csv_path)
    if not is_valid:
        print(f"   ❌ Validation failed: {error}")
        sys.exit(1)
    print("   ✓ File is valid")
    
    # Get preview
    print("\n2. Getting CSV preview...")
    preview = get_csv_preview(csv_path, num_rows=5)
    
    if 'error' in preview:
        print(f"   ❌ Error: {preview['error']}")
        sys.exit(1)
    
    print(f"   Total locations: {preview['total_locations']}")
    print(f"   States: {', '.join(preview['states'])}")
    print(f"   Columns: {len(preview['columns'])}")
    print(f"   Has metrics: {'Yes' if preview['has_metrics'] else 'No'}")
    
    # Show sample locations
    if preview['preview_locations']:
        print("\n   Sample locations:")
        for loc in preview['preview_locations']:
            print(f"   - {loc.get('Property Name')} "
                  f"({loc.get('City')}, {loc.get('State Code')})")
    
    # Parse full file
    print("\n3. Parsing full CSV file...")
    locations = parse_csv(csv_path)
    print(f"   ✓ Parsed {len(locations)} locations")
    
    # Get statistics
    print("\n4. Location statistics:")
    states = get_available_states(locations)
    print(f"   Unique states: {len(states)}")
    
    # Count by state
    from collections import Counter
    state_counts = Counter(loc.get('State Code') for loc in locations)
    print("\n   Top 10 states by location count:")
    for state, count in state_counts.most_common(10):
        print(f"   {state:4} {count:5} locations")
    
    # Data quality checks
    print("\n5. Data quality checks:")
    missing_coords = sum(1 for loc in locations 
                        if not loc.get('Latitude') or not loc.get('Longitude'))
    missing_city = sum(1 for loc in locations if not loc.get('City'))
    missing_address = sum(1 for loc in locations if not loc.get('Address'))
    
    print(f"   Missing coordinates: {missing_coords}")
    print(f"   Missing city: {missing_city}")
    print(f"   Missing address: {missing_address}")
    
    # Test state filtering
    print("\n6. Testing state filtering...")
    if states:
        test_state = states[0]
        filtered = filter_by_states(locations, [test_state])
        print(f"   Filtered to {test_state}: {len(filtered)} locations")
    
    # Test export
    print("\n7. Testing CSV export...")
    output_path = csv_path.replace('.csv', '_test_export.csv')
    export_to_csv(locations[:10], output_path)
    print(f"   ✓ Exported 10 locations to {output_path}")
    
    # Clean up test file
    if os.path.exists(output_path):
        os.remove(output_path)
        print(f"   ✓ Cleaned up test file")
    
    print("\n" + "=" * 80)
    print("✓ All tests complete!")
    print("=" * 80 + "\n")
