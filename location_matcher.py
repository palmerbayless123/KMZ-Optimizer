"""
Location Matcher Module
Match CSV locations with KMZ proposed locations using geographic proximity and location attributes.

This module handles:
- Matching CSV (actual) locations to KMZ proposed locations
- Calculating geographic distance using Haversine formula
- Confidence scoring based on proximity
- Preventing duplicate matches
- Handling edge cases (different cities, states, invalid coordinates)

Matching Strategy:
1. City must match (case-insensitive)
2. State must match
3. Distance must be within threshold (default 200m)
4. Confidence based on proximity: <50m = 100%, <200m = 80%, <500m = 60%

Author: System
Date: November 2, 2025
Version: 1.0
"""

from math import radians, sin, cos, sqrt, atan2
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def match_locations(csv_locations, kmz_proposed_locations, threshold_meters=200):
    """
    Find matches between CSV and KMZ proposed locations using geographic proximity.
    
    Each CSV location is matched to at most one KMZ proposed location (1:1 matching).
    Best match is selected based on highest confidence score.
    
    Args:
        csv_locations (list): List of dicts from Placer.ai CSV with keys:
            - City, State Code, Latitude, Longitude, Property Name, etc.
        kmz_proposed_locations (list): List of dicts from KMZ with keys:
            - city, state, latitude, longitude, name, etc.
        threshold_meters (int): Maximum distance in meters to consider a match (default: 200)
    
    Returns:
        tuple: (matches, unmatched_csv, unmatched_kmz)
            - matches (list): List of tuples (csv_loc, kmz_loc, confidence, distance)
            - unmatched_csv (list): CSV locations with no match found
            - unmatched_kmz (list): KMZ proposed locations with no match found
    """
    matches = []
    matched_kmz_indices = set()
    unmatched_csv = []
    
    logger.info(f"Starting location matching: {len(csv_locations)} CSV locations, "
                f"{len(kmz_proposed_locations)} KMZ proposed locations")
    
    # For each CSV location, find the best matching KMZ proposed location
    for csv_idx, csv_loc in enumerate(csv_locations):
        best_match = None
        best_confidence = 0
        best_kmz_idx = -1
        best_distance = float('inf')
        
        # Check against all unmatched KMZ proposed locations
        for kmz_idx, kmz_loc in enumerate(kmz_proposed_locations):
            if kmz_idx in matched_kmz_indices:
                continue  # This KMZ location already matched
            
            # Check if these two locations match
            is_match, confidence, distance = is_location_match(
                csv_loc, kmz_loc, threshold_meters
            )
            
            # Keep track of best match
            if is_match and confidence > best_confidence:
                best_match = kmz_loc
                best_confidence = confidence
                best_kmz_idx = kmz_idx
                best_distance = distance
        
        # Record the match if found
        if best_match:
            matches.append((csv_loc, best_match, best_confidence, best_distance))
            matched_kmz_indices.add(best_kmz_idx)
            logger.debug(f"Match found: CSV '{csv_loc.get('Property Name')}' -> "
                        f"KMZ '{best_match['name']}' "
                        f"({best_distance:.1f}m, {best_confidence*100:.0f}% confidence)")
        else:
            unmatched_csv.append(csv_loc)
            logger.debug(f"No match for CSV location: {csv_loc.get('Property Name')} "
                        f"in {csv_loc.get('City')}, {csv_loc.get('State Code')}")
    
    # Find unmatched KMZ proposed locations
    unmatched_kmz = [
        kmz_proposed_locations[i] 
        for i in range(len(kmz_proposed_locations)) 
        if i not in matched_kmz_indices
    ]
    
    logger.info(f"Matching complete: {len(matches)} matches, "
                f"{len(unmatched_csv)} unmatched CSV, "
                f"{len(unmatched_kmz)} unmatched KMZ proposed")
    
    return matches, unmatched_csv, unmatched_kmz


def is_location_match(csv_loc, kmz_loc, threshold_meters):
    """
    Determine if a CSV location matches a KMZ proposed location.
    
    Matching criteria (all must be true):
    1. City names match (case-insensitive)
    2. State codes match
    3. Geographic distance is within threshold
    
    Args:
        csv_loc (dict): CSV location with keys: City, State Code, Latitude, Longitude
        kmz_loc (dict): KMZ location with keys: city, state, latitude, longitude
        threshold_meters (float): Maximum distance to consider a match
    
    Returns:
        tuple: (is_match, confidence, distance)
            - is_match (bool): True if locations match
            - confidence (float): Confidence score 0.0-1.0 (based on distance)
            - distance (float): Distance in meters (inf if no match)
    """
    # 1. City must match (case-insensitive, strip whitespace)
    csv_city = str(csv_loc.get('City', '')).upper().strip()
    kmz_city = str(kmz_loc.get('city', '')).upper().strip()
    
    if not csv_city or not kmz_city:
        logger.debug(f"Missing city data: CSV='{csv_city}', KMZ='{kmz_city}'")
        return False, 0.0, float('inf')
    
    if csv_city != kmz_city:
        return False, 0.0, float('inf')
    
    # 2. State must match (case-insensitive, strip whitespace)
    csv_state = str(csv_loc.get('State Code', '')).upper().strip()
    kmz_state = str(kmz_loc.get('state', '')).upper().strip()
    
    if not csv_state or not kmz_state:
        logger.debug(f"Missing state data: CSV='{csv_state}', KMZ='{kmz_state}'")
        return False, 0.0, float('inf')
    
    if csv_state != kmz_state:
        return False, 0.0, float('inf')
    
    # 3. Calculate geographic distance
    try:
        lat1 = float(csv_loc['Latitude'])
        lon1 = float(csv_loc['Longitude'])
        lat2 = float(kmz_loc['latitude'])
        lon2 = float(kmz_loc['longitude'])
        
        # Check for invalid coordinates (0,0 or out of range)
        if not is_valid_coordinate(lat1, lon1) or not is_valid_coordinate(lat2, lon2):
            logger.debug(f"Invalid coordinates: CSV=({lat1},{lon1}), KMZ=({lat2},{lon2})")
            return False, 0.0, float('inf')
        
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        
    except (ValueError, KeyError, TypeError) as e:
        logger.debug(f"Error calculating distance: {str(e)}")
        return False, 0.0, float('inf')
    
    # 4. Determine match based on distance thresholds
    if distance <= 50:
        # Within 50 meters - almost certainly the same location
        return True, 1.0, distance
    elif distance <= 200:
        # Within 200 meters - very likely the same location
        return True, 0.8, distance
    elif distance <= threshold_meters:
        # Within custom threshold - possible match (for manual review)
        return True, 0.6, distance
    else:
        # Too far apart
        return False, 0.0, distance


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on Earth using the Haversine formula.
    
    This gives the shortest distance over the earth's surface, ignoring hills/valleys.
    
    Args:
        lat1 (float): Latitude of first point in degrees
        lon1 (float): Longitude of first point in degrees
        lat2 (float): Latitude of second point in degrees
        lon2 (float): Longitude of second point in degrees
    
    Returns:
        float: Distance in meters
    
    References:
        https://en.wikipedia.org/wiki/Haversine_formula
    """
    # Earth's radius in meters (mean radius)
    R = 6371000
    
    # Convert latitude and longitude from degrees to radians
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    
    # Haversine formula
    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    distance = R * c
    
    return distance


def is_valid_coordinate(lat, lon):
    """
    Check if a coordinate pair is valid.
    
    Invalid coordinates include:
    - (0, 0) - often indicates missing data
    - Out of range values (lat not in [-90, 90], lon not in [-180, 180])
    - NaN or None values
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
    
    Returns:
        bool: True if coordinate is valid, False otherwise
    """
    try:
        lat = float(lat)
        lon = float(lon)
        
        # Check for (0, 0) - often indicates missing data
        if lat == 0 and lon == 0:
            return False
        
        # Check range
        if not (-90 <= lat <= 90):
            return False
        if not (-180 <= lon <= 180):
            return False
        
        return True
        
    except (ValueError, TypeError):
        return False


def calculate_match_statistics(matches):
    """
    Calculate statistics about the matches for reporting.
    
    Args:
        matches (list): List of tuples (csv_loc, kmz_loc, confidence, distance)
    
    Returns:
        dict: Statistics including:
            - total_matches: Number of matches
            - avg_distance: Average distance in meters
            - avg_confidence: Average confidence score
            - high_confidence: Matches with confidence >= 0.9
            - medium_confidence: Matches with 0.7 <= confidence < 0.9
            - low_confidence: Matches with confidence < 0.7
            - distance_ranges: Count by distance range
    """
    if not matches:
        return {
            'total_matches': 0,
            'avg_distance': 0,
            'avg_confidence': 0,
            'high_confidence': 0,
            'medium_confidence': 0,
            'low_confidence': 0,
            'distance_ranges': {
                '0-50m': 0,
                '50-100m': 0,
                '100-200m': 0,
                '200-500m': 0,
                '500m+': 0
            }
        }
    
    total = len(matches)
    distances = [m[3] for m in matches]
    confidences = [m[2] for m in matches]
    
    stats = {
        'total_matches': total,
        'avg_distance': sum(distances) / total,
        'avg_confidence': sum(confidences) / total,
        'high_confidence': sum(1 for c in confidences if c >= 0.9),
        'medium_confidence': sum(1 for c in confidences if 0.7 <= c < 0.9),
        'low_confidence': sum(1 for c in confidences if c < 0.7),
        'distance_ranges': {
            '0-50m': sum(1 for d in distances if d <= 50),
            '50-100m': sum(1 for d in distances if 50 < d <= 100),
            '100-200m': sum(1 for d in distances if 100 < d <= 200),
            '200-500m': sum(1 for d in distances if 200 < d <= 500),
            '500m+': sum(1 for d in distances if d > 500)
        }
    }
    
    return stats


def generate_match_report(matches, output_format='text'):
    """
    Generate a human-readable report of matches.
    
    Args:
        matches (list): List of tuples (csv_loc, kmz_loc, confidence, distance)
        output_format (str): 'text' or 'dict'
    
    Returns:
        str or dict: Formatted report
    """
    stats = calculate_match_statistics(matches)
    
    if output_format == 'dict':
        return {
            'statistics': stats,
            'matches': [
                {
                    'csv_name': m[0].get('Property Name', 'Unknown'),
                    'csv_city': m[0].get('City', 'Unknown'),
                    'csv_state': m[0].get('State Code', 'Unknown'),
                    'kmz_name': m[1]['name'],
                    'kmz_city': m[1]['city'],
                    'kmz_state': m[1]['state'],
                    'confidence': round(m[2], 2),
                    'distance_meters': round(m[3], 2)
                }
                for m in matches
            ]
        }
    
    # Text format
    report = []
    report.append("=" * 80)
    report.append("LOCATION MATCHING REPORT")
    report.append("=" * 80)
    report.append("")
    report.append(f"Total Matches: {stats['total_matches']}")
    report.append(f"Average Distance: {stats['avg_distance']:.1f} meters")
    report.append(f"Average Confidence: {stats['avg_confidence']*100:.0f}%")
    report.append("")
    report.append("Confidence Breakdown:")
    report.append(f"  High (≥90%):   {stats['high_confidence']} matches")
    report.append(f"  Medium (70-89%): {stats['medium_confidence']} matches")
    report.append(f"  Low (<70%):    {stats['low_confidence']} matches")
    report.append("")
    report.append("Distance Breakdown:")
    for range_name, count in stats['distance_ranges'].items():
        report.append(f"  {range_name:12} {count} matches")
    report.append("")
    report.append("=" * 80)
    report.append("MATCH DETAILS")
    report.append("=" * 80)
    report.append("")
    
    for idx, (csv_loc, kmz_loc, confidence, distance) in enumerate(matches, 1):
        report.append(f"{idx}. CSV: {csv_loc.get('Property Name', 'Unknown')}")
        report.append(f"   Location: {csv_loc.get('City')}, {csv_loc.get('State Code')}")
        report.append(f"   → Replaces KMZ: {kmz_loc['name']}")
        report.append(f"   Distance: {distance:.1f}m | Confidence: {confidence*100:.0f}%")
        report.append("")
    
    return "\n".join(report)


# Example usage and testing
if __name__ == "__main__":
    import json
    
    print("\n" + "=" * 80)
    print("LOCATION MATCHER TEST")
    print("=" * 80 + "\n")
    
    # Sample test data
    csv_locations = [
        {
            'Property Name': '7 Brew Coffee',
            'City': 'Athens',
            'State Code': 'GA',
            'Latitude': 33.9390,
            'Longitude': -83.4536
        },
        {
            'Property Name': '7 Brew Coffee',
            'City': 'Augusta',
            'State Code': 'GA',
            'Latitude': 33.5125,
            'Longitude': -82.0485
        }
    ]
    
    kmz_proposed = [
        {
            'name': '7 Brew Coffee-Athens, GA (proposed)',
            'city': 'Athens',
            'state': 'GA',
            'latitude': 33.9389,
            'longitude': -83.4535
        },
        {
            'name': '7 Brew Coffee-Woodstock, GA (proposed)',
            'city': 'Woodstock',
            'state': 'GA',
            'latitude': 34.101,
            'longitude': -84.519
        }
    ]
    
    print("Test Data:")
    print(f"  CSV Locations: {len(csv_locations)}")
    print(f"  KMZ Proposed: {len(kmz_proposed)}")
    print()
    
    # Run matching
    print("Running location matching...")
    matches, unmatched_csv, unmatched_kmz = match_locations(
        csv_locations, kmz_proposed, threshold_meters=200
    )
    
    print("\nResults:")
    print(f"  Matches found: {len(matches)}")
    print(f"  Unmatched CSV: {len(unmatched_csv)}")
    print(f"  Unmatched KMZ: {len(unmatched_kmz)}")
    print()
    
    # Show match details
    if matches:
        print("Match Details:")
        for csv_loc, kmz_loc, confidence, distance in matches:
            print(f"\n  ✓ CSV: {csv_loc['Property Name']} ({csv_loc['City']}, {csv_loc['State Code']})")
            print(f"    → KMZ: {kmz_loc['name']}")
            print(f"    Distance: {distance:.1f}m | Confidence: {confidence*100:.0f}%")
    
    # Show unmatched
    if unmatched_csv:
        print("\nUnmatched CSV locations:")
        for loc in unmatched_csv:
            print(f"  - {loc['Property Name']} ({loc['City']}, {loc['State Code']})")
    
    if unmatched_kmz:
        print("\nUnmatched KMZ proposed locations:")
        for loc in unmatched_kmz:
            print(f"  - {loc['name']} ({loc['city']}, {loc['state']})")
    
    # Generate report
    print("\n" + "=" * 80)
    print(generate_match_report(matches, output_format='text'))
    
    # Test distance calculation
    print("\n" + "=" * 80)
    print("Distance Calculation Tests:")
    print("=" * 80 + "\n")
    
    test_cases = [
        ("Same location", 33.9389, -83.4535, 33.9389, -83.4535, 0),
        ("~50m apart", 33.9389, -83.4535, 33.9390, -83.4536, 50),
        ("Athens to Atlanta", 33.9389, -83.4535, 33.7490, -84.3880, 100000)
    ]
    
    for name, lat1, lon1, lat2, lon2, expected in test_cases:
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        print(f"{name}: {distance:.1f}m (expected ~{expected}m)")
    
    print("\n" + "=" * 80)
    print("✓ All tests complete!")
    print("=" * 80 + "\n")
