"""
Destination clustering for carpooling matching.
Groups requests by destination proximity.
"""

import numpy as np
from typing import List, Dict
from sklearn.cluster import DBSCAN
from core.entities import Request, Location

class DestinationClusterer:
    """Cluster requests by destination proximity"""
    
    def __init__(self, radius_km: float = 1.0):
        """
        Args:
            radius_km: Clustering radius in kilometers
        """
        self.radius_km = radius_km
        # Convert km to degrees (approximate: 1 degree ≈ 111 km)
        self.eps_degrees = radius_km / 111.0
    
    def cluster_requests(self, requests: List[Request]) -> Dict[int, List[Request]]:
        """
        Cluster requests by destination using DBSCAN.
        
        Args:
            requests: List of active requests
            
        Returns:
            Dict mapping cluster_id -> list of requests
        """
        if not requests:
            return {}
        
        # Extract destination coordinates
        destinations = np.array([
            [r.destination.lat, r.destination.lon] for r in requests
        ])
        
        # Apply DBSCAN clustering
        clustering = DBSCAN(
            eps=self.eps_degrees,
            min_samples=1,  # Allow single-request clusters
            metric='euclidean'
        ).fit(destinations)
        
        # Group requests by cluster
        clusters = {}
        for request, label in zip(requests, clustering.labels_):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(request)
        
        return clusters
    
    def get_cluster_centroid(self, requests: List[Request]) -> Location:
        """
        Compute centroid of a cluster.
        
        Args:
            requests: Requests in the cluster
            
        Returns:
            Centroid location
        """
        lats = [r.destination.lat for r in requests]
        lons = [r.destination.lon for r in requests]
        
        return Location(
            lat=np.mean(lats),
            lon=np.mean(lons)
        )
    
    def are_destinations_compatible(self, req1: Request, req2: Request) -> bool:
        """
        Check if two requests have compatible destinations.
        
        Args:
            req1, req2: Requests to check
            
        Returns:
            True if destinations are within clustering radius
        """
        distance_deg = self._haversine_distance(
            req1.destination.lat, req1.destination.lon,
            req2.destination.lat, req2.destination.lon
        )
        
        return distance_deg <= self.eps_degrees
    
    def _haversine_distance(self, lat1: float, lon1: float, 
                           lat2: float, lon2: float) -> float:
        """
        Compute Haversine distance between two points.
        
        Returns:
            Distance in degrees (for comparison with eps)
        """
        from math import radians, cos, sin, sqrt, atan2
        
        R = 111.0  # Approximate km per degree
        
        dlat = abs(lat2 - lat1)
        dlon = abs(lon2 - lon1)
        
        # Simplified distance in degrees
        return sqrt(dlat**2 + dlon**2)
    
    def filter_cluster_by_capacity(self, cluster: List[Request], 
                                   capacity: int) -> List[List[Request]]:
        """
        Split large cluster into sub-groups of size ≤ capacity.
        
        Args:
            cluster: List of requests in cluster
            capacity: Maximum group size
            
        Returns:
            List of request groups
        """
        if len(cluster) <= capacity:
            return [cluster]
        
        # Simple greedy splitting
        groups = []
        current_group = []
        
        for request in cluster:
            if len(current_group) < capacity:
                current_group.append(request)
            else:
                groups.append(current_group)
                current_group = [request]
        
        if current_group:
            groups.append(current_group)
        
        return groups
