"""
FCFS Simulator - uses simple FCFS matching instead of optimal assignment.
"""

import heapq
import numpy as np
from typing import List, Dict
from dataclasses import dataclass
from enum import Enum

from core.entities import (
    Request, Driver, Trip, Location, DriverType, RequestStatus, DriverStatus,
    generate_request_id, generate_driver_id, generate_trip_id
)
from utils.osrm_interface import OSRMClient
from algorithms.fcfs_matcher import FCFSMatcher
from utils.metrics_carpool import MetricsTracker
from simulation.simulator import EventType, Event

class FCFSSimulator:
    """FCFS carpooling simulator"""
    
    def __init__(self, config: dict, driver_types: List[DriverType], 
                 osrm: OSRMClient, events: dict = None):
        self.config = config
        self.driver_types = driver_types
        self.osrm = osrm
        self.pre_generated_events = events
        
        # Current simulation time
        self.time = 0.0
        
        # Event queue
        self.event_queue = []
        
        # System state
        self.active_requests: List[Request] = []
        self.available_drivers: List[Driver] = []
        self.active_trips: List[Trip] = []
        self.completed_trips: List[Trip] = []
        
        # FCFS matcher
        self.fcfs_matcher = FCFSMatcher(
            osrm, 
            config['carpooling']['capacity'],
            config['carpooling']['detour_max']
        )
        
        # Metrics
        self.metrics = MetricsTracker(
            config['metrics']['update_interval'],
            enable_streaming=config['metrics'].get('enable_streaming', True)
        )
        
        # Configuration shortcuts
        self.capacity = config['carpooling']['capacity']
        self.max_detour = config['carpooling']['detour_max']
        self.quit_penalty = config['costs']['quit_penalty']
        self.waiting_cost_rate = config['costs']['waiting_cost_per_sec']
        self.bounds = config['region']['bounds']
        
        # Initialize
        self._initialize_drivers(config['simulation']['initial_drivers'])
        
        if events:
            self._schedule_from_events()
        else:
            self._schedule_arrivals()
    
    def _initialize_drivers(self, count: int):
        """Spawn initial drivers"""
        for _ in range(count):
            driver_type = np.random.choice(self.driver_types)
            location = self._random_location()
            
            driver = Driver(
                id=generate_driver_id(),
                type=driver_type,
                location=location,
                status=DriverStatus.AVAILABLE,
                available_since=0.0
            )
            self.available_drivers.append(driver)
    
    def _random_location(self) -> Location:
        """Generate random location"""
        lat = np.random.uniform(self.bounds['lat_min'], self.bounds['lat_max'])
        lon = np.random.uniform(self.bounds['lon_min'], self.bounds['lon_max'])
        return Location(lat, lon)
    
    def _schedule_from_events(self):
        """Schedule events from pre-generated list"""
        # Schedule request events
        for req_event in self.pre_generated_events['requests']:
            self._add_event(req_event['time'], EventType.REQUEST_ARRIVAL, req_event)
        
        # Schedule driver events
        for driver_type_id, driver_events in self.pre_generated_events['drivers'].items():
            for drv_event in driver_events:
                self._add_event(drv_event['time'], EventType.DRIVER_ARRIVAL, drv_event)
    
    def _schedule_arrivals(self):
        """Schedule Poisson arrivals"""
        # Request arrivals
        request_rate = self.config['requests']['arrival_rate']
        next_request_time = np.random.exponential(1.0 / request_rate)
        self._add_event(next_request_time, EventType.REQUEST_ARRIVAL, {})
        
        # Driver arrivals
        for driver_type in self.driver_types:
            next_driver_time = np.random.exponential(1.0 / driver_type.arrival_rate)
            self._add_event(next_driver_time, EventType.DRIVER_ARRIVAL, 
                          {'driver_type': driver_type})
    
    def _add_event(self, time: float, event_type: EventType, data: dict):
        """Add event to priority queue"""
        event = Event(time, event_type, data)
        heapq.heappush(self.event_queue, event)
    
    def run(self, duration: float):
        """Run FCFS simulation"""
        print(f"Starting FCFS simulation...")
        
        progress_interval = duration / 10
        next_progress = progress_interval
        
        while self.event_queue and self.time < duration:
            event = heapq.heappop(self.event_queue)
            self.time = event.time
            
            if self.time >= next_progress:
                progress_pct = (self.time / duration) * 100
                print(f"  FCFS Progress: {progress_pct:.0f}% (t={self.time:.0f}s)")
                next_progress += progress_interval
            
            self._handle_event(event)
            
            # Take metrics snapshot
            available_by_type = {dt.id: 0 for dt in self.driver_types}
            for driver in self.available_drivers:
                available_by_type[driver.type.id] += 1
            
            self.metrics.snapshot_state(
                self.time, self.active_requests, available_by_type, self.active_trips
            )
        
        print(f"FCFS simulation complete at t={self.time:.0f}s")
    
    def _handle_event(self, event: Event):
        """Dispatch event"""
        if event.event_type == EventType.REQUEST_ARRIVAL:
            self._on_request_arrival(event.data)
        elif event.event_type == EventType.DRIVER_ARRIVAL:
            self._on_driver_arrival(event.data)
        elif event.event_type == EventType.PICKUP_COMPLETE:
            self._on_pickup_complete(event.data['trip'], event.data['request'])
        elif event.event_type == EventType.TRIP_COMPLETE:
            self._on_trip_complete(event.data['trip'])
    
    def _on_request_arrival(self, data: dict):
        """Handle request arrival - FCFS matching"""
        # Create request
        if 'id' in data:
            # From pre-generated events
            request = Request(
                id=data['id'],
                origin=Location(*data['origin']),
                destination=Location(*data['destination']),
                arrival_time=self.time,
                weibull_shape=data['weibull_shape'],
                weibull_scale=data['weibull_scale'],
                waiting_cost_rate=self.waiting_cost_rate
            )
        else:
            # Generate new
            request = Request(
                id=generate_request_id(),
                origin=self._random_location(),
                destination=self._random_location(),
                arrival_time=self.time,
                weibull_shape=self.config['requests']['weibull_shape'],
                weibull_scale=self.config['requests']['weibull_scale'],
                waiting_cost_rate=self.waiting_cost_rate
            )
        
        self.active_requests.append(request)
        self.metrics.record_request_arrival(request, self.time)
        
        # FCFS matching
        trip = self.fcfs_matcher.match_request(
            request, self.available_drivers, self.active_trips
        )
        
        if trip and trip.id not in [t.id for t in self.active_trips]:
            # New trip created
            self._start_trip(trip)
        elif trip:
            # Added to existing trip
            self.active_requests.remove(request)
            self.metrics.record_dynamic_insertion(request, trip, self.time)
        
        # Schedule next request (if not using pre-generated)
        if not self.pre_generated_events:
            request_rate = self.config['requests']['arrival_rate']
            next_time = self.time + np.random.exponential(1.0 / request_rate)
            self._add_event(next_time, EventType.REQUEST_ARRIVAL, {})
    
    def _on_driver_arrival(self, data: dict):
        """Handle driver arrival"""
        if 'id' in data:
            # From pre-generated
            driver_type = next(dt for dt in self.driver_types if dt.id == data['type_id'])
            driver = Driver(
                id=data['id'],
                type=driver_type,
                location=Location(*data['location']),
                status=DriverStatus.AVAILABLE,
                available_since=self.time
            )
        else:
            # Generate new
            driver_type = data['driver_type']
            driver = Driver(
                id=generate_driver_id(),
                type=driver_type,
                location=self._random_location(),
                status=DriverStatus.AVAILABLE,
                available_since=self.time
            )
        
        self.available_drivers.append(driver)
        
        # Try to match with waiting requests
        if self.active_requests:
            request = self.active_requests[0]  # FCFS: take first waiting request
            trip = self.fcfs_matcher.match_request(
                request, [driver], self.active_trips
            )
            
            if trip and trip.id not in [t.id for t in self.active_trips]:
                self._start_trip(trip)
        
        # Schedule next driver (if not using pre-generated)
        if not self.pre_generated_events:
            next_time = self.time + np.random.exponential(1.0 / driver_type.arrival_rate)
            self._add_event(next_time, EventType.DRIVER_ARRIVAL, {'driver_type': driver_type})
    
    def _start_trip(self, trip: Trip):
        """Start a new trip"""
        trip.start_time = self.time
        
        # Update entities
        trip.driver.status = DriverStatus.EN_ROUTE_PICKUP
        trip.driver.current_trip = trip.id
        
        for request in trip.passengers:
            request.status = RequestStatus.MATCHED
            request.match_time = self.time
            request.assigned_driver = trip.driver.id
            
            if request in self.active_requests:
                self.active_requests.remove(request)
        
        if trip.driver in self.available_drivers:
            self.available_drivers.remove(trip.driver)
        
        self.active_trips.append(trip)
        
        # Schedule first pickup
        first_pickup = trip.route[0]
        travel_time = self.osrm.get_duration(
            trip.driver.location.to_tuple(),
            first_pickup.to_tuple()
        )
        pickup_time = self.time + travel_time
        self._add_event(pickup_time, EventType.PICKUP_COMPLETE,
                      {'trip': trip, 'request': trip.passengers[0]})
        
        self.metrics.record_match(trip, self.time)
    
    def _on_pickup_complete(self, trip: Trip, request: Request):
        """Handle pickup completion"""
        trip.complete_pickup(request.id)
        request.pickup_time = self.time
        request.status = RequestStatus.IN_TRANSIT
        
        if trip.all_pickups_complete():
            # All pickups done, head to destination
            travel_time = self.osrm.get_duration(
                trip.driver.location.to_tuple(),
                trip.destination.to_tuple()
            )
            completion_time = self.time + travel_time
            self._add_event(completion_time, EventType.TRIP_COMPLETE, {'trip': trip})
        else:
            # Go to next pickup
            next_pickup = trip.route[trip.current_position_index]
            travel_time = self.osrm.get_duration(
                trip.driver.location.to_tuple(),
                next_pickup.to_tuple()
            )
            next_request = trip.passengers[trip.current_position_index]
            pickup_time = self.time + travel_time
            self._add_event(pickup_time, EventType.PICKUP_COMPLETE,
                          {'trip': trip, 'request': next_request})
    
    def _on_trip_complete(self, trip: Trip):
        """Handle trip completion"""
        trip.completion_time = self.time
        
        # Update passenger status
        for passenger in trip.passengers:
            passenger.status = RequestStatus.COMPLETED
            passenger.completion_time = self.time
        
        # Return driver to circulation
        trip.driver.status = DriverStatus.AVAILABLE
        trip.driver.location = trip.destination
        trip.driver.available_since = self.time
        trip.driver.current_trip = None
        
        self.available_drivers.append(trip.driver)
        self.active_trips.remove(trip)
        self.completed_trips.append(trip)
        
        self.fcfs_matcher.trip_complete(trip)
        self.metrics.record_trip_complete(trip, self.time)
    
    def get_summary(self) -> dict:
        """Get simulation summary"""
        return self.metrics.get_summary()
    
    def save_metrics(self, filename: str):
        """Save metrics to file"""
        self.metrics.export_to_json(filename, self.time)