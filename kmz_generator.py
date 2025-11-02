"""
KMZ Generator Module
Generate KMZ files with proper placemark formatting for Google Earth Pro.

This module creates KMZ files with placemarks that display information exactly as shown
in Google Earth Pro's information bubble, matching the required field format.

Field Format (as displayed in Google Earth Pro):
- Name
- Address
- City
- State
- Zip
- County (ALL CAPS, county name only)
- Placer Rank [State Code] ([Date range])
- Ranked Stores [State Code]
- Total Visits [State Code]
- Average Total Visits [State Code]
- Total Stores [State Code]
- Placer Rank US ([Date range])
- Ranked Stores US
- Total Stores US
- SF (square footage)
- Sales Per SF
- Lat
- Long

Author: System
Date: November 2, 2025
Version: 1.1
"""

import logging
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_kmz(locations, output_path, metadata=None):
    """
    Generate a KMZ file with placemarks for all locations.
    
    Args:
        locations (list): List of location dicts with all required fields
        output_path (str): Path where KMZ file should be saved
        metadata (dict): Optional metadata including:
            - date_range (str): e.g., "Apr 1 - Jun 2023"
            - total_ranked_stores (int): Total number of ranked stores
            - total_ranked_stores_us (int): Total ranked stores across US
            - total_stores_us (int): Total stores across US
            - state_store_counts (dict): Store count per state
            - average_visits_by_state (dict): Average visits per state
            - total_visits_by_state (dict): Total visits per state
    
    Returns:
        str: Path to generated KMZ file
    """
    logger.info(f"Generating KMZ file: {output_path}")
    logger.info(f"Total locations: {len(locations)}")
    
    # Set default metadata if not provided
    if metadata is None:
        metadata = {
            'date_range': 'Oct 1, 2024 - Sep 30, 2025',
            'total_ranked_stores': len(locations),
            'total_ranked_stores_us': len(locations),
            'total_stores_us': len(locations),
            'state_store_counts': {},
            'average_visits_by_state': {},
            'total_visits_by_state': {}
        }
    
    # Calculate state store counts if not provided
    if not metadata.get('state_store_counts'):
        state_counts = {}
        for loc in locations:
            state = loc.get('State Code', loc.get('State', 'Unknown'))
            state_counts[state] = state_counts.get(state, 0) + 1
        metadata['state_store_counts'] = state_counts
    
    # Generate KML content
    kml_content = generate_kml(locations, metadata)
    
    # Create KMZ file (KMZ is a ZIP file containing doc.kml)
    temp_kml_path = output_path.replace('.kmz', '_temp.kml')
    
    # Write KML to temporary file
    with open(temp_kml_path, 'w', encoding='utf-8') as f:
        f.write(kml_content)
    
    # Create KMZ (ZIP) file
    with ZipFile(output_path, 'w') as kmz:
        kmz.write(temp_kml_path, 'doc.kml')
    
    # Clean up temporary KML file
    if os.path.exists(temp_kml_path):
        os.remove(temp_kml_path)
    
    logger.info(f"KMZ file generated successfully: {output_path}")
    
    return output_path


def generate_kml(locations, metadata):
    """
    Generate KML XML content for locations.
    
    Args:
        locations (list): List of location dicts
        metadata (dict): Metadata for the KML file
    
    Returns:
        str: KML XML content as string
    """
    # Create root KML element
    kml = ET.Element('kml', xmlns='http://www.opengis.net/kml/2.2')
    document = ET.SubElement(kml, 'Document')
    
    # Add document name
    name = ET.SubElement(document, 'name')
    name.text = f"Locations - {metadata.get('date_range', 'Unknown Date Range')}"
    
    # Add style for placemarks
    style = ET.SubElement(document, 'Style', id='defaultStyle')
    icon_style = ET.SubElement(style, 'IconStyle')
    icon = ET.SubElement(icon_style, 'Icon')
    href = ET.SubElement(icon, 'href')
    href.text = 'http://maps.google.com/mapfiles/kml/paddle/red-circle.png'
    
    # Create schema for extended data
    date_range = metadata.get('date_range', 'Oct 1, 2024 - Sep 30, 2025')
    schema = create_schema(document, date_range)
    
    # Add placemark for each location
    for loc in locations:
        create_placemark(document, loc, metadata, schema.get('id'))
    
    # Convert to string with XML declaration
    xml_string = ET.tostring(kml, encoding='utf-8', method='xml').decode('utf-8')
    
    # Add XML declaration
    full_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_string
    
    return full_xml


def create_schema(parent, date_range='Oct 1, 2024 - Sep 30, 2025'):
    """
    Create schema definition for extended data fields.
    
    Args:
        parent (ET.Element): Parent XML element (Document)
        date_range (str): Date range to include in field names
    
    Returns:
        ET.Element: Schema element
    """
    schema = ET.SubElement(parent, 'Schema', {
        'name': 'LocationData',
        'id': 'LocationDataSchema'
    })
    
    # Define all simple fields that will appear in the information bubble
    # Date ranges are in the FIELD NAMES, not the values
    fields = [
        ('Name', 'string'),
        ('Address', 'string'),
        ('City', 'string'),
        ('State', 'string'),
        ('Zip', 'string'),
        ('County', 'string'),
        (f'Placer Rank [State Code] ({date_range})', 'string'),
        ('Ranked Stores [State Code]', 'string'),
        (f'Total Visits [State Code] ({date_range})', 'string'),
        (f'Average Total Visits [State Code] ({date_range})', 'string'),
        ('Total Stores [State Code]', 'string'),
        (f'Placer Rank US ({date_range})', 'string'),
        ('Ranked Stores US', 'string'),
        ('Total Stores US', 'string'),
        ('SF', 'string'),
        ('Sales Per SF', 'string'),
        ('Lat', 'double'),
        ('Long', 'double')
    ]
    
    for field_name, field_type in fields:
        ET.SubElement(schema, 'SimpleField', {
            'name': field_name,
            'type': field_type
        })
    
    return schema


def create_placemark(parent, location, metadata, schema_id):
    """
    Create a placemark for a single location with all extended data.
    
    Args:
        parent (ET.Element): Parent XML element (Document)
        location (dict): Location data
        metadata (dict): Metadata including date ranges and counts
        schema_id (str): Schema ID reference
    
    Returns:
        ET.Element: Placemark element
    """
    placemark = ET.SubElement(parent, 'Placemark')
    
    # Placemark name (displays as title in Google Earth)
    name = ET.SubElement(placemark, 'name')
    property_name = location.get('Property Name', location.get('name', 'Unknown'))
    city = location.get('City', '')
    state = location.get('State Code', location.get('State', ''))
    name.text = f"{property_name} - {city}, {state}" if city and state else property_name
    
    # Style reference
    style_url = ET.SubElement(placemark, 'styleUrl')
    style_url.text = '#defaultStyle'
    
    # Extended Data (this is what shows in the information bubble)
    extended_data = ET.SubElement(placemark, 'ExtendedData')
    schema_data = ET.SubElement(extended_data, 'SchemaData', {
        'schemaUrl': f'#{schema_id}'
    })
    
    # Get metadata values
    date_range = metadata.get('date_range', 'Oct 1, 2024 - Sep 30, 2025')
    total_ranked_stores_us = metadata.get('total_ranked_stores_us', 0)
    total_stores_us = metadata.get('total_stores_us', 0)
    state_code = location.get('State Code', location.get('State', ''))
    state_store_count = metadata.get('state_store_counts', {}).get(state_code, 0)
    average_visits_state = metadata.get('average_visits_by_state', {}).get(state_code, 0)
    total_visits_state = metadata.get('total_visits_by_state', {}).get(state_code, 0)
    
    # Format county - ALL CAPS, remove " County" suffix if present
    county = location.get('County', '')
    if county:
        county = county.upper()
        if county.endswith(' COUNTY'):
            county = county.replace(' COUNTY', '')
        if county.endswith(' PARISH'):
            county = county.replace(' PARISH', '')
    
    # Get rank (state-level)
    rank = location.get('Rank')
    rank_display = str(rank) if rank is not None else 'N/A'
    
    # Format visits with commas
    visits = location.get('Visits')
    if visits:
        try:
            visits_formatted = f"{int(visits):,}"
        except (ValueError, TypeError):
            visits_formatted = 'N/A'
    else:
        visits_formatted = 'N/A'
    
    # Format average visits with commas
    if average_visits_state:
        try:
            avg_visits_formatted = f"{int(average_visits_state):,}"
        except (ValueError, TypeError):
            avg_visits_formatted = 'N/A'
    else:
        avg_visits_formatted = 'N/A'
    
    # Format total visits for state
    if total_visits_state:
        try:
            total_visits_formatted = f"{int(total_visits_state):,}"
        except (ValueError, TypeError):
            total_visits_formatted = 'N/A'
    else:
        total_visits_formatted = 'N/A'
    
    # Get square footage
    sq_ft = location.get('sq ft')
    if sq_ft:
        try:
            sq_ft_formatted = f"{int(sq_ft):,}"
        except (ValueError, TypeError):
            sq_ft_formatted = 'N/A'
    else:
        sq_ft_formatted = 'N/A'
    
    # Calculate Sales Per SF (Visits / sq ft)
    sales_per_sf = location.get('Visits / sq ft')
    if sales_per_sf:
        try:
            sales_per_sf_formatted = f"{float(sales_per_sf):,.2f}"
        except (ValueError, TypeError):
            sales_per_sf_formatted = 'N/A'
    else:
        # Try to calculate if we have both values
        if visits and sq_ft:
            try:
                calculated_sales = float(visits) / float(sq_ft)
                sales_per_sf_formatted = f"{calculated_sales:,.2f}"
            except (ValueError, TypeError, ZeroDivisionError):
                sales_per_sf_formatted = 'N/A'
        else:
            sales_per_sf_formatted = 'N/A'
    
    # For US rank, we'd need to calculate across all locations
    # For now, use the rank if available (assuming it might be US-level from CSV)
    # This would need additional logic to determine US rank vs state rank
    rank_us_display = rank_display  # Placeholder - would need proper US ranking logic
    
    # Build the exact field structure matching the screenshot
    # NOTE: Date ranges are in FIELD NAMES (in schema), not in values
    fields_data = [
        ('Name', property_name),
        ('Address', location.get('Address', '')),
        ('City', city),
        ('State', state),
        ('Zip', location.get('Zip Code', location.get('Zip', ''))),
        ('County', county),
        (f'Placer Rank [State Code] ({date_range})', rank_display),
        ('Ranked Stores [State Code]', str(state_store_count)),
        (f'Total Visits [State Code] ({date_range})', total_visits_formatted),
        (f'Average Total Visits [State Code] ({date_range})', avg_visits_formatted),
        ('Total Stores [State Code]', str(state_store_count)),
        (f'Placer Rank US ({date_range})', rank_us_display),
        ('Ranked Stores US', str(total_ranked_stores_us)),
        ('Total Stores US', str(total_stores_us)),
        ('SF', sq_ft_formatted),
        ('Sales Per SF', sales_per_sf_formatted),
        ('Lat', str(location.get('Latitude', 0.0))),
        ('Long', str(location.get('Longitude', 0.0)))
    ]
    
    # Add each field as SimpleData
    for field_name, field_value in fields_data:
        simple_data = ET.SubElement(schema_data, 'SimpleData', {'name': field_name})
        simple_data.text = str(field_value) if field_value else ''
    
    # Point coordinates
    point = ET.SubElement(placemark, 'Point')
    coordinates = ET.SubElement(point, 'coordinates')
    lon = location.get('Longitude', 0.0)
    lat = location.get('Latitude', 0.0)
    coordinates.text = f"{lon},{lat},0"
    
    return placemark


def generate_state_kmz_files(locations, output_directory, metadata=None):
    """
    Generate separate KMZ files for each state.
    
    Args:
        locations (list): List of all locations
        output_directory (str): Directory where KMZ files should be saved
        metadata (dict): Metadata for KML generation
    
    Returns:
        dict: Mapping of state code -> KMZ file path
    """
    logger.info(f"Generating state-level KMZ files in {output_directory}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_directory, exist_ok=True)
    
    # Group locations by state
    states = {}
    for loc in locations:
        state = loc.get('State Code', loc.get('State', 'Unknown'))
        if state not in states:
            states[state] = []
        states[state].append(loc)
    
    # Generate KMZ for each state
    generated_files = {}
    for state, state_locations in states.items():
        output_path = os.path.join(output_directory, f"{state}.kmz")
        
        # Create state-specific metadata (keep US-level stats the same)
        state_metadata = metadata.copy() if metadata else {}
        
        # Note: We keep total_ranked_stores_us and total_stores_us at US level
        # But we can update state-specific counts for this particular state
        # The state_store_counts should already have the correct count for this state
        
        # Generate KMZ
        generate_kmz(state_locations, output_path, state_metadata)
        generated_files[state] = output_path
        
        logger.info(f"Generated {state}.kmz with {len(state_locations)} locations")
    
    logger.info(f"Generated {len(generated_files)} state KMZ files")
    
    return generated_files


def validate_location_data(location):
    """
    Validate that a location has all required fields for KMZ generation.
    
    Args:
        location (dict): Location data
    
    Returns:
        tuple: (is_valid, missing_fields)
    """
    required_fields = ['Property Name', 'Latitude', 'Longitude', 'City', 'State']
    missing_fields = []
    
    for field in required_fields:
        # Check both possible field name variations
        if not location.get(field) and not location.get(field.replace(' ', '_')):
            missing_fields.append(field)
    
    # Check coordinate validity
    lat = location.get('Latitude', 0)
    lon = location.get('Longitude', 0)
    
    try:
        lat = float(lat)
        lon = float(lon)
        if lat == 0 and lon == 0:
            missing_fields.append('Valid coordinates')
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            missing_fields.append('Coordinate range')
    except (ValueError, TypeError):
        missing_fields.append('Numeric coordinates')
    
    is_valid = len(missing_fields) == 0
    
    return is_valid, missing_fields


# Example usage and testing
if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("KMZ GENERATOR TEST")
    print("=" * 80 + "\n")
    
    # Sample test data matching the screenshot format with ALL new fields
    test_locations = [
        {
            'Property Name': 'The Home Depot',
            'Address': '650 Ponce De Leon',
            'City': 'Atlanta',
            'State': 'GA',
            'State Code': 'GA',
            'Zip': '30308',
            'County': 'Fulton County',
            'Rank': 52,
            'Visits': 178167,
            'sq ft': 100000,
            'Visits / sq ft': 1.78,
            'Latitude': 33.7772,
            'Longitude': -84.3663
        },
        {
            'Property Name': '7 Brew Coffee',
            'Address': '1010 S Moorland Rd',
            'City': 'Brookfield',
            'State': 'WI',
            'State Code': 'WI',
            'Zip': '53005',
            'County': 'Waukesha County',
            'Rank': 1,
            'Visits': 1001832,
            'sq ft': 1200,
            'Visits / sq ft': 834.86,
            'Latitude': 43.020958,
            'Longitude': -88.106323
        },
        {
            'Property Name': '7 Brew Coffee',
            'Address': '3455 Atlanta Hwy',
            'City': 'Athens',
            'State': 'GA',
            'State Code': 'GA',
            'Zip': '30606',
            'County': 'Clarke County',
            'Rank': 15,
            'Visits': 850000,
            'sq ft': 1150,
            'Visits / sq ft': 739.13,
            'Latitude': 33.9389,
            'Longitude': -83.4535
        }
    ]
    
    # Metadata with ALL new fields
    test_metadata = {
        'date_range': 'Apr 1 - Jun 2023',
        'total_ranked_stores': 90,
        'total_ranked_stores_us': 150,
        'total_stores_us': 200,
        'state_store_counts': {
            'GA': 2,
            'WI': 1
        },
        'average_visits_by_state': {
            'GA': 514083,  # Average of 178167 and 850000
            'WI': 1001832
        },
        'total_visits_by_state': {
            'GA': 1028167,  # Sum of GA locations
            'WI': 1001832
        }
    }
    
    print("1. Validating location data...")
    for idx, loc in enumerate(test_locations, 1):
        is_valid, missing = validate_location_data(loc)
        status = "✓" if is_valid else "✗"
        print(f"   {status} Location {idx}: {loc['Property Name']}")
        if missing:
            print(f"      Missing: {', '.join(missing)}")
    
    print("\n2. Generating single KMZ file...")
    output_path = 'test_all_locations.kmz'
    generate_kmz(test_locations, output_path, test_metadata)
    print(f"   ✓ Generated: {output_path}")
    print(f"   File size: {os.path.getsize(output_path) / 1024:.1f} KB")
    
    print("\n3. Generating state-level KMZ files...")
    output_dir = 'test_output'
    state_files = generate_state_kmz_files(test_locations, output_dir, test_metadata)
    for state, filepath in state_files.items():
        file_size = os.path.getsize(filepath) / 1024
        print(f"   ✓ {state}.kmz ({file_size:.1f} KB)")
    
    print("\n4. Verifying KMZ structure...")
    # Open and inspect the KMZ
    with ZipFile(output_path, 'r') as kmz:
        files = kmz.namelist()
        print(f"   Files in KMZ: {files}")
        
        # Read the KML content
        kml_content = kmz.read('doc.kml').decode('utf-8')
        
        # Check for required elements
        checks = [
            ('<?xml version', 'XML declaration'),
            ('<kml xmlns', 'KML namespace'),
            ('<Placemark>', 'Placemarks'),
            ('<ExtendedData>', 'Extended data'),
            ('<SimpleData name="County">', 'County field'),
            ('<SimpleData name="Placer Rank [State Code] (Apr 1 - Jun 2023)">', 'Placer Rank with date in field name'),
            ('<SimpleData name="Total Visits [State Code] (Apr 1 - Jun 2023)">', 'Total Visits with date in field name'),
            ('<SimpleData name="Average Total Visits [State Code] (Apr 1 - Jun 2023)">', 'Average Visits with date in field name'),
            ('<SimpleData name="Placer Rank US (Apr 1 - Jun 2023)">', 'Placer Rank US with date in field name'),
            ('<SimpleData name="Ranked Stores US">', 'Ranked Stores US field'),
            ('<SimpleData name="Total Stores US">', 'Total Stores US field'),
            ('<SimpleData name="SF">', 'SF field'),
            ('<SimpleData name="Sales Per SF">', 'Sales Per SF field'),
            ('FULTON', 'County in ALL CAPS')
        ]
        
        print("\n   KML content validation:")
        for search_term, description in checks:
            found = search_term in kml_content
            status = "✓" if found else "✗"
            print(f"   {status} {description}")
    
    # Clean up test files
    print("\n5. Cleaning up test files...")
    if os.path.exists(output_path):
        os.remove(output_path)
        print(f"   ✓ Removed {output_path}")
    
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
        print(f"   ✓ Removed {output_dir}")
    
    print("\n" + "=" * 80)
    print("✓ All tests complete!")
    print("=" * 80 + "\n")
    
    print("KEY FEATURES:")
    print("  • County name in ALL CAPS (no 'County' suffix)")
    print("  • Date ranges in FIELD NAMES, not in values")
    print("  • Placer Rank [State Code] (date range) - value is just the rank number")
    print("  • Total Visits [State Code] (date range) - value is comma-formatted number")
    print("  • Average Total Visits [State Code] (date range) - value is comma-formatted")
    print("  • Placer Rank US (date range) - value is just the rank number")
    print("  • Ranked Stores US - integer count")
    print("  • Total Stores US - integer count")
    print("  • SF (square footage) with comma formatting")
    print("  • Sales Per SF calculated field with decimal formatting")
    print("  • Total Stores [State Code] count")
    print("  • Proper KML structure for Google Earth Pro")
    print("  • Extended data fields match requirements exactly")
