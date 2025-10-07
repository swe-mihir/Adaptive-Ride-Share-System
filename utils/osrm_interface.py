"""
OSRM (Open Source Routing Machine) interface with caching.
"""

import requests
from typing import List, Tuple, Optional
from functools import lru_cache
import hashlib
import json

class OSRMClient:
    """Client for OSRM routing service with caching"""
    
    def __init__(self, server_url: str = "http://127.0.0.1:5000", cache_size: int = 10000):
        self.server_url = server_url.rstrip('/')
        self.cache = {}
        self.cache_size = cache_size
        self.cache_hits = 0
        self.cache_misses = 0
        
    def _cache_key(self, coords: List[Tuple[float, float]]) -> str:
        """Generate cache key from coordinates"""
        # Round to 6 decimal places (~0.1m precision)
        rounded = [(round(lat, 6), round(lon, 6)) for lat, lon in coords]
        return hashlib.md5(str(rounded).encode()).hexdigest()
    
    def get_duration(self, origin: Tuple[float, float], 
                    destination: Tuple[float, float]) -> float:
        """
        Get travel duration between two points in seconds.
        
        Args:
            origin: (lat, lon)
            destination: (lat, lon)
            
        Returns:
            Duration in seconds
        """
        return self.get_route([origin, destination])['duration']
    
    def get_distance(self, origin: Tuple[float, float], 
                    destination: Tuple[float, float]) -> float:
        """
        Get travel distance between two points in meters.
        
        Args:
            origin: (lat, lon)
            destination: (lat, lon)
            
        Returns:
            Distance in meters
        """
        return self.get_route([origin, destination])['distance']
    
    def get_route(self, coordinates: List[Tuple[float, float]]) -> dict:
        """
        Get route information for multiple waypoints.
        
        Args:
            coordinates: List of (lat, lon) tuples
            
        Returns:
            dict with 'duration' (seconds), 'distance' (meters), 'geometry'
        """
        cache_key = self._cache_key(coordinates)
        
        # Check cache
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        
        # Build OSRM request
        # OSRM expects lon,lat (not lat,lon)
        coords_str = ';'.join([f"{lon},{lat}" for lat, lon in coordinates])
        url = f"{self.server_url}/route/v1/driving/{coords_str}"
        
        params = {
            'overview': 'false',
            'geometries': 'geojson',
            'steps': 'false'
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if data['code'] != 'Ok':
                raise Exception(f"OSRM error: {data.get('message', 'Unknown error')}")
            
            route = data['routes'][0]
            result = {
                'duration': route['duration'],  # seconds
                'distance': route['distance'],  # meters
                'geometry': route.get('geometry', None)
            }
            
            # Cache result
            if len(self.cache) >= self.cache_size:
                # Simple FIFO eviction
                self.cache.pop(next(iter(self.cache)))
            
            self.cache[cache_key] = result
            return result
            
        except requests.exceptions.RequestException as e:
            # Fallback to Euclidean distance if OSRM fails
            print(f"⚠ OSRM request failed: {e}. Using fallback.")
            return self._fallback_route(coordinates)
    
    def _fallback_route(self, coordinates: List[Tuple[float, float]]) -> dict:
        """Fallback to approximate distance calculation"""
        from math import radians, cos, sin, sqrt, atan2
        
        total_distance = 0.0
        
        for i in range(len(coordinates) - 1):
            lat1, lon1 = coordinates[i]
            lat2, lon2 = coordinates[i + 1]
            
            # Haversine formula
            R = 6371000  # Earth radius in meters
            
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            
            a = (sin(dlat/2)**2 + 
                 cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2)
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            
            total_distance += R * c
        
        # Assume average speed of 40 km/h in urban areas
        avg_speed_mps = 40 * 1000 / 3600  # 11.11 m/s
        duration = total_distance / avg_speed_mps
        
        return {
            'duration': duration,
            'distance': total_distance,
            'geometry': None
        }
    
    def get_matrix(self, sources: List[Tuple[float, float]], 
                   destinations: List[Tuple[float, float]]) -> dict:
        """
        Get distance/duration matrix for multiple sources and destinations.
        Useful for batch queries.
        
        Args:
            sources: List of (lat, lon) source points
            destinations: List of (lat, lon) destination points
            
        Returns:
            dict with 'durations' (2D array), 'distances' (2D array)
        """
        # Combine all coordinates
        all_coords = sources + destinations
        coords_str = ';'.join([f"{lon},{lat}" for lat, lon in all_coords])
        
        # Source and destination indices
        source_indices = ';'.join([str(i) for i in range(len(sources))])
        dest_indices = ';'.join([str(i) for i in range(len(sources), len(all_coords))])
        
        url = f"{self.server_url}/table/v1/driving/{coords_str}"
        params = {
            'sources': source_indices,
            'destinations': dest_indices
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['code'] != 'Ok':
                raise Exception(f"OSRM error: {data.get('message', 'Unknown error')}")
            
            return {
                'durations': data['durations'],
                'distances': data.get('distances', None)
            }
            
        except requests.exceptions.RequestException as e:
            print(f"⚠ OSRM matrix request failed: {e}. Using fallback.")
            # Fallback: compute pairwise
            durations = []
            for src in sources:
                row = []
                for dst in destinations:
                    route = self._fallback_route([src, dst])
                    row.append(route['duration'])
                durations.append(row)
            return {'durations': durations, 'distances': None}
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        total = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total if total > 0 else 0
        
        return {
            'cache_size': len(self.cache),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': hit_rate
        }
    
    def clear_cache(self):
        """Clear the cache"""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
