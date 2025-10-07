"""
P1-Carpool: Assignment problem solver with capacity constraints.
Assigns available drivers to request groups optimally.
MODIFIED: Prioritizes max capacity pools and penalizes empty seats.
"""

from typing import List, Dict, Tuple, Optional
from itertools import combinations
import pulp
from core.entities import Driver, Request, Location
from algorithms.routing import RoutingEngine

class AssignmentSolver:
    """Solves P1-Carpool assignment problem"""

    def __init__(self, routing_engine: RoutingEngine, capacity: int = 3):
        self.routing = routing_engine
        self.capacity = capacity
        self.group_cache = {}  # Cache feasible groups and their costs

    def solve(self, drivers: List[Driver],
              request_clusters: Dict[int, List[Request]],
              max_detour: float = 1.5) -> List[Tuple[Driver, List[Request], List[Location], Dict, Dict]]:
        """Solve assignment problem"""

        print(f"    [SOLVER] Starting with {len(drivers)} drivers, {len(request_clusters)} clusters")

        if not drivers or not request_clusters:
            return []

        # Flatten clusters into all requests
        all_requests = []
        for cluster in request_clusters.values():
            all_requests.extend(cluster)

        print(f"    [SOLVER] Total requests: {len(all_requests)}")

        # Generate feasible groups (MODIFIED: prioritize larger groups)
        feasible_groups = self._generate_feasible_groups(
            drivers, request_clusters, max_detour
        )

        print(f"    [SOLVER] Feasible groups found: {len(feasible_groups)}")

        if not feasible_groups:
            print(f"    [SOLVER] ✗ NO FEASIBLE GROUPS! This is the problem!")
            return []

        # Solve integer program
        assignments = self._solve_ip(drivers, all_requests, feasible_groups)

        return assignments

    def _generate_feasible_groups(self, drivers: List[Driver],
                                  clusters: Dict[int, List[Request]],
                                  max_detour: float) -> List[Dict]:
        """
        Generate all feasible driver-request group combinations.
        MODIFIED: Prioritize larger groups by generating from capacity down to 1.

        Returns:
            List of feasible group dicts with keys:
                - driver: Driver object
                - requests: List of requests
                - route: Optimal pickup route
                - cost: Total route cost
                - detours: Detour ratios
                - individual_costs: Cost per passenger
        """
        feasible = []

        for driver in drivers:
            for cluster_id, cluster_requests in clusters.items():
                # MODIFIED: Try from max capacity DOWN to 1 (prioritize full vehicles)
                for k in range(min(len(cluster_requests), self.capacity), 0, -1):
                    for request_combo in combinations(cluster_requests, k):
                        group_key = (driver.id, tuple(r.id for r in request_combo))

                        # Check cache
                        if group_key in self.group_cache:
                            feasible.append(self.group_cache[group_key])
                            continue

                        # Compute route and costs
                        result = self._evaluate_group(
                            driver, list(request_combo), max_detour
                        )

                        if result:
                            self.group_cache[group_key] = result
                            feasible.append(result)

        return feasible

    def _evaluate_group(self, driver: Driver, requests: List[Request],
                       max_detour: float) -> Optional[Dict]:
        """
        Evaluate if a driver-request group is feasible.

        Returns:
            Group dict if feasible, None otherwise
        """
        # All requests must have same destination cluster
        # (Already guaranteed by clustering, but double-check)
        destinations = [r.destination for r in requests]
        if not self._are_close(destinations, radius_km=1.0):
            return None

        # Use first request's destination as common destination
        common_dest = destinations[0]

        # Get pickup locations
        pickups = [r.origin for r in requests]

        # Solve TSP for pickup order
        try:
            route, route_cost = self.routing.solve_tsp_pickups(
                driver.location, pickups, common_dest
            )
        except Exception as e:
            print(f"⚠ TSP failed for driver {driver.id}: {e}")
            return None

        # Compute detours
        detours = self.routing.compute_detour_ratios(route, requests)

        # Check detour constraint
        if any(d > max_detour for d in detours.values()):
            return None

        # Split costs by detour
        individual_costs = self.routing.split_costs_by_detour(route_cost, detours)

        # Add pickup cost (driver to first pickup)
        pickup_cost = self.routing.get_pickup_cost(driver.location, route[0])
        total_cost = pickup_cost + route_cost

        return {
            'driver': driver,
            'requests': requests,
            'route': route,
            'route_cost': route_cost,
            'pickup_cost': pickup_cost,
            'total_cost': total_cost,
            'detours': detours,
            'individual_costs': individual_costs
        }

    def _are_close(self, locations: List[Location], radius_km: float) -> bool:
        """Check if all locations are within radius of each other"""
        if len(locations) <= 1:
            return True

        from math import radians, cos, sin, sqrt, atan2

        R = 6371  # Earth radius in km

        for i in range(len(locations)):
            for j in range(i + 1, len(locations)):
                loc1, loc2 = locations[i], locations[j]

                dlat = radians(loc2.lat - loc1.lat)
                dlon = radians(loc2.lon - loc1.lon)

                a = (sin(dlat/2)**2 +
                     cos(radians(loc1.lat)) * cos(radians(loc2.lat)) * sin(dlon/2)**2)
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                distance = R * c

                if distance > radius_km:
                    return False

        return True

    def _solve_ip(self, drivers: List[Driver], requests: List[Request],
                  feasible_groups: List[Dict]) -> List[Tuple]:
        """Solve integer program to find optimal assignment.
        MODIFIED: Added penalty for non-full vehicles to maximize pool sizes."""

        print(f"    [IP SOLVER] Starting with {len(feasible_groups)} groups")

        # ============= DIAGNOSTIC BLOCK =============
        print(f"\n    [DIAGNOSTIC] Analyzing feasible groups...")

        # Show sample groups
        for idx, group in enumerate(feasible_groups[:5]):  # First 5 groups
            print(f"      Group {idx}:")
            print(f"        Driver: {group['driver'].id}")
            print(f"        Requests: {[r.id for r in group['requests']]}")
            print(f"        Pool size: {len(group['requests'])}/{self.capacity}")
            print(f"        Total cost: {group['total_cost']:.2f}")
            print(f"        Detours: {group['detours']}")

        # Check which requests have coverage
        request_coverage = {r.id: 0 for r in requests}
        for group in feasible_groups:
            for req in group['requests']:
                request_coverage[req.id] += 1

        print(f"\n    [DIAGNOSTIC] Request coverage:")
        for req_id, count in request_coverage.items():
            print(f"      Request {req_id}: {count} feasible groups")

        uncovered = [req_id for req_id, count in request_coverage.items() if count == 0]
        if uncovered:
            print(f"    [DIAGNOSTIC] ⚠ WARNING: {len(uncovered)} requests have ZERO feasible groups!")
            print(f"      Uncovered: {uncovered}")

        # Check driver utilization
        driver_coverage = {d.id: 0 for d in drivers}
        for group in feasible_groups:
            driver_coverage[group['driver'].id] += 1

        drivers_used = sum(1 for count in driver_coverage.values() if count > 0)
        print(f"    [DIAGNOSTIC] Drivers with feasible groups: {drivers_used}/{len(drivers)}")
        # =============================================

        # Create optimization problem
        prob = pulp.LpProblem("P1_Carpool_Assignment", pulp.LpMinimize)

        # Decision variables: x_g = 1 if group g is selected
        group_vars = {}
        for idx, group in enumerate(feasible_groups):
            var_name = f"group_{idx}"
            group_vars[idx] = pulp.LpVariable(var_name, cat='Binary')

        # Penalty for unserved requests (must be larger than any single ride cost)
        # Set to 10x the maximum observed cost to ensure coverage is prioritized
        max_group_cost = max((g['total_cost'] for g in feasible_groups), default=0)
        UNSERVED_PENALTY = max(10 * max_group_cost, 1000000.0)  # At least 1M

        # MODIFIED: Penalty for non-full vehicles (encourages max capacity pooling)
        # Each empty seat costs 5x the max group cost
        CAPACITY_PENALTY = max_group_cost * 3.0

        print(f"    [IP SOLVER] Max group cost: {max_group_cost:.2f}")
        print(f"    [IP SOLVER] Unserved penalty: {UNSERVED_PENALTY:.2f}")
        print(f"    [IP SOLVER] Empty seat penalty: {CAPACITY_PENALTY:.2f}")

        # Auxiliary variables: y_r = 1 if request r is served
        request_served_vars = {}
        for req in requests:
            request_served_vars[req.id] = pulp.LpVariable(
                f"served_{req.id}", cat='Binary'
            )

        # MODIFIED OBJECTIVE: minimize cost + penalty for unserved + penalty for empty seats
        prob += (
            pulp.lpSum([
                group_vars[idx] * (
                    group['total_cost'] +
                    CAPACITY_PENALTY * (self.capacity - len(group['requests']))
                )
                for idx, group in enumerate(feasible_groups)
            ]) +
            pulp.lpSum([
                (1 - request_served_vars[req.id]) * UNSERVED_PENALTY
                for req in requests
            ])
        )

        # Constraint 1: Each request assigned at most once
        request_constraints = {r.id: [] for r in requests}
        for idx, group in enumerate(feasible_groups):
            for req in group['requests']:
                request_constraints[req.id].append(group_vars[idx])

        for req in requests:
            vars_list = request_constraints[req.id]
            if vars_list:
                # Request served if any group containing it is selected
                prob += (
                    request_served_vars[req.id] <= pulp.lpSum(vars_list),
                    f"request_{req.id}_served_link"
                )
                prob += (
                    pulp.lpSum(vars_list) <= 1,
                    f"request_{req.id}_once"
                )
            else:
                # No feasible groups for this request - cannot be served
                prob += request_served_vars[req.id] == 0, f"request_{req.id}_infeasible"

        # Constraint 2: Each driver assigned at most once
        driver_constraints = {d.id: [] for d in drivers}
        for idx, group in enumerate(feasible_groups):
            driver_constraints[group['driver'].id].append(group_vars[idx])

        for driver_id, vars_list in driver_constraints.items():
            if vars_list:
                prob += pulp.lpSum(vars_list) <= 1, f"driver_{driver_id}_once"

        # Solve
        print(f"\n    [IP SOLVER] Solving with PuLP...")
        status = prob.solve(pulp.PULP_CBC_CMD(msg=0))

        print(f"    [IP SOLVER] Status: {pulp.LpStatus[status]}")
        print(f"    [IP SOLVER] Objective value: {pulp.value(prob.objective):.2f}")

        # ============= MORE DIAGNOSTICS =============
        # Check which variables are non-zero
        print(f"\n    [IP SOLVER] Variable values:")
        group_values = []
        for idx, var in group_vars.items():
            val = pulp.value(var)
            if val is not None and val > 0.01:
                group_values.append((idx, val))
                group = feasible_groups[idx]
                print(f"      group_{idx} = {val} (pool size: {len(group['requests'])}/{self.capacity})")

        if not group_values:
            print(f"      (All group variables are 0)")

        # Check request served variables
        print(f"\n    [IP SOLVER] Request served status:")
        for req in requests:
            val = pulp.value(request_served_vars[req.id])
            print(f"      {req.id}: {'SERVED' if val == 1 else 'NOT SERVED'}")
        # =============================================

        # Count served requests
        served_count = sum(
            1 for req in requests
            if pulp.value(request_served_vars[req.id]) == 1
        )
        print(f"\n    [IP SOLVER] Requests served: {served_count}/{len(requests)}")

        if status != pulp.LpStatusOptimal:
            print(f"    [IP SOLVER] ✗ Not optimal! Status: {pulp.LpStatus[status]}")
            return []

        # Extract solution
        assignments = []
        for idx, var in group_vars.items():
            if pulp.value(var) == 1:
                group = feasible_groups[idx]
                print(f"    [IP SOLVER] ✓ Selected group {idx}: "
                      f"Driver {group['driver'].id} → "
                      f"{len(group['requests'])} passengers "
                      f"(cost: {group['total_cost']:.2f})")
                assignments.append((
                    group['driver'],
                    group['requests'],
                    group['route'],
                    group['individual_costs'],
                    group['detours']
                ))

        print(f"    [IP SOLVER] Final assignments: {len(assignments)}")
        return assignments

    def clear_cache(self):
        """Clear group cache"""
        self.group_cache.clear()