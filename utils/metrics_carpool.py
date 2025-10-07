"""
Real-time metrics tracking for carpooling OMD simulation.
Designed for easy frontend integration.
"""

import json
from typing import List, Dict, Callable
from collections import deque
from core.entities import Request, Driver, Trip, RequestStatus

class MetricsTracker:
    """Track and report simulation metrics in real-time"""
    
    def __init__(self, update_interval: float = 10.0, 
                 history_size: int = 100,
                 enable_streaming: bool = True):
        """
        Args:
            update_interval: How often to aggregate metrics (seconds)
            history_size: Number of recent events to keep
            enable_streaming: Enable event streaming for frontend
        """
        self.update_interval = update_interval
        self.history_size = history_size
        self.enable_streaming = enable_streaming
        
        # Event callbacks for streaming
        self.event_callbacks = []
        
        # Cumulative counters
        self.total_requests = 0
        self.total_matches = 0
        self.total_quits = 0
        self.total_dynamic_insertions = 0
        
        # Cost tracking
        self.total_waiting_cost = 0.0
        self.total_routing_cost = 0.0
        self.total_quit_penalty = 0.0
        self.total_detour_penalty = 0.0
        
        # Pool utilization
        self.pool_stats = {1: 0, 2: 0, 3: 0}  # trips by pool size
        
        # Time series data
        self.waiting_times = []
        self.detour_ratios = []
        self.match_times = []
        
        # Recent events (for frontend display)
        self.recent_events = deque(maxlen=history_size)
        
        # Driver statistics
        self.driver_stats = {}  # driver_type_id -> {trips, passengers}
        
        # Live state snapshots
        self.snapshots = []
        self.last_snapshot_time = 0
    
    def register_callback(self, callback: Callable):
        """Register callback for event streaming"""
        self.event_callbacks.append(callback)
    
    def _emit_event(self, event: dict):
        """Emit event to all registered callbacks"""
        if self.enable_streaming:
            for callback in self.event_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    print(f"⚠ Event callback failed: {e}")
    
    def record_request_arrival(self, request: Request, time: float):
        """Record new request arrival"""
        self.total_requests += 1
        
        event = {
            'type': 'request_arrival',
            'time': time,
            'request_id': request.id,
            'origin': {'lat': request.origin.lat, 'lon': request.origin.lon},
            'destination': {'lat': request.destination.lat, 'lon': request.destination.lon}
        }
        self.recent_events.append(event)
        self._emit_event(event)
    
    def record_match(self, trip: Trip, time: float):
        """Record successful match"""
        self.total_matches += len(trip.passengers)
        pool_size = len(trip.passengers)
        self.pool_stats[pool_size] = self.pool_stats.get(pool_size, 0) + 1
        
        # Update driver stats
        driver_type_id = trip.driver.type.id
        if driver_type_id not in self.driver_stats:
            self.driver_stats[driver_type_id] = {'trips': 0, 'passengers': 0}
        self.driver_stats[driver_type_id]['trips'] += 1
        self.driver_stats[driver_type_id]['passengers'] += pool_size
        
        # Record waiting times
        for passenger in trip.passengers:
            waiting_time = time - passenger.arrival_time
            self.waiting_times.append(waiting_time)
            self.match_times.append(time)
            
            # Record waiting cost
            waiting_cost = waiting_time * passenger.waiting_cost_rate
            self.total_waiting_cost += waiting_cost
        
        # Record routing cost
        self.total_routing_cost += trip.total_route_cost
        
        event = {
            'type': 'match',
            'time': time,
            'trip_id': trip.id,
            'driver_id': trip.driver.id,
            'passengers': [p.id for p in trip.passengers],
            'pool_size': pool_size,
            'route_cost': trip.total_route_cost
        }
        self.recent_events.append(event)
        self._emit_event(event)
    
    def record_quit(self, request: Request, time: float, quit_penalty: float):
        """Record request quit"""
        self.total_quits += 1
        self.total_quit_penalty += quit_penalty
        
        waiting_time = time - request.arrival_time
        
        event = {
            'type': 'quit',
            'time': time,
            'request_id': request.id,
            'waiting_time': waiting_time,
            'penalty': quit_penalty
        }
        self.recent_events.append(event)
        self._emit_event(event)
    
    def record_dynamic_insertion(self, request: Request, trip: Trip, time: float):
        """Record dynamic insertion into existing trip"""
        self.total_dynamic_insertions += 1
        
        event = {
            'type': 'dynamic_insertion',
            'time': time,
            'request_id': request.id,
            'trip_id': trip.id,
            'new_pool_size': len(trip.passengers)
        }
        self.recent_events.append(event)
        self._emit_event(event)
    
    def record_trip_complete(self, trip: Trip, time: float):
        """Record trip completion"""
        # Record detour ratios
        for passenger in trip.passengers:
            if passenger.detour_ratio:
                self.detour_ratios.append(passenger.detour_ratio)
                
                # Record detour penalty if exceeded
                if passenger.detour_ratio > 1.5:
                    excess = passenger.actual_trip_duration - (1.5 * passenger.solo_trip_duration)
                    # Assume detour_penalty_per_sec from config
                    detour_penalty = excess * 2.0  # This should come from config
                    self.total_detour_penalty += detour_penalty
        
        event = {
            'type': 'trip_complete',
            'time': time,
            'trip_id': trip.id,
            'passengers': [p.id for p in trip.passengers],
            'total_cost': trip.total_route_cost
        }
        self.recent_events.append(event)
        self._emit_event(event)
    
    def snapshot_state(self, time: float, active_requests: List[Request],
                      available_drivers: Dict[int, int], active_trips: List[Trip]):
        """Take snapshot of current system state"""
        if time - self.last_snapshot_time < self.update_interval:
            return
        
        snapshot = {
            'time': time,
            'active_requests': len(active_requests),
            'available_drivers': available_drivers.copy(),
            'active_trips': len(active_trips),
            'passengers_in_transit': sum(len(t.passengers) for t in active_trips)
        }
        
        self.snapshots.append(snapshot)
        self.last_snapshot_time = time
        
        # Emit snapshot
        self._emit_event({'type': 'snapshot', **snapshot})
    
    def get_current_metrics(self, time: float) -> dict:
        """Get current metrics snapshot"""
        total_completed = self.total_matches + self.total_quits
        match_rate = self.total_matches / total_completed if total_completed > 0 else 0
        
        avg_waiting_time = (sum(self.waiting_times) / len(self.waiting_times) 
                          if self.waiting_times else 0)
        avg_detour = (sum(self.detour_ratios) / len(self.detour_ratios)
                     if self.detour_ratios else 0)
        
        total_trips = sum(self.pool_stats.values())
        avg_pool_size = (sum(k * v for k, v in self.pool_stats.items()) / total_trips
                        if total_trips > 0 else 0)
        
        insertion_rate = (self.total_dynamic_insertions / self.total_requests
                         if self.total_requests > 0 else 0)

        total_cost = (self.total_waiting_cost + self.total_routing_cost +
                     self.total_quit_penalty + self.total_detour_penalty)

        return {
            'simulation_time': time,
            'cumulative': {
                'total_requests': self.total_requests,
                'total_matches': self.total_matches,
                'total_quits': self.total_quits,
                'match_rate': match_rate,
                'total_cost': total_cost,
                'avg_waiting_time': avg_waiting_time,
                'avg_detour_ratio': avg_detour
            },
            'carpooling': {
                'pool_utilization': self.pool_stats.copy(),
                'avg_pool_size': avg_pool_size,
                'total_trips': total_trips,
                'dynamic_insertions': self.total_dynamic_insertions,
                'insertion_rate': insertion_rate
            },
            'cost_breakdown': {
                'waiting_cost': self.total_waiting_cost,
                'routing_cost': self.total_routing_cost,
                'quit_penalty': self.total_quit_penalty,
                'detour_penalty': self.total_detour_penalty
            },
            'driver_stats': self.driver_stats.copy(),
            'recent_events': list(self.recent_events)[-10:]  # Last 10 events
        }

    def get_summary(self) -> dict:
        """Get final summary statistics"""
        metrics = self.get_current_metrics(0)
        return {
            'total_requests': self.total_requests,
            'total_matches': self.total_matches,
            'total_quits': self.total_quits,
            'match_rate': metrics['cumulative']['match_rate'],
            'avg_pool_size': metrics['carpooling']['avg_pool_size'],
            'dynamic_insertions': self.total_dynamic_insertions,
            'total_cost': metrics['cumulative']['total_cost']
        }

    def export_to_json(self, filename: str, time: float):
        """Export metrics to JSON file"""
        metrics = self.get_current_metrics(time)
        with open(filename, 'w') as f:
            json.dump(metrics, f, indent=2)

    def get_time_series(self) -> dict:
        """Get time series data for visualization"""
        return {
            'waiting_times': self.waiting_times,
            'detour_ratios': self.detour_ratios,
            'match_times': self.match_times,
            'snapshots': self.snapshots
        }

    def get_summary(self) -> dict:
        """Get final summary statistics"""
        total_completed = self.total_matches + self.total_quits
        match_rate = self.total_matches / total_completed if total_completed > 0 else 0

        avg_pool_size = 0
        if self.pool_stats:
            total_trips = sum(self.pool_stats.values())
            if total_trips > 0:
                avg_pool_size = sum(k * v for k, v in self.pool_stats.items()) / total_trips

        total_cost = (self.total_waiting_cost + self.total_routing_cost +
                     self.total_quit_penalty + self.total_detour_penalty)

        return {
            'total_requests': self.total_requests,
            'total_matches': self.total_matches,
            'total_quits': self.total_quits,
            'match_rate': match_rate,
            'avg_pool_size': avg_pool_size,
            'dynamic_insertions': self.total_dynamic_insertions,
            'total_cost': total_cost
        }