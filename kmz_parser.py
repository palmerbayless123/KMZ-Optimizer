"""
KMZ Parser Module
Parse existing KMZ files and extract location data, separating proposed from existing locations.

This module handles:
- Extracting KML from KMZ archives
- Parsing KML XML structure
- Identifying proposed/planned locations by markers in the name
- Extracting extended data fields
- Returning categorized location data

Author: System
Date: November 2, 2025
Version: 1.0
"""

from xml.etree import ElementTree as ET
from zipfile import ZipFile
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_kmz(kmz_file_path):
    """
    Parse KMZ file and extract all placemarks, categorizing them as proposed or existing.
    
    Args:
        kmz_file_path (str): Path to the KMZ file
    
    Returns:
        tuple: (proposed_locations, existing_locations)
            - proposed_locations (list): List of dicts with locations marked as proposed/U/C
            - existing_locations (list): List of dicts with locations not marked as proposed
    
    Raises:
        FileNotFoundError: If KMZ file doesn't exist
        zipfile.BadZipFile: If file is not a valid KMZ/ZIP
        ET.ParseError: If KML content is invalid XML
    """
    if not os.path.exists(kmz_file_path):
        raise FileNotFoundError(f"KMZ file not found: {kmz_file_path}")
    
    proposed = []
    existing = []
    
    try:
        # Extract KML from KMZ (KMZ is just a ZIP file with KML inside)
        with ZipFile(kmz_file_path, 'r') as kmz:
            # Look for doc.kml (standard name) or any .kml file
            kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]
            
            if not kml_files:
                raise ValueError("No KML file found in KMZ archive")
            
            # Use doc.kml if it exists, otherwise use first .kml file
            kml_filename = 'doc.kml' if 'doc.kml' in kml_files else kml_files[0]
            kml_content = kmz.read(kml_filename)
        
        # Parse XML
        root = ET.fromstring(kml_content)
        
        # Define namespace (KML uses this namespace)
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # Extract all placemarks
        placemarks = root.findall('.//kml:Placemark', ns)
        logger.info(f"Found {len(placemarks)} placemarks in KMZ file")
        
        for placemark in placemarks:
            location = extract_placemark_data(placemark, ns)
            
            # Check if this is a proposed location
            if is_proposed_location(location['name']):
                proposed.append(location)
                logger.debug(f"Proposed location: {location['name']}")
            else:
                existing.append(location)
                logger.debug(f"Existing location: {location['name']}")
        
        logger.info(f"Categorized: {len(proposed)} proposed, {len(existing)} existing")
        
    except Exception as e:
        logger.error(f"Error parsing KMZ file: {str(e)}")
        raise
    
    return proposed, existing


def is_proposed_location(name):
    """
    Check if location name indicates it's proposed/planned/under construction.
    
    Args:
        name (str): Location name from placemark
    
    Returns:
        bool: True if location is marked as proposed, False otherwise
    """
    if not name:
        return False
    
    name_lower = name.lower()
    
    # Check for common indicators of proposed/planned locations
    indicators = [
        '(proposed)',
        '(u/c)',
        'under construction',
        '(planned)',
        '(future)',
        '(coming soon)',
        '(opening soon)',
        '(in development)',
        '(pending)',
        '(future site)',
    ]
    
    return any(indicator in name_lower for indicator in indicators)


def extract_placemark_data(placemark, namespace):
    """
    Extract all relevant data from a KML Placemark element.
    
    This handles the specific structure used in Google Earth exports where:
    - Name can be in <n> or <name> tags
    - Coordinates are in <coordinates> tag as "lon,lat,alt"
    - Extended data is in <SimpleData> elements
    
    Args:
        placemark (ET.Element): XML Element representing a KML Placemark
        namespace (dict): Dictionary with KML namespace mapping
    
    Returns:
        dict: Location data with standardized keys:
            - name (str): Location name
            - latitude (float): Latitude coordinate
            - longitude (float): Longitude coordinate
            - address (str): Street address
            - city (str): City name
            - state (str): State code
            - zip (str): Zip code
            - year_opened (str): Year opened or planned
            - web_link (str): Website link if available
            - extended_data (dict): All SimpleData fields preserved
            - original_xml (ET.Element): Original XML element for reference
    """
    ns = namespace
    
    # Extract name - try <n> first (used by some exports), then <name>
    name_elem = placemark.find('kml:n', ns)
    if name_elem is None:
        name_elem = placemark.find('kml:name', ns)
    name = name_elem.text if name_elem is not None else "Unknown"
    
    # Extract coordinates from <Point><coordinates>
    coords_elem = placemark.find('.//kml:coordinates', ns)
    coords_text = coords_elem.text.strip() if coords_elem is not None else "0,0,0"
    
    # Parse coordinates (format: "longitude,latitude,altitude")
    try:
        parts = coords_text.split(',')
        lon = float(parts[0]) if len(parts) > 0 else 0.0
        lat = float(parts[1]) if len(parts) > 1 else 0.0
    except (ValueError, IndexError) as e:
        logger.warning(f"Invalid coordinates for {name}: {coords_text}")
        lon, lat = 0.0, 0.0
    
    # Extract extended data (SimpleData elements)
    extended_data = {}
    for simple_data in placemark.findall('.//kml:SimpleData', ns):
        field_name = simple_data.get('name')
        field_value = simple_data.text if simple_data.text else ''
        extended_data[field_name] = field_value
    
    # Build standardized location dictionary
    location = {
        'name': name,
        'latitude': lat,
        'longitude': lon,
        'address': extended_data.get('Address', ''),
        'city': extended_data.get('City', ''),
        'state': extended_data.get('State', ''),
        'zip': extended_data.get('Zip', ''),
        'year_opened': extended_data.get('Year_opened', ''),
        'web_link': extended_data.get('Web_Link', ''),
        'extended_data': extended_data,  # Keep all fields
        'original_xml': placemark  # Keep original for reference/debugging
    }
    
    return location


def get_kmz_stats(kmz_file_path):
    """
    Get quick statistics about a KMZ file without full parsing.
    Useful for showing preview/stats to user before processing.
    
    Args:
        kmz_file_path (str): Path to the KMZ file
    
    Returns:
        dict: Statistics including:
            - total_placemarks (int): Total number of placemarks
            - proposed_count (int): Number of proposed locations
            - existing_count (int): Number of existing locations
            - has_extended_data (bool): Whether placemarks have extended data
    """
    try:
        proposed, existing = parse_kmz(kmz_file_path)
        
        stats = {
            'total_placemarks': len(proposed) + len(existing),
            'proposed_count': len(proposed),
            'existing_count': len(existing),
            'has_extended_data': any('extended_data' in loc and loc['extended_data'] 
                                    for loc in proposed + existing),
            'states': sorted(list(set(
                loc['state'] for loc in proposed + existing 
                if loc.get('state')
            ))),
            'cities': sorted(list(set(
                f"{loc['city']}, {loc['state']}" for loc in proposed + existing 
                if loc.get('city') and loc.get('state')
            )))[:20]  # Limit to 20 cities for preview
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting KMZ stats: {str(e)}")
        return {
            'total_placemarks': 0,
            'proposed_count': 0,
            'existing_count': 0,
            'has_extended_data': False,
            'states': [],
            'cities': [],
            'error': str(e)
        }


def validate_kmz_file(kmz_file_path, max_size_mb=10):
    """
    Validate that a file is a valid KMZ and meets size requirements.
    
    Args:
        kmz_file_path (str): Path to the KMZ file
        max_size_mb (int): Maximum file size in megabytes (default: 10MB)
    
    Returns:
        tuple: (is_valid, error_message)
            - is_valid (bool): True if file is valid
            - error_message (str): Error description if invalid, None if valid
    """
    # Check if file exists
    if not os.path.exists(kmz_file_path):
        return False, "File does not exist"
    
    # Check file size
    file_size_mb = os.path.getsize(kmz_file_path) / (1024 * 1024)
    if file_size_mb > max_size_mb:
        return False, f"File size ({file_size_mb:.1f}MB) exceeds maximum ({max_size_mb}MB)"
    
    # Check if it's a valid ZIP file
    try:
        with ZipFile(kmz_file_path, 'r') as kmz:
            # Check for KML file
            kml_files = [f for f in kmz.namelist() if f.endswith('.kml')]
            if not kml_files:
                return False, "No KML file found in KMZ archive"
    except Exception as e:
        return False, f"Invalid KMZ file: {str(e)}"
    
    # Try to parse the KML
    try:
        proposed, existing = parse_kmz(kmz_file_path)
        if len(proposed) + len(existing) == 0:
            return False, "No placemarks found in KMZ file"
    except Exception as e:
        return False, f"Error parsing KML: {str(e)}"
    
    return True, None


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python kmz_parser.py <path_to_kmz_file>")
        print("\nExample:")
        print("  python kmz_parser.py coffee_shops.kmz")
        sys.exit(1)
    
    kmz_path = sys.argv[1]
    
    print(f"\n{'='*60}")
    print(f"KMZ PARSER TEST")
    print(f"{'='*60}\n")
    
    # Validate file
    print("1. Validating KMZ file...")
    is_valid, error = validate_kmz_file(kmz_path)
    if not is_valid:
        print(f"   ❌ Validation failed: {error}")
        sys.exit(1)
    print("   ✓ File is valid")
    
    # Get stats
    print("\n2. Getting KMZ statistics...")
    stats = get_kmz_stats(kmz_path)
    print(f"   Total placemarks: {stats['total_placemarks']}")
    print(f"   Proposed locations: {stats['proposed_count']}")
    print(f"   Existing locations: {stats['existing_count']}")
    print(f"   States: {', '.join(stats['states'])}")
    if stats['cities']:
        print(f"   Sample cities: {', '.join(stats['cities'][:5])}")
    
    # Parse and show details
    print("\n3. Parsing KMZ file...")
    proposed, existing = parse_kmz(kmz_path)
    
    if proposed:
        print(f"\n   Proposed locations ({len(proposed)}):")
        for loc in proposed[:5]:  # Show first 5
            print(f"   - {loc['name']}")
            print(f"     {loc['city']}, {loc['state']} ({loc['latitude']:.4f}, {loc['longitude']:.4f})")
        if len(proposed) > 5:
            print(f"   ... and {len(proposed) - 5} more")
    
    if existing:
        print(f"\n   Existing locations ({len(existing)}):")
        for loc in existing[:5]:  # Show first 5
            print(f"   - {loc['name']}")
            print(f"     {loc['city']}, {loc['state']} ({loc['latitude']:.4f}, {loc['longitude']:.4f})")
        if len(existing) > 5:
            print(f"   ... and {len(existing) - 5} more")
    
    print(f"\n{'='*60}")
    print("✓ Parsing complete!")
    print(f"{'='*60}\n")
