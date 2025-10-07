"""
Carpooling Online Matching with Delays (OMD) System
Based on Wang Hao PhD thesis (NTU 2022) - Extended for carpooling

Main entry point for the simulation.
"""

import yaml
import json
import numpy as np
from datetime import datetime
from pathlib import Path

# Configuration
CONFIG_PATH = "config_yaml.txt"

def load_config():
    """Load configuration from YAML file"""
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

def create_default_config():
    """Create default configuration file"""
    config = {
        'simulation': {
            'duration': 300,  # 2 hours
            'max_drivers': 50,
            'initial_drivers': 50,
            'random_seed': 42
        },
        'region': {
            'name': 'Maharashtra',
            'bounds': {
                'lat_min': 15.6,
                'lat_max': 22.1,
                'lon_min': 72.6,
                'lon_max': 80.9
            }
        },
        'osrm': {
            'server_url': 'http://127.0.0.1:5000',
            'cache_size': 10000,
            'batch_size': 100
        },
        'carpooling': {
            'capacity': 3,
            'detour_max': 1.5,
            'destination_cluster_radius_km': 1.0,
            'dynamic_insertion_enabled': True
        },
        'costs': {
            'waiting_cost_per_sec': 0.5,
            'quit_penalty': 100,
            'detour_penalty_per_sec': 2
        },
        'driver_types': [
            {'id': 1, 'name': 'Fast Response', 'base_cost': 20, 'arrival_rate': 0.1, 'speed_multiplier': 1.2},
            {'id': 2, 'name': 'Normal', 'base_cost': 15, 'arrival_rate': 0.15, 'speed_multiplier': 1.0},
            {'id': 3, 'name': 'Economy', 'base_cost': 10, 'arrival_rate': 0.2, 'speed_multiplier': 0.9}
        ],
        'requests': {
            'arrival_rate': 0.05,
            'weibull_shape': 2.0,
            'weibull_scale': 300
        },
        'metrics': {
            'update_interval': 10,
            'output_file': 'metrics.json',
            'track_history': True,
            'enable_streaming': True
        }
    }
    
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    
    return config

def main():
    """Main entry point"""
    print("=" * 60)
    print("Carpooling OMD Simulation System")
    print("=" * 60)
    
    # Load or create config
    try:
        config = load_config()
        print(f"✓ Loaded configuration from {CONFIG_PATH}")
    except FileNotFoundError:
        print(f"⚠ Config file not found. Creating default: {CONFIG_PATH}")
        config = create_default_config()
    
    # Set random seed
    np.random.seed(config['simulation']['random_seed'])
    print(f"✓ Random seed set to {config['simulation']['random_seed']}")
    
    # Initialize components
    print("\nInitializing system components...")
    
    from core.entities import DriverType
    from utils.osrm_interface import OSRMClient
    from simulation.simulator import CarpoolSimulator
    
    # Initialize OSRM client
    osrm = OSRMClient(
        server_url=config['osrm']['server_url'],
        cache_size=config['osrm']['cache_size']
    )
    print(f"✓ OSRM client connected to {config['osrm']['server_url']}")
    
    # Create driver types
    driver_types = [DriverType(**dt) for dt in config['driver_types']]
    print(f"✓ Loaded {len(driver_types)} driver types")
    
    # Initialize simulator
    simulator = CarpoolSimulator(config, driver_types, osrm)
    print(f"✓ Initial drivers: {len(simulator.available_drivers)}")
    print(f"✓ Driver types: {[dt.name for dt in driver_types]}")
    print(f"✓ Simulator initialized")

    # Run simulation
    print(f"\nStarting simulation for {config['simulation']['duration']} seconds...")
    print("-" * 60)
    
    simulator.run(config['simulation']['duration'])
    
    print("\n" + "=" * 60)
    print("Simulation Complete!")
    print("=" * 60)
    simulator.print_active_pools()
    # Print final summary
    summary = simulator.get_summary()
    print("\nFinal Statistics:")
    print(f"  Total Requests: {summary['total_requests']}")
    print(f"  Total Matches: {summary['total_matches']}")
    print(f"  Total Quits: {summary['total_quits']}")
    print(f"  Match Rate: {summary['match_rate']:.1%}")
    print(f"  Avg Pool Size: {summary['avg_pool_size']:.2f}")
    print(f"  Dynamic Insertions: {summary['dynamic_insertions']}")
    print(f"  Total Cost: ₹{summary['total_cost']:.2f}")


    
    # Save final metrics
    output_file = config['metrics']['output_file']
    simulator.save_metrics(output_file)
    print(f"\n✓ Metrics saved to {output_file}")

if __name__ == "__main__":
    main()
