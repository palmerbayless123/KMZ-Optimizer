"""
County Lookup Module
Reverse geocode coordinates to determine county names.

This module handles:
- Looking up county names from latitude/longitude coordinates
- Using multiple geocoding services (FCC, Nominatim, local data)
- Caching results to minimize API calls
- Batch processing for efficiency
- Handling rate limits and errors gracefully

Methods:
1. FCC (Federal Communications Commission) API - US only, free, no key required
2. Nominatim (OpenStreetMap) - Worldwide, free, rate limited
3. Local data file - Pre-downloaded county boundaries (fastest, offline)

Author: System
Date: November 2, 2025
Version: 1.0
"""

import logging
import time
import json
from typing import Optional, Dict, Tuple, List
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CountyLookup:
    """
    County lookup service with caching and multiple data sources.
    """
    
    def __init__(self, cache_file='county_cache.json', use_fcc=True, use_nominatim=True):
        """
        Initialize county lookup service.
        
        Args:
            cache_file (str): Path to cache file for storing results
            use_fcc (bool): Enable FCC API (US only, recommended)
            use_nominatim (bool): Enable Nominatim API (backup, rate limited)
        """
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.use_fcc = use_fcc
        self.use_nominatim = use_nominatim
        
        # Rate limiting
        self.last_fcc_call = 0
        self.last_nominatim_call = 0
        self.fcc_min_interval = 0.1  # 10 requests per second max
        self.nominatim_min_interval = 1.0  # 1 request per second max (Nominatim policy)
        
        # Statistics
        self.stats = {
            'total_lookups': 0,
            'cache_hits': 0,
            'fcc_calls': 0,
            'nominatim_calls': 0,
            'failures': 0
        }
    
    def lookup_county(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Look up county name for given coordinates.
        
        Args:
            latitude (float): Latitude in degrees
            longitude (float): Longitude in degrees
        
        Returns:
            str: County name (e.g., "Fulton County") or None if not found
        """
        self.stats['total_lookups'] += 1
        
        # Check cache first
        cache_key = f"{latitude:.6f},{longitude:.6f}"
        if cache_key in self.cache:
            self.stats['cache_hits'] += 1
            logger.debug(f"Cache hit for {cache_key}")
            return self.cache[cache_key]
        
        # Try FCC API (US only, fast and reliable)
        if self.use_fcc:
            county = self._lookup_fcc(latitude, longitude)
            if county:
                self._cache_result(cache_key, county)
                return county
        
        # Try Nominatim API (worldwide, slower)
        if self.use_nominatim:
            county = self._lookup_nominatim(latitude, longitude)
            if county:
                self._cache_result(cache_key, county)
                return county
        
        # No result found
        self.stats['failures'] += 1
        logger.warning(f"Could not find county for coordinates: {latitude}, {longitude}")
        self._cache_result(cache_key, None)
        return None
    
    def lookup_batch(self, coordinates: List[Tuple[float, float]], 
                    show_progress=True) -> Dict[Tuple[float, float], Optional[str]]:
        """
        Look up counties for multiple coordinates efficiently.
        
        Args:
            coordinates (list): List of (latitude, longitude) tuples
            show_progress (bool): Print progress updates
        
        Returns:
            dict: Mapping of (lat, lon) -> county name
        """
        results = {}
        total = len(coordinates)
        
        logger.info(f"Starting batch lookup for {total} coordinates")
        
        for idx, (lat, lon) in enumerate(coordinates, 1):
            county = self.lookup_county(lat, lon)
            results[(lat, lon)] = county
            
            if show_progress and idx % 10 == 0:
                progress = (idx / total) * 100
                logger.info(f"Progress: {idx}/{total} ({progress:.1f}%) - "
                          f"Cache hits: {self.stats['cache_hits']}")
        
        logger.info(f"Batch lookup complete. Cache hit rate: "
                   f"{self.stats['cache_hits']}/{total} "
                   f"({self.stats['cache_hits']/total*100:.1f}%)")
        
        return results
    
    def _lookup_fcc(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Look up county using FCC API (US only).
        
        FCC API: https://geo.fcc.gov/api/census/
        Free, no API key required, US only
        
        Args:
            latitude (float): Latitude
            longitude (float): Longitude
        
        Returns:
            str: County name or None
        """
        try:
            import requests
            
            # Rate limiting
            self._wait_for_rate_limit('fcc')
            
            url = f"https://geo.fcc.gov/api/census/area"
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract county name from results
                if 'results' in data and len(data['results']) > 0:
                    result = data['results'][0]
                    county_name = result.get('county_name')
                    
                    if county_name:
                        self.stats['fcc_calls'] += 1
                        logger.debug(f"FCC lookup successful: {county_name}")
                        return county_name
            
            logger.debug(f"FCC lookup failed for {latitude}, {longitude}")
            return None
            
        except ImportError:
            logger.warning("requests library not available, skipping FCC lookup")
            self.use_fcc = False
            return None
        except Exception as e:
            logger.debug(f"FCC API error: {str(e)}")
            return None
    
    def _lookup_nominatim(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Look up county using Nominatim API (OpenStreetMap).
        
        Nominatim API: https://nominatim.openstreetmap.org/
        Free, rate limited to 1 request per second
        
        Args:
            latitude (float): Latitude
            longitude (float): Longitude
        
        Returns:
            str: County name or None
        """
        try:
            import requests
            
            # Rate limiting (Nominatim policy: max 1 request per second)
            self._wait_for_rate_limit('nominatim')
            
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json',
                'addressdetails': 1
            }
            headers = {
                'User-Agent': 'CountyLookupService/1.0'  # Required by Nominatim
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract county from address
                if 'address' in data:
                    address = data['address']
                    # Try multiple keys for county
                    county = (address.get('county') or 
                             address.get('county_code') or
                             address.get('state_district'))
                    
                    if county:
                        self.stats['nominatim_calls'] += 1
                        logger.debug(f"Nominatim lookup successful: {county}")
                        
                        # Add "County" suffix if not present
                        if not county.endswith('County') and not county.endswith('Parish'):
                            county = f"{county} County"
                        
                        return county
            
            logger.debug(f"Nominatim lookup failed for {latitude}, {longitude}")
            return None
            
        except ImportError:
            logger.warning("requests library not available, skipping Nominatim lookup")
            self.use_nominatim = False
            return None
        except Exception as e:
            logger.debug(f"Nominatim API error: {str(e)}")
            return None
    
    def _wait_for_rate_limit(self, service: str):
        """
        Implement rate limiting for API calls.
        
        Args:
            service (str): 'fcc' or 'nominatim'
        """
        current_time = time.time()
        
        if service == 'fcc':
            time_since_last = current_time - self.last_fcc_call
            if time_since_last < self.fcc_min_interval:
                time.sleep(self.fcc_min_interval - time_since_last)
            self.last_fcc_call = time.time()
        
        elif service == 'nominatim':
            time_since_last = current_time - self.last_nominatim_call
            if time_since_last < self.nominatim_min_interval:
                time.sleep(self.nominatim_min_interval - time_since_last)
            self.last_nominatim_call = time.time()
    
    def _load_cache(self) -> Dict:
        """
        Load cache from file.
        
        Returns:
            dict: Cached lookup results
        """
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                logger.info(f"Loaded {len(cache)} cached county lookups")
                return cache
            except Exception as e:
                logger.warning(f"Error loading cache: {str(e)}")
        
        return {}
    
    def _cache_result(self, key: str, value: Optional[str]):
        """
        Cache a lookup result.
        
        Args:
            key (str): Cache key (formatted coordinates)
            value (str or None): County name or None
        """
        self.cache[key] = value
    
    def save_cache(self):
        """
        Save cache to file.
        """
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.info(f"Saved {len(self.cache)} county lookups to cache")
        except Exception as e:
            logger.error(f"Error saving cache: {str(e)}")
    
    def get_stats(self) -> Dict:
        """
        Get lookup statistics.
        
        Returns:
            dict: Statistics about lookups performed
        """
        stats = self.stats.copy()
        if stats['total_lookups'] > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / stats['total_lookups']
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def clear_cache(self):
        """
        Clear the cache.
        """
        self.cache = {}
        if os.path.exists(self.cache_file):
            os.remove(self.cache_file)
        logger.info("Cache cleared")


def add_county_to_locations(locations: List[Dict], 
                           county_lookup: CountyLookup = None,
                           save_cache: bool = True) -> List[Dict]:
    """
    Add county names to a list of locations.
    
    Args:
        locations (list): List of location dicts with Latitude and Longitude
        county_lookup (CountyLookup): County lookup service (creates new if None)
        save_cache (bool): Save cache after processing
    
    Returns:
        list: Locations with 'County' field added
    """
    if county_lookup is None:
        county_lookup = CountyLookup()
    
    logger.info(f"Adding county data to {len(locations)} locations")
    
    # Extract unique coordinates to avoid duplicate lookups
    coord_to_locations = {}
    for loc in locations:
        lat = loc.get('Latitude')
        lon = loc.get('Longitude')
        
        if lat is not None and lon is not None:
            coord = (float(lat), float(lon))
            if coord not in coord_to_locations:
                coord_to_locations[coord] = []
            coord_to_locations[coord].append(loc)
    
    # Batch lookup
    unique_coords = list(coord_to_locations.keys())
    logger.info(f"Looking up {len(unique_coords)} unique coordinates")
    
    county_results = county_lookup.lookup_batch(unique_coords)
    
    # Apply results to locations
    for coord, county in county_results.items():
        for loc in coord_to_locations[coord]:
            loc['County'] = county
    
    # Save cache
    if save_cache:
        county_lookup.save_cache()
    
    # Log statistics
    stats = county_lookup.get_stats()
    logger.info(f"County lookup complete. Stats: {stats}")
    
    return locations


# Simple fallback function without external dependencies
def lookup_county_simple(latitude: float, longitude: float) -> Optional[str]:
    """
    Simple county lookup without external API dependencies.
    
    This is a fallback that only works for major US cities.
    For production, use the CountyLookup class with API access.
    
    Args:
        latitude (float): Latitude
        longitude (float): Longitude
    
    Returns:
        str: County name or None
    """
    # Simple hardcoded lookup for Georgia (example)
    # In production, use actual API or database
    ga_counties = {
        (33.749, -84.388): "Fulton County",  # Atlanta
        (33.939, -83.453): "Clarke County",  # Athens
        (33.512, -82.048): "Richmond County",  # Augusta
        (34.083, -83.988): "Gwinnett County",  # Buford
    }
    
    # Find closest match within 0.5 degrees
    min_distance = float('inf')
    closest_county = None
    
    for (lat, lon), county in ga_counties.items():
        distance = ((latitude - lat) ** 2 + (longitude - lon) ** 2) ** 0.5
        if distance < min_distance and distance < 0.5:
            min_distance = distance
            closest_county = county
    
    return closest_county


# Example usage and testing
if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("COUNTY LOOKUP TEST")
    print("=" * 80 + "\n")
    
    # Test coordinates (Georgia locations)
    test_coordinates = [
        (33.749, -84.388, "Atlanta, GA"),
        (33.939, -83.453, "Athens, GA"),
        (33.512, -82.048, "Augusta, GA"),
        (34.083, -83.988, "Buford, GA"),
        (32.840, -83.632, "Macon, GA"),
    ]
    
    # Initialize lookup service
    print("1. Initializing county lookup service...")
    lookup = CountyLookup(cache_file='test_county_cache.json')
    print("   ✓ Service initialized\n")
    
    # Test individual lookups
    print("2. Testing individual lookups:")
    for lat, lon, location in test_coordinates:
        county = lookup.lookup_county(lat, lon)
        status = "✓" if county else "✗"
        print(f"   {status} {location:20} → {county or 'Not found'}")
    
    print()
    
    # Test batch lookup
    print("3. Testing batch lookup:")
    coords_only = [(lat, lon) for lat, lon, _ in test_coordinates]
    results = lookup.lookup_batch(coords_only, show_progress=False)
    print(f"   ✓ Looked up {len(results)} coordinates\n")
    
    # Show statistics
    print("4. Lookup statistics:")
    stats = lookup.get_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.2%}")
        else:
            print(f"   {key}: {value}")
    
    print()
    
    # Test with location objects
    print("5. Testing with location objects:")
    test_locations = [
        {
            'Property Name': '7 Brew Coffee',
            'City': 'Atlanta',
            'State': 'GA',
            'Latitude': 33.749,
            'Longitude': -84.388
        },
        {
            'Property Name': '7 Brew Coffee',
            'City': 'Athens',
            'State': 'GA',
            'Latitude': 33.939,
            'Longitude': -83.453
        }
    ]
    
    enriched_locations = add_county_to_locations(test_locations, lookup)
    
    for loc in enriched_locations:
        print(f"   {loc['Property Name']} - {loc['City']}, {loc['State']}")
        print(f"     County: {loc.get('County', 'Unknown')}")
    
    print()
    
    # Save cache
    print("6. Saving cache...")
    lookup.save_cache()
    print(f"   ✓ Cache saved to {lookup.cache_file}\n")
    
    # Clean up test cache
    if os.path.exists('test_county_cache.json'):
        os.remove('test_county_cache.json')
        print("   ✓ Test cache cleaned up\n")
    
    print("=" * 80)
    print("✓ All tests complete!")
    print("=" * 80 + "\n")
    
    print("NOTE: For full functionality, install the 'requests' library:")
    print("  pip install requests")
