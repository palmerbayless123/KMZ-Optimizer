# WEB APP DEVELOPMENT GUIDE
## KMZ Merge Functionality - Complete Implementation Specification

**Feature**: KMZ Upload with Smart Location Replacement  
**Purpose**: Merge manually-entered proposed locations with actual Placer.ai data  
**Complexity**: Medium (requires proximity matching and data merging)  
**Last Updated**: November 2, 2025  
**Version**: 2.0

---

## 🎯 BUSINESS REQUIREMENT

### The Problem

Users maintain KMZ files with proposed/planned locations for retailers:

- Marked as "**(proposed)**" or "**(U/C)**" (Under Construction) in the placemark name
- Manually entered based on business intelligence
- May have incomplete data (estimated coordinates, no metrics)
- `Year_opened` may be future (2025, 2026, etc.) or `0`

When Placer.ai releases fresh data (CSV export):

- New stores that were "proposed" are now actually operating
- Need to replace the placeholder data with real metrics
- Prevent duplicate markers for the same location

### The Solution

**Smart KMZ Merge**:

1. User uploads BOTH files:
   - Fresh Placer.ai CSV (actual operating stores)
   - Current KMZ (may contain proposed locations) - **OPTIONAL**
2. System identifies matches between CSV stores and KMZ "proposed" locations
3. When match found:
   - CSV data replaces the proposed placemark
   - Proposed placemark is deleted
   - No duplicate markers appear
4. All other locations (non-matching) remain in final output

---

## 📋 DATA STRUCTURE COMPARISON

### KMZ Proposed Location Structure

```xml
<Placemark>
    <n>7 Brew Coffee-Athens, GA (proposed)</n>
    <styleUrl>#pointStyleMap</styleUrl>
    <ExtendedData>
        <SchemaData schemaUrl="#S_Coffee___7_Brew__287_SSSSIDDII">
            <SimpleData name="Name">7 Brew Coffee-Athens, GA (proposed)</SimpleData>
            <SimpleData name="Address">3455 Atlanta Hwy</SimpleData>
            <SimpleData name="City">Athens</SimpleData>
            <SimpleData name="State">GA</SimpleData>
            <SimpleData name="Zip">30606</SimpleData>
            <SimpleData name="LAT">33.9389</SimpleData>
            <SimpleData name="LONG">-83.4535</SimpleData>
            <SimpleData name="Year_opened">2025</SimpleData>
            <SimpleData name="Web_Link">0</SimpleData>
        </SchemaData>
    </ExtendedData>
    <Point>
        <coordinates>-83.45347,33.93890999999999,0</coordinates>
    </Point>
</Placemark>
```

**Key Identifiers:**
- Name field contains `(proposed)`, `(U/C)`, or `Under Construction`
- May have `Year_opened` in future or `0`
- Limited data fields
- Manually entered

### CSV Actual Location Structure

```csv
Rank,Id,Type,Property Name,Store Id,Chain Id,Chain Name,Latitude,Longitude,
Sub Category,Category,Category Group,Address,City,State,State Code,Country,
Country Code,Zip Code,DMA Name,DMA Code,CBSA Name,CBSA Code,Visits,sq ft,
Visits / sq ft
```

**Key Identifiers:**
- Has Placer.ai unique `Id`
- Rich metrics (`Visits`, `sq ft`, `Rank`)
- Verified coordinates
- Currently operating

---

## 🔍 MATCHING ALGORITHM

### Matching Strategy

**Primary Match**: Geographic proximity + City match

```python
def is_match(csv_location, kmz_proposed_location):
    """
    Determine if CSV location matches KMZ proposed location
    
    Returns: (is_match: bool, confidence: float)
    """
    # 1. City must match (case-insensitive)
    if csv_location['City'].upper() != kmz_proposed_location['city'].upper():
        return False, 0.0
    
    # 2. State must match
    if csv_location['State Code'] != kmz_proposed_location['state']:
        return False, 0.0
    
    # 3. Calculate geographic distance
    distance_meters = haversine_distance(
        csv_location['Latitude'], 
        csv_location['Longitude'],
        kmz_proposed_location['lat'],
        kmz_proposed_location['long']
    )
    
    # 4. Match thresholds
    if distance_meters <= 50:  # Within 50 meters
        return True, 1.0
    elif distance_meters <= 200:  # Within 200 meters (likely same location)
        return True, 0.8
    elif distance_meters <= 500:  # Within 500 meters (possible match)
        return True, 0.6
    else:
        return False, 0.0
```

### Distance Calculation (Haversine Formula)

```python
from math import radians, sin, cos, sqrt, atan2

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two points on Earth in meters
    
    Args:
        lat1, lon1: First location (degrees)
        lat2, lon2: Second location (degrees)
    
    Returns:
        distance in meters
    """
    R = 6371000  # Earth's radius in meters
    
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    
    a = sin(delta_phi/2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c
```

### Match Confidence Levels

| Distance | Confidence | Action |
|----------|-----------|---------|
| ≤ 50m | 1.0 (100%) | Auto-replace |
| ≤ 200m | 0.8 (80%) | Auto-replace |
| ≤ 500m | 0.6 (60%) | Manual review (optional) |
| > 500m | 0.0 (0%) | No match |

---

## 🔄 MERGE WORKFLOW

### Step-by-Step Process

```
┌─────────────────────────────────────────────────────┐
│                  USER UPLOADS                       │
│  ┌─────────────────┐      ┌─────────────────┐     │
│  │  Fresh CSV      │      │  Current KMZ    │     │
│  │  (Placer.ai)    │      │  (Optional)     │     │
│  └─────────────────┘      └─────────────────┘     │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│              PARSE & CATEGORIZE                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  CSV: All actual operating locations         │  │
│  │  KMZ: Separate into two lists:               │  │
│  │    - Proposed locations (marked)             │  │
│  │    - Existing locations (not marked)         │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│              MATCHING PROCESS                       │
│  For each CSV location:                             │
│    For each KMZ proposed location:                  │
│      - Check city/state match                       │
│      - Calculate distance                           │
│      - If match found (≤200m):                      │
│        * Mark KMZ proposed for deletion             │
│        * CSV location will replace it               │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│              BUILD FINAL DATASET                    │
│  Combined locations:                                │
│    1. All CSV locations (with enriched data)        │
│    2. KMZ existing locations (not proposed)         │
│    3. KMZ proposed locations (no CSV match)         │
│                                                      │
│  Excluded:                                          │
│    - KMZ proposed locations that matched CSV        │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│              GENERATE OUTPUT                        │
│  - Process through normal pipeline                  │
│  - County lookup for all locations                  │
│  - Rank calculation (CSV locations only)            │
│  - Generate state-level KMZ files                   │
└─────────────────────────────────────────────────────┘
```

---

## 📁 UPDATED FILE STRUCTURE

### Backend Architecture

```
backend/
├── app.py                      # Main Flask application
├── processing/
│   ├── __init__.py
│   ├── csv_parser.py          # Parse Placer.ai CSV
│   ├── kmz_parser.py          # NEW: Parse existing KMZ files
│   ├── location_matcher.py    # NEW: Match CSV to KMZ proposed
│   ├── data_merger.py         # NEW: Merge datasets intelligently
│   ├── county_lookup.py       # County name from coordinates
│   ├── rank_calculator.py     # Calculate rankings
│   └── kmz_generator.py       # Generate final KMZ files
├── uploads/                    # Temporary file storage
└── outputs/                    # Generated KMZ files
```

### New Module: `kmz_parser.py`

```python
"""
Parse existing KMZ files and extract location data
"""
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import re

def parse_kmz(kmz_file_path):
    """
    Parse KMZ file and extract all placemarks
    
    Returns:
        tuple: (proposed_locations, existing_locations)
            - proposed_locations: list of dict (locations marked as proposed)
            - existing_locations: list of dict (locations not marked as proposed)
    """
    proposed = []
    existing = []
    
    # Extract KML from KMZ
    with ZipFile(kmz_file_path, 'r') as kmz:
        kml_content = kmz.read('doc.kml')
    
    # Parse XML
    root = ET.fromstring(kml_content)
    
    # Define namespace
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    # Extract all placemarks
    for placemark in root.findall('.//kml:Placemark', ns):
        location = extract_placemark_data(placemark, ns)
        
        # Check if proposed
        if is_proposed_location(location['name']):
            proposed.append(location)
        else:
            existing.append(location)
    
    return proposed, existing


def is_proposed_location(name):
    """
    Check if location name indicates it's proposed/planned
    
    Args:
        name: Location name string
    
    Returns:
        bool: True if location is marked as proposed
    """
    if not name:
        return False
        
    name_lower = name.lower()
    
    # Check for indicators
    indicators = [
        '(proposed)',
        '(u/c)',
        'under construction',
        '(planned)',
        '(future)',
        '(coming soon)',
        '(opening soon)'
    ]
    
    return any(indicator in name_lower for indicator in indicators)


def extract_placemark_data(placemark, namespace):
    """
    Extract all relevant data from a placemark
    
    Args:
        placemark: XML Element representing a KML Placemark
        namespace: Dict with KML namespace
    
    Returns:
        dict: Location data with standardized keys
    """
    ns = namespace
    
    # Extract name (using <n> tag as seen in 7 Brew KML)
    name_elem = placemark.find('kml:n', ns)
    if name_elem is None:
        name_elem = placemark.find('kml:name', ns)
    name = name_elem.text if name_elem is not None else "Unknown"
    
    # Extract coordinates
    coords_elem = placemark.find('.//kml:coordinates', ns)
    coords_text = coords_elem.text.strip() if coords_elem is not None else "0,0,0"
    parts = coords_text.split(',')
    lon = float(parts[0]) if len(parts) > 0 else 0.0
    lat = float(parts[1]) if len(parts) > 1 else 0.0
    
    # Extract extended data
    extended_data = {}
    for simple_data in placemark.findall('.//kml:SimpleData', ns):
        field_name = simple_data.get('name')
        field_value = simple_data.text if simple_data.text else ''
        extended_data[field_name] = field_value
    
    # Build location dict
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
        'extended_data': extended_data,
        'original_xml': placemark  # Keep for reference
    }
    
    return location
```

### New Module: `location_matcher.py`

```python
"""
Match CSV locations with KMZ proposed locations using geographic proximity
"""
from math import radians, sin, cos, sqrt, atan2

def match_locations(csv_locations, kmz_proposed_locations, threshold_meters=200):
    """
    Find matches between CSV and KMZ proposed locations
    
    Args:
        csv_locations: list of dict from Placer.ai CSV
        kmz_proposed_locations: list of dict from KMZ file
        threshold_meters: maximum distance for match (default 200m)
    
    Returns:
        tuple: (matches, unmatched_csv, unmatched_kmz)
            - matches: list of tuples (csv_location, kmz_location, confidence, distance)
            - unmatched_csv: list of CSV locations with no match
            - unmatched_kmz: list of KMZ proposed with no match
    """
    matches = []
    matched_kmz_indices = set()
    unmatched_csv = []
    
    for csv_loc in csv_locations:
        best_match = None
        best_confidence = 0
        best_kmz_idx = -1
        best_distance = float('inf')
        
        for idx, kmz_loc in enumerate(kmz_proposed_locations):
            if idx in matched_kmz_indices:
                continue  # Already matched
            
            is_match, confidence, distance = is_location_match(
                csv_loc, kmz_loc, threshold_meters
            )
            
            if is_match and confidence > best_confidence:
                best_match = kmz_loc
                best_confidence = confidence
                best_kmz_idx = idx
                best_distance = distance
        
        if best_match:
            matches.append((csv_loc, best_match, best_confidence, best_distance))
            matched_kmz_indices.add(best_kmz_idx)
        else:
            unmatched_csv.append(csv_loc)
    
    # Find unmatched KMZ locations
    unmatched_kmz = [
        kmz_proposed_locations[i] 
        for i in range(len(kmz_proposed_locations)) 
        if i not in matched_kmz_indices
    ]
    
    return matches, unmatched_csv, unmatched_kmz


def is_location_match(csv_loc, kmz_loc, threshold_meters):
    """
    Determine if two locations are the same
    
    Args:
        csv_loc: dict from CSV with Placer.ai data
        kmz_loc: dict from KMZ with proposed location data
        threshold_meters: maximum distance to consider a match
    
    Returns:
        tuple: (is_match: bool, confidence: float, distance: float)
    """
    # 1. City must match (case-insensitive)
    csv_city = str(csv_loc.get('City', '')).upper().strip()
    kmz_city = str(kmz_loc.get('city', '')).upper().strip()
    
    if csv_city != kmz_city:
        return False, 0.0, float('inf')
    
    # 2. State must match
    csv_state = str(csv_loc.get('State Code', '')).upper().strip()
    kmz_state = str(kmz_loc.get('state', '')).upper().strip()
    
    if csv_state != kmz_state:
        return False, 0.0, float('inf')
    
    # 3. Calculate distance
    try:
        distance = haversine_distance(
            float(csv_loc['Latitude']),
            float(csv_loc['Longitude']),
            float(kmz_loc['latitude']),
            float(kmz_loc['longitude'])
        )
    except (ValueError, KeyError, TypeError):
        return False, 0.0, float('inf')
    
    # 4. Determine match based on distance
    if distance <= 50:
        return True, 1.0, distance
    elif distance <= 200:
        return True, 0.8, distance
    elif distance <= threshold_meters:
        return True, 0.6, distance
    else:
        return False, 0.0, distance


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two lat/lon points in meters using Haversine formula
    
    Args:
        lat1, lon1: First location coordinates (degrees)
        lat2, lon2: Second location coordinates (degrees)
    
    Returns:
        float: Distance in meters
    """
    R = 6371000  # Earth's radius in meters
    
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    
    a = sin(delta_phi/2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c
```

### New Module: `data_merger.py`

```python
"""
Merge CSV and KMZ data intelligently, handling duplicates and matches
"""

def merge_datasets(csv_locations, kmz_existing, kmz_proposed, matches):
    """
    Combine all location data with proper handling of matches
    
    Args:
        csv_locations: All locations from Placer.ai CSV
        kmz_existing: Non-proposed locations from KMZ
        kmz_proposed: Proposed locations from KMZ
        matches: List of (csv_loc, kmz_loc, confidence, distance) tuples
    
    Returns:
        tuple: (final_locations, metadata)
            - final_locations: Combined list of all unique locations
            - metadata: Dict with merge statistics
    """
    final_locations = []
    
    # Track matched KMZ proposed locations
    matched_kmz_proposed = {match[1]['name']: match for match in matches}
    
    # 1. Add all CSV locations (highest priority - actual data)
    for csv_loc in csv_locations:
        final_locations.append({
            'source': 'csv',
            'data': csv_loc,
            'is_actual': True,
            'has_metrics': True,
            'rank': csv_loc.get('Rank'),
            'confidence': 1.0
        })
    
    # 2. Add KMZ existing locations (non-proposed, actual stores)
    for kmz_loc in kmz_existing:
        final_locations.append({
            'source': 'kmz_existing',
            'data': convert_kmz_to_standard_format(kmz_loc),
            'is_actual': True,
            'has_metrics': False,
            'rank': None,
            'confidence': 1.0
        })
    
    # 3. Add ONLY unmatched KMZ proposed locations
    for kmz_loc in kmz_proposed:
        if kmz_loc['name'] not in matched_kmz_proposed:
            final_locations.append({
                'source': 'kmz_proposed',
                'data': convert_kmz_to_standard_format(kmz_loc),
                'is_actual': False,  # Still proposed
                'has_metrics': False,
                'rank': None,
                'confidence': 0.0
            })
    
    # 4. Generate metadata
    metadata = {
        'total_locations': len(final_locations),
        'csv_locations': len(csv_locations),
        'kmz_existing': len(kmz_existing),
        'kmz_proposed_total': len(kmz_proposed),
        'kmz_proposed_kept': len(kmz_proposed) - len(matches),
        'matches_found': len(matches),
        'proposed_replaced': len(matches),
        'match_details': [
            {
                'csv_name': match[0].get('Property Name'),
                'csv_city': match[0].get('City'),
                'kmz_name': match[1]['name'],
                'confidence': match[2],
                'distance_meters': round(match[3], 2)
            }
            for match in matches
        ]
    }
    
    return final_locations, metadata


def convert_kmz_to_standard_format(kmz_location):
    """
    Convert KMZ location format to match CSV format for downstream processing
    
    Args:
        kmz_location: dict with KMZ location data
    
    Returns:
        dict: Standardized location data matching CSV structure
    """
    # Clean up year_opened
    year_opened = kmz_location.get('year_opened', '')
    if year_opened == '0' or year_opened == 0:
        year_opened = ''
    
    return {
        'Property Name': kmz_location['name'],
        'Address': kmz_location['address'],
        'City': kmz_location['city'],
        'State': kmz_location['state'],
        'State Code': kmz_location['state'],
        'Zip Code': kmz_location['zip'],
        'Latitude': kmz_location['latitude'],
        'Longitude': kmz_location['longitude'],
        'Rank': None,  # No rank for KMZ locations
        'Visits': None,  # No visits data
        'Store Id': None,  # No Store ID
        'Id': None,  # No Placer.ai ID
        'Year_opened': year_opened,
        'Web_Link': kmz_location.get('web_link', ''),
        # Preserve all extended data
        'extended_data': kmz_location.get('extended_data', {})
    }


def deduplicate_locations(locations, distance_threshold=50):
    """
    Remove duplicate locations based on proximity
    
    Args:
        locations: list of location dicts
        distance_threshold: meters within which locations are considered duplicates
    
    Returns:
        list: Deduplicated locations (keeps highest priority)
    """
    from location_matcher import haversine_distance
    
    unique_locations = []
    
    # Sort by priority: CSV > KMZ existing > KMZ proposed
    priority_order = {'csv': 3, 'kmz_existing': 2, 'kmz_proposed': 1}
    sorted_locations = sorted(
        locations, 
        key=lambda x: priority_order.get(x['source'], 0),
        reverse=True
    )
    
    for loc in sorted_locations:
        is_duplicate = False
        loc_data = loc['data']
        
        for unique_loc in unique_locations:
            unique_data = unique_loc['data']
            
            # Check if same city/state
            if (loc_data['City'] == unique_data['City'] and 
                loc_data['State Code'] == unique_data['State Code']):
                
                # Calculate distance
                try:
                    distance = haversine_distance(
                        float(loc_data['Latitude']),
                        float(loc_data['Longitude']),
                        float(unique_data['Latitude']),
                        float(unique_data['Longitude'])
                    )
                    
                    if distance <= distance_threshold:
                        is_duplicate = True
                        break
                except:
                    pass
        
        if not is_duplicate:
            unique_locations.append(loc)
    
    return unique_locations
```

---

## 🔌 UPDATED API ENDPOINTS

### POST `/upload`

**Purpose**: Upload CSV and optional KMZ files

**Request**:
```
Content-Type: multipart/form-data

csv_files: [File, File, ...]          # One or more CSV files
kmz_file: File (optional)             # Current KMZ file (if exists)
```

**Response**:
```json
{
  "job_id": "abc123-def456-ghi789",
  "csv_count": 2,
  "kmz_uploaded": true,
  "kmz_stats": {
    "total_placemarks": 45,
    "proposed_count": 8,
    "existing_count": 37
  },
  "status": "uploaded",
  "timestamp": "2025-11-02T10:30:00Z"
}
```

### POST `/generate`

**Purpose**: Process files and generate merged KMZ outputs

**Request**:
```json
{
  "job_id": "abc123-def456-ghi789",
  "csv_state_selections": {
    "7_brew_coffee.csv": ["GA", "FL", "AL", "SC"],
    "another_retailer.csv": ["GA", "TN"]
  },
  "merge_with_kmz": true,
  "match_threshold_meters": 200,
  "include_unmatched_proposed": true
}
```

**Response**:
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "processing",
  "estimated_time_seconds": 120,
  "processing_started": "2025-11-02T10:31:00Z"
}
```

### GET `/status/:job_id`

**Purpose**: Check processing status and get merge statistics

**Response**:
```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "completed",
  "progress": 100,
  "merge_stats": {
    "total_csv_locations": 150,
    "kmz_existing_kept": 50,
    "kmz_proposed_total": 10,
    "kmz_proposed_kept": 5,
    "matches_found": 5,
    "proposed_replaced": 5,
    "match_details": [
      {
        "csv_name": "7 Brew Coffee",
        "csv_city": "Athens",
        "kmz_name": "7 Brew Coffee-Athens, GA (proposed)",
        "confidence": 0.8,
        "distance_meters": 45.2
      }
    ]
  },
  "states_generated": ["GA", "FL", "AL"],
  "download_url": "/download/abc123-def456-ghi789",
  "processing_completed": "2025-11-02T10:33:00Z"
}
```

### GET `/download/:job_id`

**Purpose**: Download the generated ZIP file with all state KMZ files

**Response**: ZIP file containing state-specific KMZ files

---

## 🎨 UPDATED UI COMPONENTS (React with Tailwind CSS)

### File Upload Component with KMZ Support

```jsx
import React, { useState } from 'react';
import { Upload, FileText, Map, AlertCircle } from 'lucide-react';

function FileUploadWithKMZ() {
  const [csvFiles, setCsvFiles] = useState([]);
  const [kmzFile, setKmzFile] = useState(null);
  const [kmzStats, setKmzStats] = useState(null);

  const handleKmzUpload = async (file) => {
    setKmzFile(file);
    // Parse KMZ and show preview
    // This would call an API endpoint to get stats
  };

  return (
    <div className="space-y-6 p-6">
      {/* CSV Upload */}
      <div className="border-2 border-dashed border-blue-300 rounded-lg p-6 bg-blue-50">
        <div className="flex items-center gap-3 mb-4">
          <FileText className="text-blue-600" size={24} />
          <h3 className="text-lg font-semibold">Upload Placer.ai CSV Files</h3>
        </div>
        <input
          type="file"
          multiple
          accept=".csv"
          onChange={(e) => setCsvFiles(Array.from(e.target.files))}
          className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700"
        />
        <p className="text-sm text-gray-600 mt-2">
          <strong>Required:</strong> Fresh data from Placer.ai Ranking Index export
        </p>
        {csvFiles.length > 0 && (
          <div className="mt-4 space-y-2">
            {csvFiles.map((file, idx) => (
              <div key={idx} className="flex items-center gap-2 bg-white p-2 rounded">
                <span className="text-green-600">✓</span>
                <span className="flex-1">{file.name}</span>
                <span className="text-sm text-gray-500">
                  ({(file.size / 1024).toFixed(1)} KB)
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* KMZ Upload (Optional) */}
      <div className="border-2 border-dashed border-purple-300 rounded-lg p-6 bg-purple-50">
        <div className="flex items-center gap-3 mb-4">
          <Map className="text-purple-600" size={24} />
          <h3 className="text-lg font-semibold">Upload Current KMZ (Optional)</h3>
        </div>
        <input
          type="file"
          accept=".kmz"
          onChange={(e) => handleKmzUpload(e.target.files[0])}
          className="block w-full text-sm file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-700"
        />
        <div className="flex items-start gap-2 mt-3 p-3 bg-purple-100 rounded">
          <AlertCircle size={16} className="text-purple-700 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-gray-700">
            Include your existing KMZ file if you have proposed/planned locations.
            The system will intelligently replace proposed locations with actual 
            data from CSV when matches are found.
          </p>
        </div>
        
        {kmzFile && (
          <div className="mt-4 bg-white p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-green-600">✓</span>
              <span className="font-medium">{kmzFile.name}</span>
            </div>
            {kmzStats && (
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-gray-50 p-3 rounded">
                  <div className="text-xs text-gray-600 mb-1">Total Locations</div>
                  <div className="text-2xl font-bold">{kmzStats.total_placemarks}</div>
                </div>
                <div className="bg-orange-50 p-3 rounded">
                  <div className="text-xs text-gray-600 mb-1">Proposed/U/C</div>
                  <div className="text-2xl font-bold text-orange-600">{kmzStats.proposed_count}</div>
                </div>
                <div className="bg-green-50 p-3 rounded">
                  <div className="text-xs text-gray-600 mb-1">Existing</div>
                  <div className="text-2xl font-bold text-green-600">{kmzStats.existing_count}</div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Smart Merge Info Box */}
      {kmzFile && csvFiles.length > 0 && (
        <div className="bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-6">
          <h4 className="text-lg font-semibold mb-3 flex items-center gap-2">
            🔄 Smart Merge Enabled
          </h4>
          <ul className="space-y-2 text-sm text-gray-700">
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-1">•</span>
              <span>
                Locations marked as <code className="bg-white px-1.5 py-0.5 rounded text-xs">(proposed)</code> or{' '}
                <code className="bg-white px-1.5 py-0.5 rounded text-xs">(U/C)</code> in 
                your KMZ will be matched against CSV data
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-1">•</span>
              <span>
                When a match is found (within 200 meters, same city/state), the 
                proposed location will be replaced with actual Placer.ai data
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-1">•</span>
              <span>Proposed locations without matches will remain in the output</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-blue-600 mt-1">•</span>
              <span>All existing (non-proposed) KMZ locations will be preserved</span>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}

export default FileUploadWithKMZ;
```

### Processing Status with Detailed Merge Stats

```jsx
import React, { useState, useEffect } from 'react';
import { CheckCircle, Clock, Map, Download } from 'lucide-react';

function ProcessingStatus({ jobId }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const pollStatus = async () => {
      const response = await fetch(`/status/${jobId}`);
      const data = await response.json();
      setStatus(data);
      setLoading(false);
      
      if (data.status !== 'completed' && data.status !== 'failed') {
        setTimeout(pollStatus, 2000);
      }
    };
    
    pollStatus();
  }, [jobId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center gap-3 mb-4">
          {status.status === 'completed' ? (
            <CheckCircle className="text-green-600" size={32} />
          ) : (
            <Clock className="text-blue-600 animate-pulse" size={32} />
          )}
          <h3 className="text-2xl font-bold">
            {status.status === 'completed' ? 'Processing Complete' : 'Processing...'}
          </h3>
        </div>
        
        <div className="relative w-full h-4 bg-gray-200 rounded-full overflow-hidden">
          <div 
            className="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-500"
            style={{ width: `${status.progress}%` }}
          />
        </div>
        <div className="text-right mt-1 text-sm text-gray-600">{status.progress}%</div>
      </div>
      
      {status.merge_stats && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h4 className="text-xl font-semibold mb-4">📊 Merge Statistics</h4>
          
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="text-sm text-gray-600 mb-1">CSV Locations</div>
              <div className="text-3xl font-bold text-blue-600">
                {status.merge_stats.csv_locations}
              </div>
            </div>
            
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="text-sm text-gray-600 mb-1">KMZ Existing</div>
              <div className="text-3xl font-bold text-green-600">
                {status.merge_stats.kmz_existing}
              </div>
            </div>
            
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <div className="text-sm text-gray-600 mb-1">Proposed Replaced</div>
              <div className="text-3xl font-bold text-purple-600">
                {status.merge_stats.proposed_replaced}
              </div>
            </div>
            
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
              <div className="text-sm text-gray-600 mb-1">Proposed Kept</div>
              <div className="text-3xl font-bold text-orange-600">
                {status.merge_stats.kmz_proposed_kept}
              </div>
            </div>
            
            <div className="bg-gray-50 border border-gray-300 rounded-lg p-4">
              <div className="text-sm text-gray-600 mb-1">Total Locations</div>
              <div className="text-3xl font-bold text-gray-800">
                {status.merge_stats.total_locations}
              </div>
            </div>
          </div>

          {status.merge_stats.match_details && 
           status.merge_stats.match_details.length > 0 && (
            <div className="mt-6">
              <h5 className="font-semibold mb-3">Match Details</h5>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b">
                    <tr>
                      <th className="px-4 py-2 text-left">CSV Location</th>
                      <th className="px-4 py-2 text-left">Replaced Proposed</th>
                      <th className="px-4 py-2 text-left">City</th>
                      <th className="px-4 py-2 text-center">Confidence</th>
                      <th className="px-4 py-2 text-right">Distance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {status.merge_stats.match_details.map((match, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-3">{match.csv_name}</td>
                        <td className="px-4 py-3 text-red-600 line-through">{match.kmz_name}</td>
                        <td className="px-4 py-3">{match.csv_city}</td>
                        <td className="px-4 py-3 text-center">
                          <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                            match.confidence >= 0.9 ? 'bg-green-100 text-green-800' :
                            match.confidence >= 0.7 ? 'bg-yellow-100 text-yellow-800' :
                            'bg-orange-100 text-orange-800'
                          }`}>
                            {(match.confidence * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right text-gray-600">
                          {match.distance_meters}m
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {status.status === 'completed' && (
        <div className="bg-gradient-to-r from-green-50 to-blue-50 border border-green-200 rounded-lg p-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div>
              <h4 className="text-lg font-semibold mb-1">Ready to Download</h4>
              <p className="text-sm text-gray-600">
                Generated {status.states_generated.length} state files: {' '}
                <span className="font-medium">{status.states_generated.join(', ')}</span>
              </p>
            </div>
            <a 
              href={status.download_url} 
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
              download
            >
              <Download size={20} />
              Download KMZ Files
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProcessingStatus;
```

---

## 🧪 TESTING STRATEGY

### Test Cases

#### Test Case 1: Exact Match (< 50m distance)

**Setup:**
- KMZ proposed: "7 Brew Coffee-Athens, GA (proposed)" at (33.9389, -83.4535)
- CSV actual: "7 Brew Coffee" at (33.9390, -83.4536)

**Expected:**
- Match found with confidence 1.0
- CSV data replaces proposed marker
- Proposed marker deleted
- Final KMZ has one marker with CSV data

#### Test Case 2: Close Match (< 200m distance)

**Setup:**
- KMZ proposed: "7 Brew Coffee-Cumming, GA (proposed)" at (34.172, -84.1841)
- CSV actual: "7 Brew Coffee" at (34.1725, -84.1838)

**Expected:**
- Match found with confidence 0.8
- CSV data replaces proposed marker
- Proposed marker deleted

#### Test Case 3: No Match (> 500m distance)

**Setup:**
- KMZ proposed: "7 Brew Coffee-Woodstock, GA (proposed)" at (34.101, -84.519)
- CSV: No locations in Woodstock

**Expected:**
- No match found
- Proposed marker kept in final KMZ
- Still shows as "(proposed)"

#### Test Case 4: Multiple Proposed, Some Match

**Setup:**
- KMZ proposed: 5 locations marked (proposed)
- CSV: 2 locations match two of the proposed

**Expected:**
- 2 matches found and replaced
- 3 proposed locations kept
- CSV adds other new locations
- Total = CSV count + 3 kept proposed + existing KMZ

#### Test Case 5: KMZ Without Proposed Locations

**Setup:**
- KMZ: All existing locations (no "proposed" markers)
- CSV: New data

**Expected:**
- All KMZ locations kept
- All CSV locations added
- No matches attempted

#### Test Case 6: No KMZ Uploaded

**Setup:**
- User only uploads CSV files
- No KMZ file provided

**Expected:**
- Process normally without merge
- Generate fresh KMZ from CSV only
- No matching attempted

### Unit Tests

```python
import pytest
from processing.location_matcher import is_location_match, haversine_distance
from processing.kmz_parser import is_proposed_location

def test_exact_match():
    """Test matching with very close proximity"""
    csv_loc = {
        'City': 'Athens',
        'State Code': 'GA',
        'Latitude': 33.9389,
        'Longitude': -83.4535
    }
    kmz_loc = {
        'city': 'Athens',
        'state': 'GA',
        'latitude': 33.9390,
        'longitude': -83.4536
    }
    
    is_match, confidence, distance = is_location_match(csv_loc, kmz_loc, 200)
    
    assert is_match == True
    assert confidence >= 0.8
    assert distance < 50

def test_no_match_different_city():
    """Test that different cities don't match"""
    csv_loc = {
        'City': 'Athens',
        'State Code': 'GA',
        'Latitude': 33.9389,
        'Longitude': -83.4535
    }
    kmz_loc = {
        'city': 'Atlanta',
        'state': 'GA',
        'latitude': 33.9389,
        'longitude': -83.4535
    }
    
    is_match, confidence, distance = is_location_match(csv_loc, kmz_loc, 200)
    
    assert is_match == False
    assert confidence == 0.0

def test_no_match_different_state():
    """Test that different states don't match"""
    csv_loc = {
        'City': 'Columbus',
        'State Code': 'GA',
        'Latitude': 32.4609,
        'Longitude': -84.9877
    }
    kmz_loc = {
        'city': 'Columbus',
        'state': 'OH',
        'latitude': 39.9612,
        'longitude': -82.9988
    }
    
    is_match, confidence, distance = is_location_match(csv_loc, kmz_loc, 200)
    
    assert is_match == False

def test_distance_calculation():
    """Test known distance calculation"""
    # Athens, GA to Atlanta, GA: approximately 100km
    distance = haversine_distance(33.9389, -83.4535, 33.7490, -84.3880)
    
    assert 95000 < distance < 105000  # ~100km ± 5km

def test_proposed_location_detection():
    """Test detection of proposed location markers"""
    assert is_proposed_location("7 Brew Coffee-Athens, GA (proposed)") == True
    assert is_proposed_location("7 Brew Coffee-Athens, GA (U/C)") == True
    assert is_proposed_location("7 Brew Coffee-Athens, GA Under Construction") == True
    assert is_proposed_location("7 Brew Coffee-Athens, GA") == False
    assert is_proposed_location("7 Brew Coffee-Athens, GA (opening soon)") == True
```

---

## 📊 EDGE CASES & HANDLING

### Edge Case 1: Multiple KMZ Proposed Match Same CSV Location

**Scenario:**
- 2 proposed locations within 200m of each other
- 1 CSV location equidistant to both

**Handling:**
- Match to closest KMZ proposed
- Other proposed location remains
- Log warning for manual review in metadata

### Edge Case 2: KMZ Has More Data Fields Than CSV

**Scenario:**
- KMZ existing location has custom fields (notes, contact info, web links)
- CSV has Placer.ai metrics

**Handling:**
- Preserve ALL KMZ custom fields
- Add CSV metrics to existing data
- Merge intelligently, don't overwrite unique data
- Extended data fields preserved in output

### Edge Case 3: Year_opened Conflict

**Scenario:**
- KMZ proposed: `Year_opened = 2025` (future)
- CSV actual: `Year_opened = 2024` (already opened)

**Handling:**
- CSV data takes priority (it's actual)
- Update Year_opened to CSV value
- Log discrepancy in metadata

### Edge Case 4: Invalid Coordinates

**Scenario:**
- KMZ or CSV has (0, 0) or invalid coordinates

**Handling:**
- Skip matching for invalid coordinates
- Log warning
- Keep location but mark as needing review

### Edge Case 5: City Name Variations

**Scenario:**
- CSV: "Saint Louis"
- KMZ: "St. Louis"

**Handling:**
- Normalize city names (St. → Saint, remove periods)
- Apply fuzzy matching if exact match fails
- Log normalization in metadata

---

## 🔔 USER NOTIFICATIONS

### Success Messages

**Matches Found:**
```
✓ Found 3 matches between CSV and proposed locations
  - Athens, GA (proposed) → Replaced with actual data (45m away, 95% confidence)
  - Cumming, GA (proposed) → Replaced with actual data (120m away, 80% confidence)
  - Lilburn, GA (proposed) → Replaced with actual data (35m away, 100% confidence)
```

**Proposed Kept:**
```
⚠ 2 proposed locations kept (no match found in CSV)
  - Woodstock, GA (proposed) - Still planned
  - Sandy Springs, GA (proposed) - Still planned

These locations will remain marked as proposed in the output files.
```

**Complete Summary:**
```
📊 Merge Complete

✓ 150 locations from CSV (actual Placer.ai data)
✓ 50 existing locations from KMZ (preserved)
✓ 5 proposed locations replaced with actual data
✓ 2 proposed locations still pending

= 202 total unique locations in final output

Files generated: GA.kmz, FL.kmz, AL.kmz, SC.kmz
```

---

## ⚠️ IMPORTANT CONSIDERATIONS

### Data Privacy

- Don't log specific addresses in plain text logs
- Sanitize filenames before storage
- Clean up temp files immediately after processing
- Secure file uploads with virus scanning
- Limit file sizes (CSV: 50MB, KMZ: 10MB)

### Performance

- Matching algorithm is O(n × m) where n = CSV count, m = proposed count
- For 1000 CSV + 100 proposed: ~100,000 comparisons
- Optimization strategies:
  - Early exit on state/city mismatch
  - Spatial indexing for large datasets (R-tree)
  - Parallel processing for independent states
  - Cache distance calculations

### User Experience

- Show real-time merge statistics during processing
- Highlight which proposed locations were replaced
- Provide downloadable merge report (JSON/CSV)
- Allow manual review of low-confidence matches
- Visual map preview of matches (future enhancement)

---

## 🚀 IMPLEMENTATION CHECKLIST

### Phase 1: Core Merge Logic (4 hours)

- [ ] Implement `kmz_parser.py` with KML extraction
- [ ] Handle both `<n>` and `<name>` tags
- [ ] Implement `location_matcher.py` with haversine distance
- [ ] Implement `data_merger.py` with smart combining
- [ ] Add deduplication logic
- [ ] Write unit tests for each component (15+ tests)
- [ ] Test with provided 7 Brew CSV and KMZ

### Phase 2: API Integration (3 hours)

- [ ] Update `/upload` endpoint to accept KMZ
- [ ] Add KMZ parsing and stats preview
- [ ] Update `/generate` endpoint with merge parameters
- [ ] Update `/status` endpoint with detailed merge stats
- [ ] Add match details to metadata
- [ ] Update error handling for KMZ parsing errors
- [ ] Test with Postman/curl

### Phase 3: UI Integration (3 hours)

- [ ] Add KMZ file upload component
- [ ] Show KMZ stats preview after upload
- [ ] Add merge enable/disable toggle
- [ ] Display merge statistics during processing
- [ ] Show detailed match report in results
- [ ] Add download button for merge report (JSON)
- [ ] Test complete user workflow

### Phase 4: Testing & Polish (2 hours)

- [ ] Test all 6 test cases
- [ ] Test all 5 edge cases
- [ ] Verify with real 7 Brew data
- [ ] Performance test with large datasets (1000+ locations)
- [ ] Load testing (10 simultaneous uploads)
- [ ] Update all documentation
- [ ] Create user guide with screenshots

**Total estimated time: 12 hours**

---

## 📚 REFERENCES

- [Haversine Formula](https://en.wikipedia.org/wiki/Haversine_formula) - Geographic distance calculation
- [KML Reference](https://developers.google.com/kml/documentation/kmlreference) - KML/KMZ structure
- [Python xml.etree](https://docs.python.org/3/library/xml.etree.elementtree.html) - XML parsing
- [GeoPy Distance](https://geopy.readthedocs.io/en/stable/#module-geopy.distance) - Alternative distance library
- [Spatial Indexing with R-trees](https://en.wikipedia.org/wiki/R-tree) - Performance optimization

---

## 📝 DOCUMENT METADATA

- **Created**: November 2, 2025
- **Version**: 2.0
- **Status**: Ready for Implementation
- **Author**: System Documentation
- **Last Review**: November 2, 2025

---

## 🎯 NEXT STEPS

1. Review and approve this specification
2. Set up development environment
3. Implement Phase 1 (Core Merge Logic)
4. Create test data fixtures
5. Build and test API endpoints
6. Integrate UI components
7. Conduct user acceptance testing
8. Deploy to production
