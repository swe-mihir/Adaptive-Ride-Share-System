"""
Routing engine for carpooling with TSP solver for pickup sequencing.
"""

from typing import List, Tuple, Dict, Optional
from itertools import permutations
from core.entities import Location, Request, Driver
from utils.osrm_interface import OSRMClient

class RoutingEngine:
    """Handles route optimization for carpooling"""

    def __init__(self, osrm_client: OSRMClient, capacity: int = 3):
        self.osrm = osrm_client
        self.capacity = capacity
        self.tsp_cache = {}  # Cache TSP solutions

    def solve_tsp_pickups(self, driver_location: Location,
                         pickup_locations: List[Location],
                         destination: Location) -> Tuple[List[Location], float]:
        """
        Solve TSP for optimal pickup sequence.

        Args:
            driver_location: Current driver position
            pickup_locations: List of passenger pickup locations
            destination: Final destination (same for all passengers)

        Returns:
            (optimal_route, total_cost) where route = [P1, P2, ..., Pk, Destination]
        """
        # Cache key
        pickups_tuple = tuple(sorted((p.lat, p.lon) for p in pickup_locations))
        cache_key = (driver_location.to_tuple(), pickups_tuple, destination.to_tuple())

        if cache_key in self.tsp_cache:
            return self.tsp_cache[cache_key]

        # For K≤3, brute force all permutations
        if len(pickup_locations) <= 3:
            best_route, best_cost = self._brute_force_tsp(
                driver_location, pickup_locations, destination
            )
        else:
            # Fallback to nearest neighbor for larger instances
            best_route, best_cost = self._nearest_neighbor_tsp(
                driver_location, pickup_locations, destination
            )

        # Cache result
        self.tsp_cache[cache_key] = (best_route, best_cost)
        return best_route, best_cost

    def _brute_force_tsp(self, start: Location, pickups: List[Location],
                        destination: Location) -> Tuple[List[Location], float]:
        """Brute force TSP for small number of pickups"""
        best_route = None
        min_cost = float('inf')

        # Try all permutations
        for perm in permutations(pickups):
            route = [start] + list(perm) + [destination]
            cost = self._compute_route_cost(route)

            if cost < min_cost:
                min_cost = cost
                best_route = list(perm) + [destination]

        return best_route, min_cost

    def _nearest_neighbor_tsp(self, start: Location, pickups: List[Location],
                             destination: Location) -> Tuple[List[Location], float]:
        """Nearest neighbor heuristic for TSP"""
        unvisited = set(pickups)
        route = []
        current = start

        while unvisited:
            # Find nearest unvisited pickup
            nearest = min(unvisited,
                         key=lambda p: self.osrm.get_duration(current.to_tuple(), p.to_tuple()))
            route.append(nearest)
            unvisited.remove(nearest)
            current = nearest

        route.append(destination)
        cost = self._compute_route_cost([start] + route)

        return route, cost

    def _compute_route_cost(self, route: List[Location]) -> float:
        """Compute total cost (duration) of a route"""
        coordinates = [loc.to_tuple() for loc in route]
        result = self.osrm.get_route(coordinates)
        return result['duration']

    def compute_detour_ratios(self, route: List[Location],
                             passengers: List[Request]) -> Dict[str, float]:
        """
        Compute detour ratio for each passenger in a shared trip.

        Detour ratio = (actual_trip_time) / (solo_trip_time)

        Args:
            route: Full route [P1, P2, ..., Pk, Destination]
            passengers: List of passengers in order of pickup

        Returns:
            Dict mapping passenger_id -> detour_ratio
        """
        detours = {}
        destination = route[-1]

        # Get solo trip times for each passenger
        solo_times = {}
        for passenger in passengers:
            solo_time = self.osrm.get_duration(
                passenger.origin.to_tuple(),
                passenger.destination.to_tuple()
            )
            solo_times[passenger.id] = solo_time
            passenger.solo_trip_duration = solo_time

        # Compute actual trip time for each passenger
        # Passenger's trip = time from their pickup to destination
        for i, passenger in enumerate(passengers):
            # Find passenger's pickup position in route
            pickup_idx = None
            for j, loc in enumerate(route[:-1]):  # Exclude destination
                if (abs(loc.lat - passenger.origin.lat) < 0.0001 and
                    abs(loc.lon - passenger.origin.lon) < 0.0001):
                    pickup_idx = j
                    break

            if pickup_idx is None:
                # Fallback: assume pickup is at position i
                pickup_idx = i

            # Compute time from pickup to destination
            sub_route = route[pickup_idx:]
            actual_time = self._compute_route_cost(sub_route)

            passenger.actual_trip_duration = actual_time
            detour_ratio = actual_time / solo_times[passenger.id]
            detours[passenger.id] = detour_ratio
            passenger.detour_ratio = detour_ratio

        return detours

    def split_costs_by_detour(self, total_route_cost: float,
                              detour_ratios: Dict[str, float]) -> Dict[str, float]:
        """
        Split routing cost among passengers proportional to their detour ratio.

        Higher detour = higher cost share.
        """
        total_detour_weight = sum(detour_ratios.values())

        if total_detour_weight == 0:
            # Equal split if no detours
            n = len(detour_ratios)
            return {pid: total_route_cost / n for pid in detour_ratios}

        costs = {}
        for passenger_id, detour_ratio in detour_ratios.items():
            weight = detour_ratio / total_detour_weight
            costs[passenger_id] = total_route_cost * weight

        return costs

    def try_insert_request(self, route: List[Location],
                          passengers: List[Request],
                          new_request: Request,
                          driver_location: Location,
                          max_detour: float = 1.5) -> Optional[Tuple[List[Location], Dict, Dict]]:
        """
        Try to insert a new request into an existing route.

        Returns:
            (new_route, new_costs, new_detours) if successful, None otherwise
        """
        if len(passengers) >= self.capacity:
            return None

        destination = route[-1]
        current_pickups = [p.origin for p in passengers]

        # Try inserting new pickup at each position
        best_insertion = None
        min_cost_increase = float('inf')

        for insert_pos in range(len(current_pickups) + 1):
            # Create test route
            test_pickups = current_pickups[:insert_pos] + [new_request.origin] + current_pickups[insert_pos:]
            test_passengers = passengers[:insert_pos] + [new_request] + passengers[insert_pos:]

            # Solve TSP for new route
            test_route, test_cost = self.solve_tsp_pickups(
                driver_location, test_pickups, destination
            )
            
            # Compute detours
            test_detours = self.compute_detour_ratios(test_route, test_passengers)
            
            # Check detour constraint
            if any(d > max_detour for d in test_detours.values()):
                continue  # Violates detour constraint
            
            # Compute costs
            test_costs = self.split_costs_by_detour(test_cost, test_detours)
            
            # Compare cost increase
            original_cost = sum([p.cost_share or 0 for p in passengers])
            cost_increase = sum(test_costs.values()) - original_cost

            if cost_increase < min_cost_increase:
                min_cost_increase = cost_increase
                best_insertion = (test_route, test_costs, test_detours)

        return best_insertion

    def validate_route(self, route: List[Location], passengers: List[Request],
                      max_detour: float = 1.5) -> bool:
        """
        Validate that a route satisfies detour constraints.

        Returns:
            True if all passengers have detour ≤ max_detour
        """
        detours = self.compute_detour_ratios(route, passengers)
        return all(d <= max_detour for d in detours.values())

    def get_pickup_cost(self, driver_location: Location,
                       pickup_location: Location) -> float:
        """Get cost for driver to reach pickup location"""
        return self.osrm.get_duration(
            driver_location.to_tuple(),
            pickup_location.to_tuple()
        )

    def clear_cache(self):
        """Clear TSP cache"""
        self.tsp_cache.clear()