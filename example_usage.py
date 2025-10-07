"""
Quick start example for carpooling OMD system.
Demonstrates basic usage and customization.
"""

import yaml
import numpy as np
from pathlib import Path

# Import components
from core.entities import DriverType, Location
from utils.osrm_interface import OSRMClient
from simulation.simulator import CarpoolSimulator
from utils.visualization import SimulationVisualizer

def example_1_basic_simulation():
    """Example 1: Run basic simulation with default config"""
    print("=" * 60)
    print("Example 1: Basic Simulation")
    print("=" * 60)
    
    # Load config
    with open('config_yaml.txt', 'r') as f:
        config = yaml.safe_load(f)
    
    # Override for quick test
    config['simulation']['duration'] = 600  # 10 minutes
    config['simulation']['initial_drivers'] = 20
    
    # Initialize
    np.random.seed(42)
    osrm = OSRMClient(config['osrm']['server_url'])
    driver_types = [DriverType(**dt) for dt in config['driver_types']]
    
    # Create simulator
    sim = CarpoolSimulator(config, driver_types, osrm)
    
    # Run
    print("\nRunning simulation for 10 minutes...")
    sim.run(600)
    
    # Results
    summary = sim.get_summary()
    print(f"\n✓ Simulation Complete!")
    print(f"  Requests: {summary['total_requests']}")
    print(f"  Matches: {summary['total_matches']}")
    print(f"  Match Rate: {summary['match_rate']:.1%}")
    print(f"  Avg Pool Size: {summary['avg_pool_size']:.2f}")
    
    # Save metrics
    sim.save_metrics("example1_metrics.json")
    print(f"\n✓ Metrics saved to example1_metrics.json")
    
    return sim

def example_2_custom_parameters():
    """Example 2: Customize simulation parameters"""
    print("\n" + "=" * 60)
    print("Example 2: Custom Parameters")
    print("=" * 60)
    
    config = {
        'simulation': {
            'duration': 1800,  # 30 minutes
            'initial_drivers': 30,
            'random_seed': 123
        },
        'region': {
            'name': 'Mumbai',
            'bounds': {
                'lat_min': 18.9,
                'lat_max': 19.3,
                'lon_min': 72.8,
                'lon_max': 72.95
            }
        },
        'osrm': {
            'server_url': 'http://127.0.0.1:5000',
            'cache_size': 5000,
            'batch_size': 100
        },
        'carpooling': {
            'capacity': 3,
            'detour_max': 1.3,  # Stricter: max 30% detour
            'destination_cluster_radius_km': 0.5,  # Tighter clusters
            'dynamic_insertion_enabled': True
        },
        'costs': {
            'waiting_cost_per_sec': 0.75,  # Higher waiting cost
            'quit_penalty': 150,
            'detour_penalty_per_sec': 3
        },
        'driver_types': [
            {'id': 1, 'name': 'Premium', 'base_cost': 30, 'arrival_rate': 0.05, 'speed_multiplier': 1.3},
            {'id': 2, 'name': 'Standard', 'base_cost': 20, 'arrival_rate': 0.1, 'speed_multiplier': 1.0},
            {'id': 3, 'name': 'Economy', 'base_cost': 15, 'arrival_rate': 0.15, 'speed_multiplier': 0.9}
        ],
        'requests': {
            'arrival_rate': 0.08,  # Higher demand
            'weibull_shape': 1.5,
            'weibull_scale': 240
        },
        'metrics': {
            'update_interval': 15,
            'output_file': 'example2_metrics.json',
            'track_history': True,
            'enable_streaming': True
        }
    }
    
    print("\n📋 Configuration:")
    print(f"  Region: {config['region']['name']}")
    print(f"  Capacity: {config['carpooling']['capacity']}")
    print(f"  Max Detour: {config['carpooling']['detour_max']}x")
    print(f"  Request Rate: {config['requests']['arrival_rate']}/sec")
    
    # Initialize
    np.random.seed(config['simulation']['random_seed'])
    osrm = OSRMClient(config['osrm']['server_url'])
    driver_types = [DriverType(**dt) for dt in config['driver_types']]
    
    sim = CarpoolSimulator(config, driver_types, osrm)
    
    print("\nRunning simulation...")
    sim.run(config['simulation']['duration'])
    
    # Results
    summary = sim.get_summary()
    print(f"\n✓ Complete!")
    print(f"  Total Cost: ₹{summary['total_cost']:.2f}")
    print(f"  Dynamic Insertions: {summary['dynamic_insertions']}")
    
    sim.save_metrics(config['metrics']['output_file'])
    
    return sim

def example_3_event_callbacks():
    """Example 3: Use event callbacks for real-time monitoring"""
    print("\n" + "=" * 60)
    print("Example 3: Real-time Event Monitoring")
    print("=" * 60)
    
    # Load basic config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    config['simulation']['duration'] = 300  # 5 minutes for demo

    # Initialize
    np.random.seed(42)
    osrm = OSRMClient(config['osrm']['server_url'])
    driver_types = [DriverType(**dt) for dt in config['driver_types']]
    sim = CarpoolSimulator(config, driver_types, osrm)

    # Event counters
    event_counts = {'match': 0, 'quit': 0, 'dynamic_insertion': 0}

    # Define callback
    def on_event(event):
        event_type = event['type']

        if event_type == 'match':
            event_counts['match'] += 1
            pool_size = event['pool_size']
            print(f"  ✓ Match #{event_counts['match']}: {pool_size} passengers (Trip {event['trip_id'][:8]})")

        elif event_type == 'dynamic_insertion':
            event_counts['dynamic_insertion'] += 1
            print(f"  ⚡ Dynamic insertion #{event_counts['dynamic_insertion']}: Request {event['request_id'][:8]} → Trip {event['trip_id'][:8]}")

        elif event_type == 'quit':
            event_counts['quit'] += 1
            print(f"  ✗ Quit #{event_counts['quit']}: Request {event['request_id'][:8]} after {event['waiting_time']:.1f}s")

    # Register callback
    sim.metrics.register_callback(on_event)

    print("\n🔔 Monitoring events...")
    print("-" * 60)

    sim.run(config['simulation']['duration'])

    print("-" * 60)
    print(f"\n📊 Event Summary:")
    print(f"  Matches: {event_counts['match']}")
    print(f"  Dynamic Insertions: {event_counts['dynamic_insertion']}")
    print(f"  Quits: {event_counts['quit']}")

    return sim

def example_4_analyze_results():
    """Example 4: Analyze simulation results with visualization"""
    print("\n" + "=" * 60)
    print("Example 4: Result Analysis & Visualization")
    print("=" * 60)

    # Check if metrics file exists
    metrics_file = "metrics.json"
    if not Path(metrics_file).exists():
        print(f"\n⚠ {metrics_file} not found. Running simulation first...")
        sim = example_1_basic_simulation()
        metrics_file = "example1_metrics.json"

    # Load and visualize
    print(f"\n📊 Loading metrics from {metrics_file}...")
    viz = SimulationVisualizer(metrics_file)

    # Print summary
    viz.print_summary()

    # Generate plots
    print("\n📈 Generating visualizations...")
    try:
        viz.plot_summary_dashboard("dashboard.png")
        print("  ✓ dashboard.png")

        viz.plot_pool_utilization("pool_utilization.png")
        print("  ✓ pool_utilization.png")

        viz.plot_cost_breakdown("cost_breakdown.png")
        print("  ✓ cost_breakdown.png")

        viz.plot_driver_performance("driver_performance.png")
        print("  ✓ driver_performance.png")

        print("\n✓ All visualizations saved!")
    except Exception as e:
        print(f"\n⚠ Visualization failed: {e}")
        print("  (Make sure matplotlib is installed)")

def example_5_osrm_testing():
    """Example 5: Test OSRM connection and caching"""
    print("\n" + "=" * 60)
    print("Example 5: OSRM Testing")
    print("=" * 60)

    osrm = OSRMClient("http://127.0.0.1:5000", cache_size=100)

    # Test locations in Maharashtra
    mumbai = (19.0760, 72.8777)
    pune = (18.5204, 73.8567)
    nagpur = (21.1458, 79.0882)

    print("\n🗺️  Testing OSRM connectivity...")

    try:
        # Test route
        duration = osrm.get_duration(mumbai, pune)
        distance = osrm.get_distance(mumbai, pune)

        print(f"✓ OSRM is working!")
        print(f"\n  Mumbai → Pune:")
        print(f"    Duration: {duration/60:.1f} minutes")
        print(f"    Distance: {distance/1000:.1f} km")

        # Test caching
        print("\n🔄 Testing cache...")

        # First call (cache miss)
        osrm.get_duration(mumbai, nagpur)
        stats1 = osrm.get_cache_stats()

        # Second call (cache hit)
        osrm.get_duration(mumbai, nagpur)
        stats2 = osrm.get_cache_stats()

        print(f"  Cache size: {stats2['cache_size']}")
        print(f"  Hit rate: {stats2['hit_rate']:.1%}")
        print(f"  ✓ Caching works!")

        # Test matrix API
        print("\n📊 Testing matrix API...")
        sources = [mumbai, pune]
        destinations = [nagpur, (20.0, 77.0)]

        matrix = osrm.get_matrix(sources, destinations)
        print(f"  ✓ Matrix computed: {len(matrix['durations'])}x{len(matrix['durations'][0])}")

    except Exception as e:
        print(f"✗ OSRM test failed: {e}")
        print("\n⚠ Make sure OSRM server is running at http://127.0.0.1:5000")
        print("  See README.md for setup instructions")

def example_6_compare_strategies():
    """Example 6: Compare with/without dynamic insertion"""
    print("\n" + "=" * 60)
    print("Example 6: Strategy Comparison")
    print("=" * 60)

    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    config['simulation']['duration'] = 900  # 15 minutes

    results = {}

    for strategy in ['without_insertion', 'with_insertion']:
        print(f"\n📍 Running: {strategy.replace('_', ' ').title()}")

        # Toggle dynamic insertion
        config['carpooling']['dynamic_insertion_enabled'] = (strategy == 'with_insertion')

        # Initialize
        np.random.seed(42)  # Same seed for fair comparison
        osrm = OSRMClient(config['osrm']['server_url'])
        driver_types = [DriverType(**dt) for dt in config['driver_types']]

        sim = CarpoolSimulator(config, driver_types, osrm)
        sim.run(config['simulation']['duration'])

        summary = sim.get_summary()
        results[strategy] = summary

        print(f"  Matches: {summary['total_matches']}")
        print(f"  Avg Pool: {summary['avg_pool_size']:.2f}")
        print(f"  Cost: ₹{summary['total_cost']:.2f}")

    # Comparison
    print("\n" + "=" * 60)
    print("📊 COMPARISON")
    print("=" * 60)

    without = results['without_insertion']
    with_ins = results['with_insertion']

    print(f"\nMatches:")
    print(f"  Without: {without['total_matches']}")
    print(f"  With:    {with_ins['total_matches']} (+{with_ins['total_matches']-without['total_matches']})")

    print(f"\nAverage Pool Size:")
    print(f"  Without: {without['avg_pool_size']:.2f}")
    print(f"  With:    {with_ins['avg_pool_size']:.2f} (+{(with_ins['avg_pool_size']-without['avg_pool_size']):.2f})")

    print(f"\nTotal Cost:")
    print(f"  Without: ₹{without['total_cost']:.2f}")
    print(f"  With:    ₹{with_ins['total_cost']:.2f} (Δ{(with_ins['total_cost']-without['total_cost']):.2f})")

    print(f"\nDynamic Insertions: {with_ins['dynamic_insertions']}")

    cost_savings = without['total_cost'] - with_ins['total_cost']
    if cost_savings > 0:
        print(f"\n💰 Cost Savings: ₹{cost_savings:.2f} ({cost_savings/without['total_cost']*100:.1f}%)")
    else:
        print(f"\n⚠ Cost Increase: ₹{-cost_savings:.2f}")

def main():
    """Run all examples"""
    print("\n" + "🚗" * 30)
    print("CARPOOLING OMD SYSTEM - EXAMPLES")
    print("🚗" * 30)

    examples = [
        ("Basic Simulation", example_1_basic_simulation),
        ("Custom Parameters", example_2_custom_parameters),
        ("Event Callbacks", example_3_event_callbacks),
        ("Result Analysis", example_4_analyze_results),
        ("OSRM Testing", example_5_osrm_testing),
        ("Strategy Comparison", example_6_compare_strategies)
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    print(f"  0. Run all")

    choice = input("\nSelect example (0-6): ").strip()

    if choice == '0':
        for name, func in examples:
            try:
                func()
            except KeyboardInterrupt:
                print("\n\n⚠ Interrupted by user")
                break
            except Exception as e:
                print(f"\n✗ Example failed: {e}")
                import traceback
                traceback.print_exc()
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        name, func = examples[int(choice) - 1]
        try:
            func()
        except Exception as e:
            print(f"\n✗ Example failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Invalid choice!")

    print("\n" + "=" * 60)
    print("Done! Check the generated files and metrics.")
    print("=" * 60)

if __name__ == "__main__":
    main()