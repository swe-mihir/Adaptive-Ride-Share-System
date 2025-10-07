"""
Core entities for the carpooling OMD system.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum
import uuid
import numpy as np

class RequestStatus(Enum):
    WAITING = "waiting"
    MATCHED = "matched"
    IN_TRANSIT = "in_transit"
    COMPLETED = "completed"
    QUIT = "quit"

class DriverStatus(Enum):
    AVAILABLE = "available"
    EN_ROUTE_PICKUP = "en_route_pickup"
    IN_TRIP = "in_trip"

@dataclass
class Location:
    """Geographic location"""
    lat: float
    lon: float
    
    def to_tuple(self) -> Tuple[float, float]:
        return (self.lat, self.lon)
    
    def __hash__(self):
        return hash((round(self.lat, 6), round(self.lon, 6)))

@dataclass
class Request:
    """Ride request from a passenger"""
    id: str
    origin: Location
    destination: Location
    arrival_time: float
    weibull_shape: float
    weibull_scale: float
    waiting_cost_rate: float
    status: RequestStatus = RequestStatus.WAITING
    quit_time: Optional[float] = None
    match_time: Optional[float] = None
    pickup_time: Optional[float] = None
    completion_time: Optional[float] = None
    assigned_driver: Optional[str] = None
    threshold: Optional[float] = None


    # Carpooling specific
    trip_id: Optional[str] = None
    solo_trip_duration: Optional[float] = None
    actual_trip_duration: Optional[float] = None
    detour_ratio: Optional[float] = None
    cost_share: Optional[float] = None

    def generate_patience(self) -> float:
        """
        Generate patience time from Weibull distribution.

        Returns:
            Patience time in seconds
        """
        patience = np.random.weibull(self.weibull_shape) * self.weibull_scale
        return max(1.0, patience)  # Ensure minimum 1 second

    def sample_quit_time(self) -> float:
        """Sample quit time from Weibull distribution"""
        import numpy as np
        return np.random.weibull(self.weibull_shape) * self.weibull_scale
    
    def get_waiting_time(self, current_time: float) -> float:
        """Calculate current waiting time"""
        if self.match_time:
            return self.match_time - self.arrival_time
        return current_time - self.arrival_time
    
    def get_waiting_cost(self, current_time: float) -> float:
        """Calculate current waiting cost"""
        return self.get_waiting_time(current_time) * self.waiting_cost_rate
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'origin': {'lat': self.origin.lat, 'lon': self.origin.lon},
            'destination': {'lat': self.destination.lat, 'lon': self.destination.lon},
            'arrival_time': self.arrival_time,
            'status': self.status.value,
            'match_time': self.match_time,
            'trip_id': self.trip_id,
            'detour_ratio': self.detour_ratio,
            'cost_share': self.cost_share
        }

@dataclass
class DriverType:
    """Type of driver (Fast Response, Normal, Economy)"""
    id: int
    name: str
    base_cost: float
    arrival_rate: float
    speed_multiplier: float

@dataclass
class Driver:
    """Driver in the system"""
    id: str
    type: DriverType
    location: Location
    status: DriverStatus = DriverStatus.AVAILABLE
    current_trip: Optional[str] = None
    available_since: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'type': self.type.name,
            'location': {'lat': self.location.lat, 'lon': self.location.lon},
            'status': self.status.value,
            'current_trip': self.current_trip
        }

@dataclass
class Trip:
    """Active trip with multiple passengers"""
    id: str
    driver: Driver
    passengers: List[Request] = field(default_factory=list)
    route: List[Location] = field(default_factory=list)  # [P1, P2, ..., Pk, Destination]
    destination: Optional[Location] = None
    capacity: int = 3
    start_time: Optional[float] = None
    completion_time: Optional[float] = None

    # Route tracking
    current_position_index: int = 0  # Which stop we're heading to
    pickups_completed: List[str] = field(default_factory=list)

    # Costs
    total_route_cost: float = 0.0
    individual_costs: dict = field(default_factory=dict)  # passenger_id -> cost
    detour_ratios: dict = field(default_factory=dict)  # passenger_id -> detour_ratio

    def capacity_available(self) -> int:
        """Return available capacity"""
        return self.capacity - len(self.passengers)

    def is_full(self) -> bool:
        """Check if trip is at capacity"""
        return len(self.passengers) >= self.capacity

    def add_passenger(self, request: Request, new_route: List[Location],
                     new_costs: dict, new_detours: dict):
        """Add passenger via dynamic insertion"""
        self.passengers.append(request)
        self.route = new_route
        self.individual_costs = new_costs
        self.detour_ratios = new_detours
        request.trip_id = self.id
        request.status = RequestStatus.MATCHED

    def complete_pickup(self, request_id: str):
        """Mark a pickup as completed"""
        self.pickups_completed.append(request_id)
        self.current_position_index += 1

    def all_pickups_complete(self) -> bool:
        """Check if all pickups are done"""
        return len(self.pickups_completed) == len(self.passengers)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'driver_id': self.driver.id,
            'passengers': [p.id for p in self.passengers],
            'route': [{'lat': loc.lat, 'lon': loc.lon} for loc in self.route],
            'capacity_used': len(self.passengers),
            'capacity_available': self.capacity_available(),
            'pickups_completed': self.pickups_completed,
            'total_cost': self.total_route_cost,
            'individual_costs': self.individual_costs,
            'detour_ratios': self.detour_ratios
        }

def generate_request_id() -> str:
    """Generate unique request ID"""
    return f"r_{uuid.uuid4().hex[:8]}"

def generate_driver_id() -> str:
    """Generate unique driver ID"""
    return f"d_{uuid.uuid4().hex[:8]}"

def generate_trip_id() -> str:
    """Generate unique trip ID"""
    return f"t_{uuid.uuid4().hex[:8]}"
