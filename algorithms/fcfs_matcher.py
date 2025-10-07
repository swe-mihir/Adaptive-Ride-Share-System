"""
First-Come-First-Served (FCFS) carpooling matcher.
UPDATED: Now includes pickup costs for fair comparison with optimal method.
"""

from typing import List, Optional, Dict
from core.entities import Request, Driver, Trip, Location, generate_trip_id
from utils.osrm_interface import OSRMClient

class FCFSMatcher:
    """FCFS matching algorithm - greedy, no optimization"""

    def __init__(self, osrm_client: OSRMClient, capacity: int = 3, max_detour: float = 1.5):
        self.osrm = osrm_client
        self.capacity = capacity
        self.max_detour = max_detour
        self.active_trips: Dict[str, Trip] = {}  # driver_id -> Trip

    def match_request(self, request: Request, available_drivers: List[Driver],
                     active_trips: List[Trip]) -> Optional[Trip]:
        """
        Match request using FCFS logic.

        1. Try to add to first available trip with capacity
        2. Otherwise assign to first available driver
        3. No optimization - purely first-come-first-served

        Returns:
            Trip if matched, None otherwise
        """
        # Sort drivers by availability time (first come first served)
        sorted_drivers = sorted(available_drivers, key=lambda d: d.available_since or 0)

        # First try to add to existing trips
        for trip in active_trips:
            if trip.capacity_available() > 0:
                # Simple check: can we add this request?
                if self._can_add_to_trip(trip, request):
                    self._add_to_trip_fcfs(trip, request)
                    return trip

        # No existing trip available, create new trip with first available driver
        if sorted_drivers:
            driver = sorted_drivers[0]
            new_trip = self._create_trip_fcfs(driver, request)
            return new_trip

        return None

    def _can_add_to_trip(self, trip: Trip, request: Request) -> bool:
        """
        Simple feasibility check - much simpler than optimal.
        Just check if destination is close enough.
        """
        # Check if destinations are close (within 5km - very loose)
        dest_distance = self.osrm.get_distance(
            trip.destination.to_tuple(),
            request.destination.to_tuple()
        )

        # Very permissive - accept if within 5km
        return dest_distance < 5000  # 5km

    def _add_to_trip_fcfs(self, trip: Trip, request: Request):
        """
        Add request to trip - NO TSP, just append to end.
        This is intentionally worse than optimal algorithm.
        """
        # Store old route for cost calculation
        old_route = trip.route.copy()
        old_passenger_count = len(trip.passengers)

        # Simply append pickup to route (no optimization)
        # Insert before destination
        trip.route.insert(-1, request.origin)
        trip.passengers.append(request)

        # ===== UPDATED COST CALCULATION =====
        # Recompute route cost (passenger route only)
        route_cost = self._compute_simple_route_cost(trip.route)

        # Pickup cost is ALREADY PAID by the trip (driver already traveling)
        # For existing trips, we don't add new pickup cost
        # The initial pickup cost was added when trip was created

        trip.total_route_cost = route_cost  # This is the shared route cost

        # Simple equal cost split (no detour-proportional)
        cost_per_passenger = route_cost / len(trip.passengers)
        for passenger in trip.passengers:
            trip.individual_costs[passenger.id] = cost_per_passenger
            passenger.cost_share = cost_per_passenger

        # Compute detours (for metrics)
        self._compute_simple_detours(trip)

        request.trip_id = trip.id

    def _create_trip_fcfs(self, driver: Driver, request: Request) -> Trip:
        """
        Create new trip - simple route, no optimization.
        UPDATED: Now includes pickup cost for fair comparison.
        """
        trip = Trip(
            id=generate_trip_id(),
            driver=driver,
            passengers=[request],
            route=[request.origin, request.destination],  # Simple: pickup -> dest
            destination=request.destination,
            capacity=self.capacity,
            start_time=0  # Will be set by simulator
        )

        # ===== UPDATED COST CALCULATION =====
        # 1. Compute pickup cost (driver -> first pickup)
        pickup_cost = self.osrm.get_duration(
            driver.location.to_tuple(),
            request.origin.to_tuple()
        )

        # 2. Compute route cost (pickup -> destination)
        route_cost = self._compute_simple_route_cost(trip.route)

        # 3. Total cost = pickup + route (same as optimal method)
        total_cost = pickup_cost + route_cost

        # Store both components
        trip.pickup_cost = pickup_cost
        trip.route_cost = route_cost
        trip.total_route_cost = total_cost

        # For single passenger, they pay the full route cost
        # (pickup cost is system overhead, not charged to passenger)
        trip.individual_costs[request.id] = route_cost
        request.cost_share = route_cost

        # Simple detour (1.0 for solo trip)
        trip.detour_ratios[request.id] = 1.0
        request.detour_ratio = 1.0
        request.trip_id = trip.id

        self.active_trips[driver.id] = trip

        return trip

    def _compute_simple_route_cost(self, route: List[Location]) -> float:
        """
        Compute route cost without optimization.
        Just sum segment-by-segment.
        """
        if len(route) < 2:
            return 0.0

        total_cost = 0.0
        for i in range(len(route) - 1):
            segment_cost = self.osrm.get_duration(
                route[i].to_tuple(),
                route[i + 1].to_tuple()
            )
            total_cost += segment_cost

        return total_cost

    def _compute_simple_detours(self, trip: Trip):
        """
        Compute detour ratios - simple calculation.
        """
        for passenger in trip.passengers:
            # Solo trip time
            solo_time = self.osrm.get_duration(
                passenger.origin.to_tuple(),
                passenger.destination.to_tuple()
            )
            passenger.solo_trip_duration = solo_time

            # Actual trip time (from pickup to destination in route)
            pickup_idx = None
            for i, loc in enumerate(trip.route):
                if (abs(loc.lat - passenger.origin.lat) < 0.0001 and
                    abs(loc.lon - passenger.origin.lon) < 0.0001):
                    pickup_idx = i
                    break

            if pickup_idx is not None:
                # Time from pickup to end
                sub_route = trip.route[pickup_idx:]
                actual_time = self._compute_simple_route_cost(sub_route)
                passenger.actual_trip_duration = actual_time

                detour_ratio = actual_time / solo_time if solo_time > 0 else 1.0
                trip.detour_ratios[passenger.id] = detour_ratio
                passenger.detour_ratio = detour_ratio
            else:
                trip.detour_ratios[passenger.id] = 1.0
                passenger.detour_ratio = 1.0

    def trip_complete(self, trip: Trip):
        """Mark trip as complete and remove from active trips"""
        if trip.driver.id in self.active_trips:
            del self.active_trips[trip.driver.id]