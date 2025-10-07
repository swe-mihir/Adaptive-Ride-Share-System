"""
Event-driven simulator for carpooling OMD system.
FIXED: Request generation now works correctly for both live and pre-generated modes.
"""

import heapq
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

from core.entities import (
    Request, Driver, Trip, Location, DriverType, RequestStatus, DriverStatus,
    generate_request_id, generate_driver_id, generate_trip_id
)
from utils.osrm_interface import OSRMClient
from algorithms.routing import RoutingEngine
from algorithms.clustering import DestinationClusterer
from algorithms.assignment_p1_carpool import AssignmentSolver
from algorithms.threshold_policy import ThresholdPolicy
from utils.metrics_carpool import MetricsTracker

class EventType(Enum):
    REQUEST_ARRIVAL = "request_arrival"
    DRIVER_ARRIVAL = "driver_arrival"
    REQUEST_QUIT = "request_quit"
    THRESHOLD_REACHED = "threshold_reached"
    PICKUP_COMPLETE = "pickup_complete"
    TRIP_COMPLETE = "trip_complete"

@dataclass
class Event:
    """Simulation event"""
    time: float
    event_type: EventType
    data: dict

    def __lt__(self, other):
        return self.time < other.time

class CarpoolSimulator:
    """Main carpooling OMD simulator"""

    def __init__(self, config: dict, driver_types: List[DriverType], osrm: OSRMClient, events: dict = None):
        self.config = config
        self.driver_types = driver_types
        self.osrm = osrm

        # FIXED: Properly determine if using live generation
        self.use_live_generation = (events is None or not events or 'requests' not in events)
        self.pre_generated_events = events if not self.use_live_generation else None

        # Current simulation time
        self.time = 0.0

        # Event queue (priority queue)
        self.event_queue = []

        # System state
        self.active_requests: List[Request] = []
        self.available_drivers: List[Driver] = []
        self.active_trips: List[Trip] = []
        self.completed_trips: List[Trip] = []

        # Components
        self.routing = RoutingEngine(osrm, config['carpooling']['capacity'])
        self.clusterer = DestinationClusterer(
            config['carpooling']['destination_cluster_radius_km']
        )
        self.assignment_solver = AssignmentSolver(
            self.routing, config['carpooling']['capacity']
        )
        self.threshold_policy = ThresholdPolicy(
            driver_types, config['costs']['quit_penalty']
        )
        self.metrics = MetricsTracker(
            config['metrics']['update_interval'],
            enable_streaming=config['metrics'].get('enable_streaming', True)
        )

        # Configuration shortcuts
        self.capacity = config['carpooling']['capacity']
        self.max_detour = config['carpooling']['detour_max']
        self.dynamic_insertion_enabled = config['carpooling']['dynamic_insertion_enabled']
        self.quit_penalty = config['costs']['quit_penalty']
        self.waiting_cost_rate = config['costs']['waiting_cost_per_sec']

        # Driver cap
        self.max_drivers = config['simulation'].get('max_drivers', 100)
        self.total_drivers_spawned = config['simulation']['initial_drivers']

        # Region bounds
        self.bounds = config['region']['bounds']

        # Initialize
        self._initialize_drivers(config['simulation']['initial_drivers'])

        # Schedule events
        if self.use_live_generation:
            print(f"  ✓ Using LIVE event generation (Poisson arrivals)")
            self._schedule_arrivals()
        else:
            print(f"  ✓ Using PRE-GENERATED events")
            self._schedule_from_events()

    def _initialize_drivers(self, count: int):
        """Spawn initial drivers randomly in the region"""
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
        """Generate random location within region bounds"""
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
        """Schedule Poisson arrivals for requests and drivers"""
        # Request arrivals
        request_rate = self.config['requests']['arrival_rate']
        next_request_time = np.random.exponential(1.0 / request_rate)
        self._add_event(next_request_time, EventType.REQUEST_ARRIVAL, {})
        print(f"  ✓ First request scheduled at t={next_request_time:.2f}s (rate={request_rate})")

        # Driver arrivals (by type)
        for driver_type in self.driver_types:
            next_driver_time = np.random.exponential(1.0 / driver_type.arrival_rate)
            self._add_event(next_driver_time, EventType.DRIVER_ARRIVAL,
                          {'driver_type': driver_type})

    def _add_event(self, time: float, event_type: EventType, data: dict):
        """Add event to priority queue"""
        event = Event(time, event_type, data)
        heapq.heappush(self.event_queue, event)

    def run(self, duration: float):
        """Run simulation for specified duration"""
        print(f"Starting simulation...")
        print(f"  Event generation mode: {'LIVE' if self.use_live_generation else 'PRE-GENERATED'}")
        print(f"  Initial event queue size: {len(self.event_queue)}")

        progress_interval = duration / 10
        next_progress = progress_interval

        # DIAGNOSTIC: Track request generation
        total_requests_generated = 0

        while self.event_queue and self.time < duration:
            # Get next event
            event = heapq.heappop(self.event_queue)
            self.time = event.time

            # Progress indicator
            if self.time >= next_progress:
                progress_pct = (self.time / duration) * 100
                print(f"  Progress: {progress_pct:.0f}% (t={self.time:.0f}s) | "
                      f"Requests: {total_requests_generated} | "
                      f"Active: {len(self.active_requests)} | "
                      f"Drivers: {len(self.available_drivers)}")
                next_progress += progress_interval

            # Track request arrivals
            if event.event_type == EventType.REQUEST_ARRIVAL:
                total_requests_generated += 1

            # Handle event
            self._handle_event(event)

            # Take metrics snapshot
            available_by_type = {dt.id: 0 for dt in self.driver_types}
            for driver in self.available_drivers:
                available_by_type[driver.type.id] += 1

            self.metrics.snapshot_state(
                self.time, self.active_requests, available_by_type, self.active_trips
            )

        print(f"Simulation complete at t={self.time:.0f}s")
        print(f"Total requests generated: {total_requests_generated}")
        print(f"Total drivers spawned: {self.total_drivers_spawned}")

    def _handle_event(self, event: Event):
        """Dispatch event to appropriate handler"""
        if event.event_type == EventType.REQUEST_ARRIVAL:
            self._on_request_arrival(event.data)
        elif event.event_type == EventType.DRIVER_ARRIVAL:
            self._on_driver_arrival(event.data)
        elif event.event_type == EventType.REQUEST_QUIT:
            self._on_request_quit(event.data['request'])
        elif event.event_type == EventType.THRESHOLD_REACHED:
            self._on_threshold_reached(event.data['request'])
        elif event.event_type == EventType.PICKUP_COMPLETE:
            self._on_pickup_complete(event.data['trip'], event.data['request'])
        elif event.event_type == EventType.TRIP_COMPLETE:
            self._on_trip_complete(event.data['trip'])

    def _on_request_arrival(self, data: dict):
        """Handle new request arrival"""
        # Create request
        if data and 'id' in data:
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

        # Try dynamic insertion first
        if self.dynamic_insertion_enabled:
            inserted = self._try_dynamic_insertion(request)
            if inserted:
                # FIXED: Still schedule next request even if inserted
                if self.use_live_generation:
                    self._schedule_next_request()
                return

        # Schedule quit event based on request's patience
        patience = request.generate_patience()
        quit_time = self.time + patience
        self._add_event(quit_time, EventType.REQUEST_QUIT, {'request': request})

        # Compute threshold
        threshold_time = self.time + self.threshold_policy.compute_threshold(
            request, len(self.active_requests), self.capacity
        )
        self._add_event(threshold_time, EventType.THRESHOLD_REACHED, {'request': request})

        # Run matching algorithm
        self._run_matching()

        # FIXED: Schedule next request for live generation
        if self.use_live_generation:
            self._schedule_next_request()

    def _schedule_next_request(self):
        """Schedule next request arrival (for live generation only)"""
        request_rate = self.config['requests']['arrival_rate']
        inter_arrival_time = np.random.exponential(1.0 / request_rate)
        next_time = self.time + inter_arrival_time
        self._add_event(next_time, EventType.REQUEST_ARRIVAL, {})

    def _try_dynamic_insertion(self, request: Request) -> bool:
        """Try to insert request into active trips"""
        best_trip = None
        best_insertion = None
        min_cost_increase = float('inf')

        for trip in self.active_trips:
            if trip.capacity_available() == 0:
                continue

            # Check if destinations are compatible
            if not self.clusterer.are_destinations_compatible(
                request, trip.passengers[0]
            ):
                continue

            # Try insertion
            result = self.routing.try_insert_request(
                trip.route, trip.passengers, request,
                trip.driver.location, self.max_detour
            )

            if result:
                new_route, new_costs, new_detours = result
                current_cost = sum(trip.individual_costs.values())
                new_total_cost = sum(new_costs.values())
                cost_increase = new_total_cost - current_cost

                if cost_increase < min_cost_increase:
                    min_cost_increase = cost_increase
                    best_trip = trip
                    best_insertion = (new_route, new_costs, new_detours)

        if best_trip and best_insertion:
            # Perform insertion
            new_route, new_costs, new_detours = best_insertion
            best_trip.add_passenger(request, new_route, new_costs, new_detours)

            # Update passenger cost shares
            for passenger in best_trip.passengers:
                passenger.cost_share = new_costs[passenger.id]

            self.active_requests.remove(request)
            self.metrics.record_dynamic_insertion(request, best_trip, self.time)
            return True

        return False

    def _on_driver_arrival(self, data: dict):
        """Handle new driver arrival - with driver cap"""
        # Check driver cap
        total_drivers = len(self.available_drivers) + len(self.active_trips)
        if total_drivers >= self.max_drivers:
            # Don't spawn new driver, but still schedule next arrival check
            if self.use_live_generation:
                driver_type = data.get('driver_type')
                if driver_type:
                    next_time = self.time + np.random.exponential(1.0 / driver_type.arrival_rate)
                    self._add_event(next_time, EventType.DRIVER_ARRIVAL, {'driver_type': driver_type})
            return

        if data and 'id' in data:
            # From pre-generated events
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
            location = self._random_location()
            driver = Driver(
                id=generate_driver_id(),
                type=driver_type,
                location=location,
                status=DriverStatus.AVAILABLE,
                available_since=self.time
            )

        self.available_drivers.append(driver)
        self.total_drivers_spawned += 1

        # Run matching
        self._run_matching()

        # FIXED: Schedule next driver arrival for live generation
        if self.use_live_generation:
            next_time = self.time + np.random.exponential(1.0 / driver_type.arrival_rate)
            self._add_event(next_time, EventType.DRIVER_ARRIVAL, {'driver_type': driver_type})

    def _on_request_quit(self, request: Request):
        """Handle request quitting (passenger runs out of patience)"""
        if request in self.active_requests:
            self.active_requests.remove(request)
            request.status = RequestStatus.QUIT
            request.quit_time = self.time

            # Record quit with penalty
            self.metrics.record_quit(request, self.time, self.quit_penalty)

            print(f"  ⏱️  Request {request.id} quit after {self.time - request.arrival_time:.1f}s")

    def _on_threshold_reached(self, request: Request):
        """Handle threshold reached for a request"""
        if request not in self.active_requests:
            return  # Already matched or quit

        # Force matching with best available driver
        if self.available_drivers:
            self._run_matching()

    def _on_pickup_complete(self, trip: Trip, request: Request):
        """Handle driver completing a pickup"""
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

        # Return driver to circulation at destination
        trip.driver.status = DriverStatus.AVAILABLE
        trip.driver.location = trip.destination
        trip.driver.available_since = self.time
        trip.driver.current_trip = None

        self.available_drivers.append(trip.driver)
        self.active_trips.remove(trip)
        self.completed_trips.append(trip)

        self.metrics.record_trip_complete(trip, self.time)

    def _run_matching(self):
        """Run matching algorithm (P1-Carpool)"""
        if not self.active_requests or not self.available_drivers:
            return

        # Cluster requests by destination
        clusters = self.clusterer.cluster_requests(self.active_requests)

        # Solve assignment problem
        try:
            assignments = self.assignment_solver.solve(
                self.available_drivers, clusters, self.max_detour
            )
        except Exception as e:
            print(f"  ✗ ERROR in assignment solver: {e}")
            return

        # Create trips from assignments
        for driver, requests, route, costs, detours in assignments:
            self._create_trip(driver, requests, route, costs, detours)

    def _create_trip(self, driver: Driver, requests: List[Request],
                    route: List[Location], costs: Dict, detours: Dict):
        """Create a new trip from assignment"""
        trip = Trip(
            id=generate_trip_id(),
            driver=driver,
            passengers=requests,
            route=route,
            destination=route[-1],
            capacity=self.capacity,
            start_time=self.time
        )

        trip.individual_costs = costs
        trip.detour_ratios = detours
        trip.total_route_cost = sum(costs.values())

        # Update entities
        driver.status = DriverStatus.EN_ROUTE_PICKUP
        driver.current_trip = trip.id

        for request in requests:
            request.status = RequestStatus.MATCHED
            request.match_time = self.time
            request.assigned_driver = driver.id
            request.trip_id = trip.id
            request.cost_share = costs[request.id]

            if request in self.active_requests:
                self.active_requests.remove(request)

        if driver in self.available_drivers:
            self.available_drivers.remove(driver)

        self.active_trips.append(trip)

        # Schedule first pickup
        first_pickup = route[0]
        travel_time = self.osrm.get_duration(
            driver.location.to_tuple(),
            first_pickup.to_tuple()
        )
        pickup_time = self.time + travel_time
        self._add_event(pickup_time, EventType.PICKUP_COMPLETE,
                      {'trip': trip, 'request': requests[0]})

        self.metrics.record_match(trip, self.time)

    def get_summary(self) -> dict:
        """Get simulation summary"""
        return self.metrics.get_summary()

    def save_metrics(self, filename: str):
        """Save metrics to file"""
        self.metrics.export_to_json(filename, self.time)

    def print_active_pools(self):
        """Print all drivers currently in active carpools with their passengers"""
        print("\n" + "=" * 80)
        print(f"ACTIVE CARPOOLS AT TIME t={self.time:.1f}s")
        print("=" * 80)

        if not self.active_trips:
            print("  (No active trips)")
            return

        for trip in self.active_trips:
            print(f"\n  Trip ID: {trip.id}")
            print(f"  ├─ Driver: {trip.driver.id} ({trip.driver.type.name})")
            print(f"  ├─ Driver Location: ({trip.driver.location.lat:.4f}, {trip.driver.location.lon:.4f})")
            print(f"  ├─ Status: {trip.driver.status.value}")
            print(f"  ├─ Pool Size: {len(trip.passengers)}/{self.capacity}")
            print(f"  ├─ Destination: ({trip.destination.lat:.4f}, {trip.destination.lon:.4f})")
            print(f"  ├─ Total Cost: ₹{trip.total_route_cost:.2f}")
            print(f"  └─ Passengers:")

            for i, passenger in enumerate(trip.passengers, 1):
                waiting_time = self.time - passenger.arrival_time
                print(f"      {i}. Request {passenger.id}")
                print(f"         • Origin: ({passenger.origin.lat:.4f}, {passenger.origin.lon:.4f})")
                print(f"         • Destination: ({passenger.destination.lat:.4f}, {passenger.destination.lon:.4f})")
                print(f"         • Status: {passenger.status.value}")
                print(f"         • Waiting: {waiting_time:.1f}s")
                print(f"         • Cost Share: ₹{passenger.cost_share:.2f}")
                if passenger.id in trip.detour_ratios:
                    print(f"         • Detour Ratio: {trip.detour_ratios[passenger.id]:.2f}x")

        print("\n" + "=" * 80)