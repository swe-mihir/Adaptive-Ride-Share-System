"""
Threshold policy computation for carpooling OMD.
Adapted from single-request OMD to account for pooling opportunities.
"""

import numpy as np
from typing import List
from core.entities import Request, DriverType

class ThresholdPolicy:
    """Compute optimal thresholds for matching decisions"""
    
    def __init__(self, driver_types: List[DriverType], quit_penalty: float,
                 pooling_benefit_factor: float = 0.3):
        """
        Args:
            driver_types: List of driver types (sorted by cost)
            quit_penalty: Cost of request quitting (c_q)
            pooling_benefit_factor: Adjustment factor for pooling (α)
        """
        self.driver_types = sorted(driver_types, key=lambda dt: dt.base_cost)
        self.quit_penalty = quit_penalty
        self.alpha = pooling_benefit_factor
        
    def compute_threshold(self, request: Request, current_pool_size: int,
                         capacity: int = 3) -> float:
        """
        Compute threshold time for a request.
        
        For carpooling, we adjust the original threshold based on:
        - Current pool size (more requests waiting → lower threshold)
        - Pooling benefit (opportunity to share costs)
        
        Original threshold from Theorem 4.2:
        q(T_j) >= [Σ λ_i(b_j - b_i) - 1] / (c_q - b_j)
        
        Carpooling adjustment:
        T'_j = T_j * (1 - α * n / K)
        where n = current pool size, K = capacity
        
        Args:
            request: Request to compute threshold for
            current_pool_size: Number of waiting requests
            capacity: Vehicle capacity
            
        Returns:
            Threshold time in seconds
        """
        # Use cheapest driver type (Economy - type 3)
        cheapest_type = self.driver_types[0]
        
        # Compute base threshold using Weibull hazard rate
        base_threshold = self._compute_base_threshold(request, cheapest_type)
        
        # Apply carpooling adjustment
        pooling_factor = 1 - self.alpha * min(current_pool_size, capacity) / capacity
        adjusted_threshold = base_threshold * pooling_factor
        
        # Ensure threshold is positive
        return max(1.0, adjusted_threshold)
    
    def _compute_base_threshold(self, request: Request, driver_type: DriverType) -> float:
        """
        Compute base threshold using original OMD formula.
        
        Solve: q(T) >= [Σ λ_i(b_j - b_i) - 1] / (c_q - b_j)
        
        For simplicity with multiple driver types, we use the cheapest type
        and assume request should wait for better options.
        """
        # Weibull hazard rate: q(t) = (k/λ) * (t/λ)^(k-1)
        k = request.weibull_shape
        lam = request.weibull_scale
        
        # Right-hand side of threshold condition
        # Simplified: assume we're comparing with next-best driver type
        if len(self.driver_types) < 2:
            # Only one type, use simple threshold
            rhs = 1.0 / (self.quit_penalty - driver_type.base_cost)
        else:
            next_type = self.driver_types[1]
            lambda_sum = sum(dt.arrival_rate * (next_type.base_cost - dt.base_cost) 
                           for dt in self.driver_types if dt.base_cost < next_type.base_cost)
            rhs = max(0, (lambda_sum - 1) / (self.quit_penalty - next_type.base_cost))
        
        # Solve q(T) = rhs for T
        # q(T) = (k/lam) * (T/lam)^(k-1) = rhs
        # (T/lam)^(k-1) = rhs * lam / k
        # T = lam * (rhs * lam / k)^(1/(k-1))
        
        if k == 1:
            # Exponential case: q(t) = 1/lam (constant)
            threshold = lam * rhs
        else:
            if rhs <= 0:
                threshold = 0
            else:
                threshold = lam * np.power(rhs * lam / k, 1.0 / (k - 1))
        
        # Bound threshold to reasonable range
        return np.clip(threshold, 1.0, 600.0)  # 1 sec to 10 min
    
    def compute_thresholds_for_all_types(self, request: Request,
                                        current_pool_size: int,
                                        capacity: int = 3) -> dict:
        """
        Compute thresholds for all driver types.
        
        Returns:
            Dict mapping driver_type_id -> threshold
        """
        thresholds = {}
        for driver_type in self.driver_types:
            base_t = self._compute_base_threshold(request, driver_type)
            pooling_factor = 1 - self.alpha * min(current_pool_size, capacity) / capacity
            thresholds[driver_type.id] = max(1.0, base_t * pooling_factor)
        
        return thresholds
    
    def should_match_now(self, request: Request, driver_type: DriverType,
                        current_time: float, current_pool_size: int,
                        capacity: int = 3) -> bool:
        """
        Decide if request should be matched to driver now.
        
        Args:
            request: Request waiting
            driver_type: Available driver type
            current_time: Current simulation time
            current_pool_size: Number of waiting requests
            capacity: Vehicle capacity
            
        Returns:
            True if should match now
        """
        waiting_time = current_time - request.arrival_time
        threshold = self.compute_threshold(request, current_pool_size, capacity)
        
        return waiting_time >= threshold
