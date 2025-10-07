"""
Dual simulator - runs FCFS and Optimal algorithms simultaneously
with the same random events for fair comparison.
"""

import numpy as np
from typing import List
from core.entities import DriverType, Request, Driver, Location, generate_request_id, generate_driver_id
from utils.osrm_interface import OSRMClient
from simulation.simulator import CarpoolSimulator
from simulation.fcfs_simulator import FCFSSimulator

class DualSimulator:
    """Run FCFS and Optimal algorithms side-by-side"""
    
    def __init__(self, config: dict):
        self.config = config
        
        # Set seed for reproducibility
        np.random.seed(config['simulation']['random_seed'])
        
        # Pre-generate all random events
        self.events = self._generate_events(config['simulation']['duration'])
        
        # Create OSRM client (shared)
        self.osrm = OSRMClient(
            config['osrm']['server_url'],
            config['osrm']['cache_size']
        )
        
        # Create driver types
        self.driver_types = [DriverType(**dt) for dt in config['driver_types']]
        
        # Create both simulators
        self.sim_fcfs = FCFSSimulator(config, self.driver_types, self.osrm, self.events)
        self.sim_optimal = CarpoolSimulator(config, self.driver_types, self.osrm, self.events)
        
        print("✓ Dual simulator initialized")
        print(f"  - FCFS simulator ready")
        print(f"  - Optimal simulator ready")
        print(f"  - {len(self.events['requests'])} request events")
        print(f"  - {sum(len(events) for events in self.events['drivers'].values())} driver events")
    
    def _generate_events(self, duration: float) -> dict:
        """
        Pre-generate all random events so both simulators see same data.
        
        Returns:
            dict with 'requests' and 'drivers' event lists
        """
        events = {
            'requests': [],
            'drivers': {dt['id']: [] for dt in self.config['driver_types']}
        }
        
        bounds = self.config['region']['bounds']
        
        # Generate request arrivals
        request_rate = self.config['requests']['arrival_rate']
        current_time = 0.0
        
        while current_time < duration:
            # Next arrival time
            current_time += np.random.exponential(1.0 / request_rate)
            
            if current_time >= duration:
                break
            
            # Create request event
            events['requests'].append({
                'time': current_time,
                'id': generate_request_id(),
                'origin': (
                    np.random.uniform(bounds['lat_min'], bounds['lat_max']),
                    np.random.uniform(bounds['lon_min'], bounds['lon_max'])
                ),
                'destination': (
                    np.random.uniform(bounds['lat_min'], bounds['lat_max']),
                    np.random.uniform(bounds['lon_min'], bounds['lon_max'])
                ),
                'weibull_shape': self.config['requests']['weibull_shape'],
                'weibull_scale': self.config['requests']['weibull_scale']
            })
        
        # Generate driver arrivals for each type
        for driver_type in self.config['driver_types']:
            current_time = 0.0
            arrival_rate = driver_type['arrival_rate']
            
            while current_time < duration:
                current_time += np.random.exponential(1.0 / arrival_rate)
                
                if current_time >= duration:
                    break
                
                events['drivers'][driver_type['id']].append({
                    'time': current_time,
                    'id': generate_driver_id(),
                    'type_id': driver_type['id'],
                    'location': (
                        np.random.uniform(bounds['lat_min'], bounds['lat_max']),
                        np.random.uniform(bounds['lon_min'], bounds['lon_max'])
                    )
                })
        
        return events
    
    def run(self, duration: float):
        """Run both simulators simultaneously"""
        print(f"\n{'='*60}")
        print("Starting Dual Simulation")
        print(f"{'='*60}")
        
        # Run FCFS
        print("\n[FCFS Algorithm]")
        self.sim_fcfs.run(duration)
        
        # Reset seed for optimal to ensure same events
        np.random.seed(self.config['simulation']['random_seed'])
        
        # Run Optimal
        print("\n[Optimal Algorithm]")
        self.sim_optimal.run(duration)
        
        print(f"\n{'='*60}")
        print("Simulation Complete")
        print(f"{'='*60}")
        
        self._print_comparison()
    
    def _print_comparison(self):
        """Print comparison between algorithms"""
        fcfs_summary = self.sim_fcfs.get_summary()
        optimal_summary = self.sim_optimal.get_summary()
        
        print("\n" + "="*60)
        print("ALGORITHM COMPARISON")
        print("="*60)
        
        print(f"\n📊 Requests:")
        print(f"  FCFS:    {fcfs_summary['total_requests']}")
        print(f"  Optimal: {optimal_summary['total_requests']}")
        
        print(f"\n✓ Matches:")
        print(f"  FCFS:    {fcfs_summary['total_matches']} ({fcfs_summary['match_rate']:.1%})")
        print(f"  Optimal: {optimal_summary['total_matches']} ({optimal_summary['match_rate']:.1%})")
        
        print(f"\n🚗 Avg Pool Size:")
        print(f"  FCFS:    {fcfs_summary['avg_pool_size']:.2f}")
        print(f"  Optimal: {optimal_summary['avg_pool_size']:.2f}")
        
        print(f"\n⚡ Dynamic Insertions:")
        print(f"  FCFS:    {fcfs_summary['dynamic_insertions']}")
        print(f"  Optimal: {optimal_summary['dynamic_insertions']}")
        
        print(f"\n💰 Total Cost:")
        print(f"  FCFS:    ₹{fcfs_summary['total_cost']:.2f}")
        print(f"  Optimal: ₹{optimal_summary['total_cost']:.2f}")
        
        if fcfs_summary['total_cost'] > optimal_summary['total_cost']:
            savings = fcfs_summary['total_cost'] - optimal_summary['total_cost']
            pct = (savings / fcfs_summary['total_cost']) * 100
            print(f"\n  💡 Optimal saves ₹{savings:.2f} ({pct:.1f}%)")
        
        print("\n" + "="*60)
    
    def get_comparison_metrics(self) -> dict:
        """Get detailed comparison metrics"""
        return {
            'fcfs': self.sim_fcfs.metrics.get_current_metrics(self.sim_fcfs.time),
            'optimal': self.sim_optimal.metrics.get_current_metrics(self.sim_optimal.time)
        }
