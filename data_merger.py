"""
Data Merger Module
Intelligently merge CSV (Placer.ai) and KMZ data, handling matches and preserving all unique locations.

This module handles:
- Combining CSV locations (actual data) with KMZ locations (existing + proposed)
- Replacing matched proposed locations with actual CSV data
- Preserving unmatched proposed locations
- Preserving all existing (non-proposed) KMZ locations
- Deduplication based on proximity
- Generating comprehensive merge metadata

Priority order:
1. CSV locations (highest - actual Placer.ai data)
2. KMZ existing locations (non-proposed, actual stores)
3. KMZ proposed locations (lowest - still planned, only if no CSV match)

Author: System
Date: November 2, 2025
Version: 1.1
"""

import logging
import re
from typing import List, Dict, Tuple, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def merge_datasets(csv_locations, kmz_existing, kmz_proposed, matches):
    """
    Combine all location data with proper handling of matches and deduplication.
    
    This is the core merge function that:
    1. Adds all CSV locations (highest priority)
    2. Adds all KMZ existing (non-proposed) locations
    3. Adds ONLY unmatched KMZ proposed locations
    4. Excludes matched KMZ proposed (they're replaced by CSV data)
    
    Args:
        csv_locations (list): All locations from Placer.ai CSV
        kmz_existing (list): Non-proposed locations from KMZ
        kmz_proposed (list): Proposed locations from KMZ
        matches (list): List of (csv_loc, kmz_loc, confidence, distance) tuples
    
    Returns:
        tuple: (final_locations, metadata)
            - final_locations (list): Combined list of all unique locations with metadata
            - metadata (dict): Comprehensive merge statistics and details
    """
    final_locations = []
    
    # Track which KMZ proposed locations were matched (to exclude them)
    matched_kmz_proposed_names = {match[1]['name']: match for match in matches}
    
    logger.info(f"Starting merge: {len(csv_locations)} CSV, {len(kmz_existing)} KMZ existing, "
                f"{len(kmz_proposed)} KMZ proposed, {len(matches)} matches")
    
    # 1. ADD ALL CSV LOCATIONS (highest priority - actual data with metrics)
    for csv_loc in csv_locations:
        final_locations.append({
            'source': 'csv',
            'data': csv_loc,
            'is_actual': True,
            'has_metrics': True,
            'rank': csv_loc.get('Rank'),
            'confidence': 1.0,
            'matched_proposed': None  # Track if this replaced a proposed location
        })
    
    # Tag CSV locations that replaced proposed locations
    for match in matches:
        csv_loc, kmz_loc, confidence, distance = match
        # Find the CSV location in final_locations and tag it
        for final_loc in final_locations:
            if final_loc['source'] == 'csv' and final_loc['data'] == csv_loc:
                final_loc['matched_proposed'] = {
                    'name': kmz_loc['name'],
                    'distance': distance,
                    'confidence': confidence
                }
                break
    
    logger.info(f"Added {len(csv_locations)} CSV locations")
    
    # 2. ADD ALL KMZ EXISTING LOCATIONS (non-proposed, actual stores)
    for kmz_loc in kmz_existing:
        final_locations.append({
            'source': 'kmz_existing',
            'data': convert_kmz_to_standard_format(kmz_loc),
            'is_actual': True,
            'has_metrics': False,
            'rank': None,
            'confidence': 1.0,
            'matched_proposed': None
        })
    
    logger.info(f"Added {len(kmz_existing)} KMZ existing locations")
    
    # 3. ADD ONLY UNMATCHED KMZ PROPOSED LOCATIONS
    unmatched_proposed = []
    for kmz_loc in kmz_proposed:
        if kmz_loc['name'] not in matched_kmz_proposed_names:
            final_locations.append({
                'source': 'kmz_proposed',
                'data': convert_kmz_to_standard_format(kmz_loc),
                'is_actual': False,  # Still proposed/planned
                'has_metrics': False,
                'rank': None,
                'confidence': 0.0,
                'matched_proposed': None
            })
            unmatched_proposed.append(kmz_loc)
    
    logger.info(f"Added {len(unmatched_proposed)} unmatched KMZ proposed locations "
                f"(excluded {len(matches)} matched)")
    
    # 4. GENERATE COMPREHENSIVE METADATA
    metadata = {
        'total_locations': len(final_locations),
        'csv_locations': len(csv_locations),
        'kmz_existing': len(kmz_existing),
        'kmz_proposed_total': len(kmz_proposed),
        'kmz_proposed_kept': len(unmatched_proposed),
        'matches_found': len(matches),
        'proposed_replaced': len(matches),
        'match_details': [
            {
                'csv_name': match[0].get('Property Name', 'Unknown'),
                'csv_address': match[0].get('Address', ''),
                'csv_city': match[0].get('City', ''),
                'csv_state': match[0].get('State Code', ''),
                'kmz_name': match[1]['name'],
                'kmz_address': match[1].get('address', ''),
                'kmz_city': match[1]['city'],
                'kmz_state': match[1]['state'],
                'confidence': round(match[2], 3),
                'distance_meters': round(match[3], 2)
            }
            for match in matches
        ],
        'unmatched_proposed': [
            {
                'name': loc['name'],
                'city': loc['city'],
                'state': loc['state'],
                'reason': 'No matching CSV location found within threshold'
            }
            for loc in unmatched_proposed
        ],
        'source_breakdown': {
            'csv': len(csv_locations),
            'kmz_existing': len(kmz_existing),
            'kmz_proposed': len(unmatched_proposed)
        }
    }
    
    logger.info(f"Merge complete: {metadata['total_locations']} total locations")
    
    return final_locations, metadata


def convert_kmz_to_standard_format(kmz_location):
    """
    Convert KMZ location format to match CSV format for downstream processing.
    
    This ensures all locations have the same structure, making it easier to:
    - Generate KMZ output files
    - Perform county lookups
    - Calculate rankings
    - Display in UI
    
    Args:
        kmz_location (dict): KMZ location with keys:
            - name, address, city, state, zip, latitude, longitude, 
              year_opened, web_link, extended_data
    
    Returns:
        dict: Standardized location data matching CSV structure
    """
    # Clean up year_opened (0 or "0" means unknown/not set)
    year_opened = kmz_location.get('year_opened', '')
    if year_opened == '0' or year_opened == 0 or year_opened == '':
        year_opened = None
    
    # Build standardized location dict
    standardized = {
        'Property Name': kmz_location['name'],
        'Address': kmz_location.get('address', ''),
        'City': kmz_location.get('city', ''),
        'State': kmz_location.get('state', ''),
        'State Code': kmz_location.get('state', ''),
        'Zip Code': kmz_location.get('zip', ''),
        'Latitude': kmz_location.get('latitude', 0.0),
        'Longitude': kmz_location.get('longitude', 0.0),
        
        # Fields that KMZ locations don't have (CSV-only)
        'Rank': None,
        'Visits': None,
        'sq ft': None,
        'Visits / sq ft': None,
        'Store Id': None,
        'Chain Id': None,
        'Chain Name': None,
        'Id': None,  # Placer.ai ID
        'Type': 'venue',
        
        # Fields that KMZ may have
        'Year_opened': year_opened,
        'Web_Link': kmz_location.get('web_link', ''),
        
        # Preserve all extended data from KMZ
        'extended_data': kmz_location.get('extended_data', {}),
        
        # Metadata flags
        '_source': 'kmz',
        '_is_proposed': '(proposed)' in kmz_location['name'].lower() or 
                       '(u/c)' in kmz_location['name'].lower()
    }
    
    return standardized


def deduplicate_locations(locations, distance_threshold=50):
    """
    Remove duplicate locations based on geographic proximity.
    
    When two locations are within the threshold distance:
    - Keep the one with higher priority (CSV > KMZ existing > KMZ proposed)
    - Keep the one with more complete data if same priority
    
    Args:
        locations (list): List of location dicts with 'source' and 'data' keys
        distance_threshold (float): Distance in meters to consider duplicates (default: 50m)
    
    Returns:
        list: Deduplicated locations
    """
    from location_matcher import haversine_distance, is_valid_coordinate
    
    unique_locations = []
    
    # Sort by priority: CSV > KMZ existing > KMZ proposed
    priority_order = {'csv': 3, 'kmz_existing': 2, 'kmz_proposed': 1}
    sorted_locations = sorted(
        locations, 
        key=lambda x: priority_order.get(x['source'], 0),
        reverse=True
    )
    
    logger.info(f"Deduplicating {len(locations)} locations (threshold: {distance_threshold}m)")
    duplicates_removed = 0
    
    for loc in sorted_locations:
        is_duplicate = False
        loc_data = loc['data']
        
        # Check against all unique locations found so far
        for unique_loc in unique_locations:
            unique_data = unique_loc['data']
            
            # Quick check: must be same city and state
            if (loc_data.get('City') == unique_data.get('City') and 
                loc_data.get('State Code') == unique_data.get('State Code')):
                
                # Calculate distance
                try:
                    lat1 = float(loc_data.get('Latitude', 0))
                    lon1 = float(loc_data.get('Longitude', 0))
                    lat2 = float(unique_data.get('Latitude', 0))
                    lon2 = float(unique_data.get('Longitude', 0))
                    
                    # Skip if coordinates are invalid
                    if not is_valid_coordinate(lat1, lon1) or not is_valid_coordinate(lat2, lon2):
                        continue
                    
                    distance = haversine_distance(lat1, lon1, lat2, lon2)
                    
                    if distance <= distance_threshold:
                        is_duplicate = True
                        duplicates_removed += 1
                        logger.debug(f"Duplicate found: '{loc_data.get('Property Name')}' "
                                   f"within {distance:.1f}m of '{unique_data.get('Property Name')}'")
                        break
                        
                except (ValueError, TypeError) as e:
                    logger.debug(f"Error calculating distance for deduplication: {str(e)}")
                    continue
        
        if not is_duplicate:
            unique_locations.append(loc)
    
    logger.info(f"Deduplication complete: removed {duplicates_removed} duplicates, "
                f"kept {len(unique_locations)} unique locations")
    
    return unique_locations


def enrich_location_data(location, county_name=None, additional_data=None):
    """
    Enrich a location with additional data like county name, computed fields, etc.
    
    Args:
        location (dict): Location data
        county_name (str): County name from reverse geocoding
        additional_data (dict): Any additional fields to add
    
    Returns:
        dict: Enriched location data
    """
    enriched = location.copy()
    
    if county_name:
        enriched['County'] = county_name
    
    if additional_data:
        enriched.update(additional_data)
    
    return enriched


def generate_merge_summary(metadata):
    """
    Generate a human-readable summary of the merge operation.
    
    Args:
        metadata (dict): Merge metadata from merge_datasets()
    
    Returns:
        str: Formatted summary text
    """
    summary = []
    summary.append("=" * 80)
    summary.append("MERGE SUMMARY")
    summary.append("=" * 80)
    summary.append("")
    summary.append("INPUT:")
    summary.append(f"  • CSV locations (Placer.ai):      {metadata['csv_locations']}")
    summary.append(f"  • KMZ existing locations:         {metadata['kmz_existing']}")
    summary.append(f"  • KMZ proposed locations:         {metadata['kmz_proposed_total']}")
    summary.append("")
    summary.append("MATCHING:")
    summary.append(f"  • Matches found:                  {metadata['matches_found']}")
    summary.append(f"  • Proposed locations replaced:    {metadata['proposed_replaced']}")
    summary.append(f"  • Proposed locations kept:        {metadata['kmz_proposed_kept']}")
    summary.append("")
    summary.append("OUTPUT:")
    summary.append(f"  • Total unique locations:         {metadata['total_locations']}")
    summary.append("")
    summary.append("BREAKDOWN BY SOURCE:")
    summary.append(f"  • CSV (actual data):              {metadata['source_breakdown']['csv']}")
    summary.append(f"  • KMZ existing (preserved):       {metadata['source_breakdown']['kmz_existing']}")
    summary.append(f"  • KMZ proposed (still pending):   {metadata['source_breakdown']['kmz_proposed']}")
    summary.append("")
    
    if metadata['match_details']:
        summary.append("REPLACED PROPOSED LOCATIONS:")
        for idx, match in enumerate(metadata['match_details'], 1):
            summary.append(f"  {idx}. {match['kmz_name']}")
            summary.append(f"     → Replaced with: {match['csv_name']}")
            summary.append(f"     Location: {match['csv_city']}, {match['csv_state']}")
            summary.append(f"     Distance: {match['distance_meters']}m | "
                         f"Confidence: {match['confidence']*100:.0f}%")
            summary.append("")
    
    if metadata['unmatched_proposed']:
        summary.append("PROPOSED LOCATIONS STILL PENDING:")
        for idx, loc in enumerate(metadata['unmatched_proposed'], 1):
            summary.append(f"  {idx}. {loc['name']}")
            summary.append(f"     Location: {loc['city']}, {loc['state']}")
            summary.append(f"     Reason: {loc['reason']}")
            summary.append("")
    
    summary.append("=" * 80)
    
    return "\n".join(summary)


def validate_merged_data(final_locations):
    """
    Validate the merged dataset for common issues.
    
    Args:
        final_locations (list): Merged location data
    
    Returns:
        dict: Validation results with warnings and errors
    """
    warnings = []
    errors = []
    
    for idx, loc in enumerate(final_locations):
        data = loc['data']
        
        # Check for required fields
        if not data.get('Property Name'):
            errors.append(f"Location {idx+1}: Missing property name")
        
        if not data.get('City'):
            warnings.append(f"Location {idx+1}: Missing city")
        
        if not data.get('State Code'):
            warnings.append(f"Location {idx+1}: Missing state")
        
        # Check coordinates
        lat = data.get('Latitude', 0)
        lon = data.get('Longitude', 0)
        
        if lat == 0 and lon == 0:
            errors.append(f"Location {idx+1} ({data.get('Property Name')}): Invalid coordinates (0,0)")
        
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            errors.append(f"Location {idx+1} ({data.get('Property Name')}): "
                        f"Coordinates out of range ({lat}, {lon})")
    
    return {
        'valid': len(errors) == 0,
        'warnings': warnings,
        'errors': errors,
        'total_locations': len(final_locations),
        'locations_with_warnings': len(warnings),
        'locations_with_errors': len(errors)
    }


def calculate_state_statistics(final_locations):
    """
    Calculate statistics needed for KMZ generation (state store counts, total ranked, etc.)
    
    Args:
        final_locations (list): List of location dicts with 'source' and 'data' keys
    
    Returns:
        dict: Statistics including:
            - state_store_counts (dict): Count of stores per state
            - total_ranked_stores (int): Total number of locations with ranks (per state)
            - total_ranked_stores_us (int): Total number of ranked locations across ALL states
            - total_stores_us (int): Total number of stores across ALL states
            - average_visits_by_state (dict): Average visits per state
            - total_visits_by_state (dict): Total visits per state
            - states (list): List of unique state codes
    """
    state_counts = {}
    total_ranked = 0
    total_ranked_us = 0
    total_stores_us = 0
    
    # Track visits by state for average calculation
    visits_by_state = {}  # state -> list of visit counts
    total_visits_by_state = {}  # state -> sum of all visits
    
    for loc in final_locations:
        data = loc['data']
        state = data.get('State Code', data.get('State', 'Unknown'))
        
        # Count stores per state
        state_counts[state] = state_counts.get(state, 0) + 1
        total_stores_us += 1
        
        # Count ranked stores (those with Placer.ai rank data)
        if data.get('Rank') is not None:
            total_ranked += 1
            total_ranked_us += 1
        
        # Track visits for average calculation
        visits = data.get('Visits')
        if visits is not None:
            try:
                visits_value = float(visits)
                if state not in visits_by_state:
                    visits_by_state[state] = []
                    total_visits_by_state[state] = 0
                visits_by_state[state].append(visits_value)
                total_visits_by_state[state] += visits_value
            except (ValueError, TypeError):
                pass
    
    # Calculate average visits per state
    average_visits_by_state = {}
    for state, visit_list in visits_by_state.items():
        if visit_list:
            average_visits_by_state[state] = sum(visit_list) / len(visit_list)
        else:
            average_visits_by_state[state] = 0
    
    return {
        'state_store_counts': state_counts,
        'total_ranked_stores': total_ranked,  # This appears to be overall in original code
        'total_ranked_stores_us': total_ranked_us,
        'total_stores_us': total_stores_us,
        'average_visits_by_state': average_visits_by_state,
        'total_visits_by_state': total_visits_by_state,
        'states': sorted(list(state_counts.keys()))
    }


def prepare_kmz_metadata(final_locations, date_range=None):
    """
    Prepare metadata dict for KMZ generation.
    
    Args:
        final_locations (list): List of location dicts with 'source' and 'data' keys
        date_range (str): Optional date range string (e.g., "Apr 1 - Jun 2023")
    
    Returns:
        dict: Metadata for KMZ generation including:
            - date_range (str): Date range for the data
            - total_ranked_stores (int): Total ranked locations (overall)
            - total_ranked_stores_us (int): Total ranked locations across US
            - total_stores_us (int): Total stores across US
            - state_store_counts (dict): Store count per state
            - average_visits_by_state (dict): Average visits per state
            - total_visits_by_state (dict): Total visits per state
    """
    # Calculate statistics
    stats = calculate_state_statistics(final_locations)
    
    # Determine date range
    if date_range is None:
        # Try to infer from CSV data if available
        date_range = infer_date_range_from_locations(final_locations)
    
    metadata = {
        'date_range': date_range or 'Oct 1, 2024 - Sep 30, 2025',
        'total_ranked_stores': stats['total_ranked_stores'],
        'total_ranked_stores_us': stats['total_ranked_stores_us'],
        'total_stores_us': stats['total_stores_us'],
        'state_store_counts': stats['state_store_counts'],
        'average_visits_by_state': stats['average_visits_by_state'],
        'total_visits_by_state': stats['total_visits_by_state']
    }
    
    return metadata


def infer_date_range_from_locations(final_locations):
    """
    Try to infer date range from location data or filenames.
    
    Args:
        final_locations (list): List of location dicts
    
    Returns:
        str: Date range string or None if cannot be inferred
    """
    # Check if any location has date range metadata
    for loc in final_locations:
        data = loc['data']
        
        # Check for date range in extended data
        if 'extended_data' in data:
            date_range = data['extended_data'].get('date_range')
            if date_range:
                return date_range
        
        # Check source file name for date patterns
        source_file = data.get('_source_file', '')
        
        # Common patterns in Placer.ai exports:
        # "Ranking_Index_-_7_Brew_Coffee_-_Oct_1__2024_-_Sep_30__2025.csv"
        import re
        
        # Pattern: Month_Day__Year_-_Month_Day__Year
        pattern = r'([A-Z][a-z]{2})_(\d{1,2})__(\d{4})_-_([A-Z][a-z]{2})_(\d{1,2})__(\d{4})'
        match = re.search(pattern, source_file)
        
        if match:
            start_month, start_day, start_year = match.group(1), match.group(2), match.group(3)
            end_month, end_day, end_year = match.group(4), match.group(5), match.group(6)
            
            # Format as "Oct 1, 2024 - Sep 30, 2025"
            return f"{start_month} {start_day}, {start_year} - {end_month} {end_day}, {end_year}"
    
    return None


def group_locations_by_state(final_locations):
    """
    Group locations by state for state-level KMZ generation.
    
    Args:
        final_locations (list): List of location dicts with 'source' and 'data' keys
    
    Returns:
        dict: Mapping of state code -> list of location data dicts
    """
    states = {}
    
    for loc in final_locations:
        data = loc['data']
        state = data.get('State Code', data.get('State', 'Unknown'))
        
        if state not in states:
            states[state] = []
        
        states[state].append(data)
    
    return states


# Example usage and testing
if __name__ == "__main__":
    import json
    
    print("\n" + "=" * 80)
    print("DATA MERGER TEST")
    print("=" * 80 + "\n")
    
    # Sample test data
    csv_locations = [
        {
            'Property Name': '7 Brew Coffee',
            'City': 'Athens',
            'State Code': 'GA',
            'Latitude': 33.9390,
            'Longitude': -83.4536,
            'Rank': 1,
            'Visits': 50000,
            'sq ft': 1200
        },
        {
            'Property Name': '7 Brew Coffee',
            'City': 'Augusta',
            'State Code': 'GA',
            'Latitude': 33.5125,
            'Longitude': -82.0485,
            'Rank': 2,
            'Visits': 45000,
            'sq ft': 1100
        }
    ]
    
    kmz_existing = [
        {
            'name': '7 Brew Coffee-Buford, GA',
            'city': 'Buford',
            'state': 'GA',
            'latitude': 34.083,
            'longitude': -83.9887,
            'address': '3700 Buford Dr',
            'zip': '30519'
        }
    ]
    
    kmz_proposed = [
        {
            'name': '7 Brew Coffee-Athens, GA (proposed)',
            'city': 'Athens',
            'state': 'GA',
            'latitude': 33.9389,
            'longitude': -83.4535,
            'address': '3455 Atlanta Hwy',
            'zip': '30606'
        },
        {
            'name': '7 Brew Coffee-Woodstock, GA (proposed)',
            'city': 'Woodstock',
            'state': 'GA',
            'latitude': 34.101,
            'longitude': -84.519,
            'address': '',
            'zip': ''
        }
    ]
    
    # Simulate matches (Athens matched)
    matches = [
        (csv_locations[0], kmz_proposed[0], 0.95, 15.3)
    ]
    
    print("Test Data:")
    print(f"  CSV locations: {len(csv_locations)}")
    print(f"  KMZ existing: {len(kmz_existing)}")
    print(f"  KMZ proposed: {len(kmz_proposed)}")
    print(f"  Matches: {len(matches)}")
    print()
    
    # Run merge
    print("Running merge...")
    final_locations, metadata = merge_datasets(
        csv_locations, kmz_existing, kmz_proposed, matches
    )
    
    print(f"\nMerge complete!")
    print(f"  Final locations: {len(final_locations)}")
    print()
    
    # Display summary
    print(generate_merge_summary(metadata))
    
    # Test new statistics calculation
    print("\n" + "=" * 80)
    print("TESTING NEW STATISTICS CALCULATION")
    print("=" * 80 + "\n")
    
    # Prepare metadata
    kmz_metadata = prepare_kmz_metadata(final_locations)
    
    print("KMZ Metadata:")
    print(f"  Date Range: {kmz_metadata['date_range']}")
    print(f"  Total Ranked Stores: {kmz_metadata['total_ranked_stores']}")
    print(f"  Total Ranked Stores US: {kmz_metadata['total_ranked_stores_us']}")
    print(f"  Total Stores US: {kmz_metadata['total_stores_us']}")
    print(f"  State Store Counts: {kmz_metadata['state_store_counts']}")
    print(f"  Average Visits by State:")
    for state, avg in kmz_metadata['average_visits_by_state'].items():
        print(f"    {state}: {avg:,.0f}")
    print(f"  Total Visits by State:")
    for state, total in kmz_metadata['total_visits_by_state'].items():
        print(f"    {state}: {total:,.0f}")
    
    # Validate
    print("\n" + "=" * 80)
    print("VALIDATION")
    print("=" * 80 + "\n")
    
    validation = validate_merged_data(final_locations)
    
    print(f"  Valid: {validation['valid']}")
    print(f"  Warnings: {validation['locations_with_warnings']}")
    print(f"  Errors: {validation['locations_with_errors']}")
    
    if validation['warnings']:
        print("\n  Warnings:")
        for warning in validation['warnings'][:5]:
            print(f"    - {warning}")
    
    if validation['errors']:
        print("\n  Errors:")
        for error in validation['errors'][:5]:
            print(f"    - {error}")
    
    # Show final locations breakdown
    print("\n" + "=" * 80)
    print("FINAL LOCATIONS BREAKDOWN")
    print("=" * 80 + "\n")
    
    for source_type in ['csv', 'kmz_existing', 'kmz_proposed']:
        locs = [l for l in final_locations if l['source'] == source_type]
        if locs:
            print(f"{source_type.upper()}: {len(locs)} locations")
            for loc in locs[:3]:
                data = loc['data']
                print(f"  - {data.get('Property Name')} ({data.get('City')}, {data.get('State Code')})")
            if len(locs) > 3:
                print(f"  ... and {len(locs) - 3} more")
            print()
    
    print("=" * 80)
    print("✓ All tests complete!")
    print("=" * 80 + "\n")
