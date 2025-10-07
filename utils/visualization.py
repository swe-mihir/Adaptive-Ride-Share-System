"""
Visualization tools for carpooling OMD simulation.
Optional module for analyzing simulation results.
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List
import json

class SimulationVisualizer:
    """Visualize simulation metrics and results"""
    
    def __init__(self, metrics_file = "metrics.json"):
        """
        Args:
            metrics_file: Path to metrics JSON file
        """
        with open("C:/Users/mihir/PycharmProjects/ASR/metrics.json", 'r') as f:
            self.metrics = json.load(f)
    
    def plot_pool_utilization(self, save_path: str = None):
        """Plot distribution of pool sizes"""
        pool_stats = self.metrics['carpooling']['pool_utilization']
        
        sizes = list(pool_stats.keys())
        counts = list(pool_stats.values())
        
        plt.figure(figsize=(8, 6))
        plt.bar(sizes, counts, color=['#1f77b4', '#ff7f0e', '#2ca02c'])
        plt.xlabel('Pool Size (Passengers per Trip)')
        plt.ylabel('Number of Trips')
        plt.title('Pool Utilization Distribution')
        plt.xticks(sizes)
        
        # Add percentages on bars
        total = sum(counts)
        for i, (size, count) in enumerate(zip(sizes, counts)):
            pct = (count / total) * 100
            plt.text(size, count + max(counts)*0.02, f'{pct:.1f}%', 
                    ha='center', va='bottom')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def plot_cost_breakdown(self, save_path: str = None):
        """Plot cost breakdown pie chart"""
        costs = self.metrics['cost_breakdown']
        
        labels = ['Waiting', 'Routing', 'Quit Penalty', 'Detour Penalty']
        values = [
            costs['waiting_cost'],
            costs['routing_cost'],
            costs['quit_penalty'],
            costs['detour_penalty']
        ]
        
        colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']
        
        plt.figure(figsize=(8, 8))
        plt.pie(values, labels=labels, autopct='%1.1f%%', colors=colors,
                startangle=90)
        plt.title('Total Cost Breakdown')
        plt.axis('equal')
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def plot_driver_performance(self, save_path: str = None):
        """Plot driver type performance comparison"""
        driver_stats = self.metrics['driver_stats']
        
        types = list(driver_stats.keys())
        trips = [stats['trips'] for stats in driver_stats.values()]
        passengers = [stats['passengers'] for stats in driver_stats.values()]
        avg_pool = [p/t if t > 0 else 0 for p, t in zip(passengers, trips)]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Trips by type
        ax1.bar(types, trips, color=['#1f77b4', '#ff7f0e', '#2ca02c'])
        ax1.set_xlabel('Driver Type')
        ax1.set_ylabel('Number of Trips')
        ax1.set_title('Trips Completed by Driver Type')
        
        # Average pool size by type
        ax2.bar(types, avg_pool, color=['#1f77b4', '#ff7f0e', '#2ca02c'])
        ax2.set_xlabel('Driver Type')
        ax2.set_ylabel('Average Passengers per Trip')
        ax2.set_title('Pool Size by Driver Type')
        ax2.axhline(y=np.mean(avg_pool), color='r', linestyle='--', 
                   label='Overall Average')
        ax2.legend()
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def plot_summary_dashboard(self, save_path: str = None):
        """Create comprehensive dashboard"""
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # 1. Pool utilization
        ax1 = fig.add_subplot(gs[0, 0])
        pool_stats = self.metrics['carpooling']['pool_utilization']
        ax1.bar(pool_stats.keys(), pool_stats.values(), 
               color=['#1f77b4', '#ff7f0e', '#2ca02c'])
        ax1.set_title('Pool Utilization')
        ax1.set_xlabel('Pool Size')
        ax1.set_ylabel('Trips')
        
        # 2. Match rate
        ax2 = fig.add_subplot(gs[0, 1])
        cumulative = self.metrics['cumulative']
        match_rate = cumulative['match_rate']
        ax2.pie([match_rate, 1-match_rate], labels=['Matched', 'Quit'],
               autopct='%1.1f%%', colors=['#2ca02c', '#d62728'])
        ax2.set_title(f'Match Rate: {match_rate:.1%}')
        
        # 3. Key metrics
        ax3 = fig.add_subplot(gs[0, 2])
        ax3.axis('off')
        metrics_text = f"""
        Total Requests: {cumulative['total_requests']}
        Total Matches: {cumulative['total_matches']}
        Total Quits: {cumulative['total_quits']}
        
        Avg Pool Size: {self.metrics['carpooling']['avg_pool_size']:.2f}
        Avg Waiting: {cumulative['avg_waiting_time']:.1f}s
        Avg Detour: {cumulative['avg_detour_ratio']:.2f}x
        
        Dynamic Insertions: {self.metrics['carpooling']['dynamic_insertions']}
        Insertion Rate: {self.metrics['carpooling']['insertion_rate']:.1%}
        """
        ax3.text(0.1, 0.5, metrics_text, fontsize=11, 
                verticalalignment='center', family='monospace')
        ax3.set_title('Summary Statistics')
        
        # 4. Cost breakdown
        ax4 = fig.add_subplot(gs[1, :])
        costs = self.metrics['cost_breakdown']
        cost_labels = ['Waiting', 'Routing', 'Quit Penalty', 'Detour Penalty']
        cost_values = [costs['waiting_cost'], costs['routing_cost'],
                      costs['quit_penalty'], costs['detour_penalty']]
        colors = ['#ff9999', '#66b3ff', '#99ff99', '#ffcc99']
        
        bars = ax4.barh(cost_labels, cost_values, color=colors)
        ax4.set_xlabel('Cost (₹)')
        ax4.set_title('Cost Breakdown')
        
        # Add values on bars
        for bar, value in zip(bars, cost_values):
            ax4.text(value + max(cost_values)*0.02, bar.get_y() + bar.get_height()/2,
                    f'₹{value:.2f}', va='center')
        
        # 5. Driver performance
        ax5 = fig.add_subplot(gs[2, :2])
        driver_stats = self.metrics['driver_stats']
        types = list(driver_stats.keys())
        trips = [stats['trips'] for stats in driver_stats.values()]
        passengers = [stats['passengers'] for stats in driver_stats.values()]
        
        x = np.arange(len(types))
        width = 0.35
        
        bars1 = ax5.bar(x - width/2, trips, width, label='Trips', color='#1f77b4')
        bars2 = ax5.bar(x + width/2, passengers, width, label='Passengers', color='#ff7f0e')
        
        ax5.set_xlabel('Driver Type')
        ax5.set_ylabel('Count')
        ax5.set_title('Driver Performance')
        ax5.set_xticks(x)
        ax5.set_xticklabels(types)
        ax5.legend()
        
        # 6. Carpooling efficiency
        ax6 = fig.add_subplot(gs[2, 2])
        total_trips = sum(pool_stats.values())
        solo_trips = pool_stats.get('1', 0)
        pooled_trips = total_trips - solo_trips
        
        pooling_rate = pooled_trips / total_trips if total_trips > 0 else 0
        ax6.pie([pooling_rate, 1-pooling_rate], 
               labels=['Pooled', 'Solo'],
               autopct='%1.1f%%', colors=['#2ca02c', '#ff7f0e'])
        ax6.set_title(f'Pooling Rate: {pooling_rate:.1%}')
        
        fig.suptitle('Carpooling OMD Simulation Dashboard', fontsize=16, y=0.98)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def print_summary(self):
        """Print text summary of results"""
        print("=" * 60)
        print("CARPOOLING OMD SIMULATION SUMMARY")
        print("=" * 60)
        
        cumulative = self.metrics['cumulative']
        carpooling = self.metrics['carpooling']
        costs = self.metrics['cost_breakdown']
        
        print(f"\n📊 Overall Performance:")
        print(f"  Total Requests:    {cumulative['total_requests']}")
        print(f"  Matched:           {cumulative['total_matches']} ({cumulative['match_rate']:.1%})")
        print(f"  Quit:              {cumulative['total_quits']}")
        
        print(f"\n🚗 Carpooling Metrics:")
        print(f"  Avg Pool Size:     {carpooling['avg_pool_size']:.2f} passengers/trip")
        print(f"  Total Trips:       {carpooling['total_trips']}")
        print(f"  Pool Distribution:")
        pool_stats = carpooling['pool_utilization']
        total_trips = sum(pool_stats.values())
        for size, count in sorted(pool_stats.items()):
            pct = (count / total_trips) * 100 if total_trips > 0 else 0
            print(f"    {size} passenger(s): {count:4d} trips ({pct:5.1f}%)")
        
        print(f"\n⚡ Dynamic Insertion:")
        print(f"  Insertions:        {carpooling['dynamic_insertions']}")
        print(f"  Insertion Rate:    {carpooling['insertion_rate']:.1%}")
        
        print(f"\n⏱️  Timing:")
        print(f"  Avg Waiting Time:  {cumulative['avg_waiting_time']:.1f} seconds")
        print(f"  Avg Detour Ratio:  {cumulative['avg_detour_ratio']:.2f}x")
        
        print(f"\n💰 Cost Breakdown:")
        total_cost = cumulative['total_cost']
        print(f"  Total Cost:        ₹{total_cost:.2f}")
        print(f"  Waiting Cost:      ₹{costs['waiting_cost']:.2f} ({costs['waiting_cost']/total_cost*100:.1f}%)")
        print(f"  Routing Cost:      ₹{costs['routing_cost']:.2f} ({costs['routing_cost']/total_cost*100:.1f}%)")
        print(f"  Quit Penalty:      ₹{costs['quit_penalty']:.2f} ({costs['quit_penalty']/total_cost*100:.1f}%)")
        print(f"  Detour Penalty:    ₹{costs['detour_penalty']:.2f} ({costs['detour_penalty']/total_cost*100:.1f}%)")
        
        print(f"\n🚙 Driver Statistics:")
        driver_stats = self.metrics['driver_stats']
        for dtype, stats in driver_stats.items():
            avg_pool = stats['passengers'] / stats['trips'] if stats['trips'] > 0 else 0
            print(f"  Type {dtype}: {stats['trips']} trips, {stats['passengers']} passengers (avg {avg_pool:.2f})")
        
        print("\n" + "=" * 60)

def main():
    """Example usage"""
    import sys
    
    if len(sys.argv) > 1:
        metrics_file = sys.argv[1]
    else:
        metrics_file = "metrics.json"
    
    viz = SimulationVisualizer(metrics_file)
    
    # Print summary
    viz.print_summary()
    
    # Generate plots
    print("\nGenerating visualizations...")
    viz.plot_summary_dashboard("dashboard.png")
    print("✓ Saved dashboard.png")
    
    viz.plot_pool_utilization("pool_utilization.png")
    print("✓ Saved pool_utilization.png")
    
    viz.plot_cost_breakdown("cost_breakdown.png")
    print("✓ Saved cost_breakdown.png")
    
    viz.plot_driver_performance("driver_performance.png")
    print("✓ Saved driver_performance.png")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
