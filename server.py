# """
# WebSocket server with entity location tracking for map visualization.
# """
#
# from flask import Flask, jsonify
# from flask_socketio import SocketIO, emit
# from flask_cors import CORS
# import threading
# import yaml
# import time
#
# app = Flask(__name__)
# CORS(app)
# socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
#
# simulator_fcfs = None
# simulator_optimal = None
# is_running = False
# current_config = None
#
# @app.route('/api/metrics')
# def get_metrics():
#     """Get metrics AND entity locations for map rendering"""
#     if not simulator_fcfs or not simulator_optimal:
#         return jsonify({
#             'fcfs': {'live': {}, 'cumulative': {}, 'entities': {}},
#             'optimal': {'live': {}, 'cumulative': {}, 'entities': {}}
#         })
#
#     try:
#         # Get metrics
#         fcfs_metrics = simulator_fcfs.metrics.get_current_metrics(simulator_fcfs.time)
#         optimal_metrics = simulator_optimal.metrics.get_current_metrics(simulator_optimal.time)
#
#         # Add entity locations for map
#         fcfs_metrics['entities'] = get_entities(simulator_fcfs)
#         optimal_metrics['entities'] = get_entities(simulator_optimal)
#
#         return jsonify({
#             'fcfs': fcfs_metrics,
#             'optimal': optimal_metrics
#         })
#     except Exception as e:
#         print(f"Error getting metrics: {e}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({
#             'fcfs': {'live': {}, 'cumulative': {}, 'entities': {}},
#             'optimal': {'live': {}, 'cumulative': {}, 'entities': {}}
#         })
#
# def get_entities(sim):
#     """Extract entity locations for map rendering"""
#     entities = {
#         'drivers': [],
#         'requests': [],
#         'trips': []
#     }
#
#     # Available drivers
#     for driver in sim.available_drivers:
#         entities['drivers'].append({
#             'id': driver.id,
#             'lat': driver.location.lat,
#             'lon': driver.location.lon,
#             'status': 'available',
#             'type': driver.type.name
#         })
#
#     # Active requests (waiting)
#     for request in sim.active_requests:
#         entities['requests'].append({
#             'id': request.id,
#             'origin_lat': request.origin.lat,
#             'origin_lon': request.origin.lon,
#             'dest_lat': request.destination.lat,
#             'dest_lon': request.destination.lon,
#             'status': 'waiting'
#         })
#
#     # Active trips
#     for trip in sim.active_trips:
#         route_coords = [[loc.lat, loc.lon] for loc in trip.route]
#         entities['trips'].append({
#             'id': trip.id,
#             'driver_id': trip.driver.id,
#             'driver_lat': trip.driver.location.lat,
#             'driver_lon': trip.driver.location.lon,
#             'passenger_count': len(trip.passengers),
#             'route': route_coords,
#             'destination': [trip.destination.lat, trip.destination.lon]
#         })
#
#     return entities
#
# @socketio.on('connect')
# def handle_connect():
#     print('Client connected')
#     if is_running:
#         emit('simulation_running', {'status': 'running'})
#
# @socketio.on('start_simulation')
# def handle_start(data):
#     global is_running, current_config
#
#     if is_running:
#         print("Simulation already running")
#         return
#
#     print("Starting simulation...")
#     config = load_config()
#
#     # Apply settings from frontend
#     if data and 'config' in data:
#         settings = data['config']
#         if 'detourMax' in settings:
#             config['carpooling']['detour_max'] = settings['detourMax']
#         if 'clusterRadius' in settings:
#             config['carpooling']['destination_cluster_radius_km'] = settings['clusterRadius']
#         if 'capacity' in settings:
#             config['carpooling']['capacity'] = settings['capacity']
#
#     current_config = config
#     is_running = True
#
#     thread = threading.Thread(target=run_simulation, args=(config,))
#     thread.daemon = True
#     thread.start()
#
#     emit('simulation_started', {'status': 'running'})
#
# @socketio.on('pause_simulation')
# def handle_pause():
#     global is_running
#     is_running = False
#     emit('simulation_paused')
#
# @socketio.on('reset_simulation')
# def handle_reset():
#     global is_running, simulator_fcfs, simulator_optimal
#     is_running = False
#     simulator_fcfs = None
#     simulator_optimal = None
#     emit('simulation_reset')
#
# def load_config():
#     try:
#         with open('config_yaml.txt', 'r') as f:
#             return yaml.safe_load(f)
#     except FileNotFoundError:
#         print("Warning: config_yaml.txt not found")
#         return {
#             'simulation': {'duration': 300, 'initial_drivers': 25, 'random_seed': 42},
#             'carpooling': {'capacity': 3, 'detour_max': 1.5, 'destination_cluster_radius_km': 1.0},
#             'region': {'bounds': {'lat_min': 15.6, 'lat_max': 22.1, 'lon_min': 72.6, 'lon_max': 80.9}},
#             'osrm': {'server_url': 'http://127.0.0.1:5000', 'cache_size': 10000},
#             'costs': {'waiting_cost_per_sec': 0.5, 'quit_penalty': 100, 'detour_penalty_per_sec': 2},
#             'driver_types': [
#                 {'id': 1, 'name': 'Fast', 'base_cost': 20, 'arrival_rate': 0.1, 'speed_multiplier': 1.2},
#                 {'id': 2, 'name': 'Normal', 'base_cost': 15, 'arrival_rate': 0.15, 'speed_multiplier': 1.0},
#                 {'id': 3, 'name': 'Economy', 'base_cost': 10, 'arrival_rate': 0.2, 'speed_multiplier': 0.9}
#             ],
#             'requests': {'arrival_rate': 0.05, 'weibull_shape': 2.0, 'weibull_scale': 300},
#             'metrics': {'update_interval': 10, 'output_file': 'metrics.json'}
#         }
#
# def run_simulation(config):
#     global simulator_fcfs, simulator_optimal, is_running
#
#     print("\nInitializing dual simulation...")
#
#     try:
#         from simulation.dual_simulator import DualSimulator
#
#         dual_sim = DualSimulator(config)
#         simulator_fcfs = dual_sim.sim_fcfs
#         simulator_optimal = dual_sim.sim_optimal
#
#         socketio.emit('simulation_initialized', {'status': 'ready'})
#
#         print("Running FCFS simulation...")
#         # Just run the whole simulation - it will complete quickly
#         duration = config['simulation']['duration']
#         dual_sim.run(duration)
#
#         is_running = False
#         print("\nSimulation complete")
#
#         socketio.emit('simulation_complete', {
#             'fcfs': simulator_fcfs.get_summary(),
#             'optimal': simulator_optimal.get_summary()
#         })
#
#     except Exception as e:
#         print(f"Error: {e}")
#         import traceback
#         traceback.print_exc()
#         is_running = False
#         socketio.emit('simulation_error', {'error': str(e)})
#
# if __name__ == '__main__':
#     print("="*60)
#     print("WebSocket Server")
#     print("="*60)
#     print("Starting on port 5001...")
#     print("Connect frontend to: http://localhost:5001")
#     print("="*60)
#     socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)


"""
WebSocket server with entity location tracking and database integration.
"""

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
import yaml
import time
from database.db_manager import DatabaseManager

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

simulator_fcfs = None
simulator_optimal = None
is_running = False
current_config = None
db_manager = None
current_run_id = None


def init_database():
    """Initialize database connection"""
    global db_manager
    try:
        db_manager = DatabaseManager()
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        print("  Continuing without database...")
        db_manager = None


@app.route('/api/metrics')
def get_metrics():
    """Get metrics AND entity locations for map rendering"""
    if not simulator_fcfs or not simulator_optimal:
        return jsonify({
            'fcfs': {'live': {}, 'cumulative': {}, 'entities': {}},
            'optimal': {'live': {}, 'cumulative': {}, 'entities': {}}
        })

    try:
        # Get metrics
        fcfs_metrics = simulator_fcfs.metrics.get_current_metrics(simulator_fcfs.time)
        optimal_metrics = simulator_optimal.metrics.get_current_metrics(simulator_optimal.time)

        # Add entity locations for map
        fcfs_metrics['entities'] = get_entities(simulator_fcfs)
        optimal_metrics['entities'] = get_entities(simulator_optimal)

        # Save to database if available
        if db_manager and current_run_id:
            try:
                db_manager.save_metrics_snapshot(
                    current_run_id, 'fcfs', fcfs_metrics, simulator_fcfs.time
                )
                db_manager.save_metrics_snapshot(
                    current_run_id, 'optimal', optimal_metrics, simulator_optimal.time
                )
                db_manager.save_entity_locations(
                    current_run_id, 'fcfs', fcfs_metrics['entities'], simulator_fcfs.time
                )
                db_manager.save_entity_locations(
                    current_run_id, 'optimal', optimal_metrics['entities'], simulator_optimal.time
                )
            except Exception as e:
                print(f"Warning: Failed to save to database: {e}")

        return jsonify({
            'fcfs': fcfs_metrics,
            'optimal': optimal_metrics
        })
    except Exception as e:
        print(f"Error getting metrics: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'fcfs': {'live': {}, 'cumulative': {}, 'entities': {}},
            'optimal': {'live': {}, 'cumulative': {}, 'entities': {}}
        })


@app.route('/api/runs')
def get_runs():
    """Get recent simulation runs from database"""
    if not db_manager:
        return jsonify({'error': 'Database not available'}), 503

    try:
        runs = db_manager.get_simulation_runs(limit=20)
        return jsonify({
            'runs': [
                {
                    'id': r[0],
                    'start_time': r[1].isoformat() if r[1] else None,
                    'end_time': r[2].isoformat() if r[2] else None,
                    'duration': r[3],
                    'status': r[4]
                }
                for r in runs
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/runs/<int:run_id>/metrics')
def get_run_metrics(run_id):
    """Get metrics history for a specific run"""
    if not db_manager:
        return jsonify({'error': 'Database not available'}), 503

    sim_type = request.args.get('type')
    try:
        metrics = db_manager.get_metrics_history(run_id, sim_type)
        return jsonify({'metrics': metrics})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_entities(sim):
    """Extract entity locations for map rendering"""
    entities = {
        'drivers': [],
        'requests': [],
        'trips': []
    }

    # Available drivers
    for driver in sim.available_drivers:
        entities['drivers'].append({
            'id': driver.id,
            'lat': driver.location.lat,
            'lon': driver.location.lon,
            'status': 'available',
            'type': driver.type.name
        })

    # Active requests (waiting)
    for request in sim.active_requests:
        entities['requests'].append({
            'id': request.id,
            'origin_lat': request.origin.lat,
            'origin_lon': request.origin.lon,
            'dest_lat': request.destination.lat,
            'dest_lon': request.destination.lon,
            'status': 'waiting'
        })

    # Active trips
    for trip in sim.active_trips:
        route_coords = [[loc.lat, loc.lon] for loc in trip.route]
        entities['trips'].append({
            'id': trip.id,
            'driver_id': trip.driver.id,
            'driver_lat': trip.driver.location.lat,
            'driver_lon': trip.driver.location.lon,
            'passenger_count': len(trip.passengers),
            'route': route_coords,
            'destination': [trip.destination.lat, trip.destination.lon]
        })

    return entities


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    if is_running:
        emit('simulation_running', {'status': 'running'})


@socketio.on('start_simulation')
def handle_start(data):
    global is_running, current_config, current_run_id

    if is_running:
        print("Simulation already running")
        return

    print("Starting simulation...")
    config = load_config()

    # Apply settings from frontend
    if data and 'config' in data:
        settings = data['config']
        if 'detourMax' in settings:
            config['carpooling']['detour_max'] = settings['detourMax']
        if 'clusterRadius' in settings:
            config['carpooling']['destination_cluster_radius_km'] = settings['clusterRadius']
        if 'capacity' in settings:
            config['carpooling']['capacity'] = settings['capacity']

    current_config = config
    is_running = True

    # Create database record for this simulation run
    if db_manager:
        try:
            current_run_id = db_manager.create_simulation_run(config)
            print(f"✓ Simulation run #{current_run_id} created in database")
        except Exception as e:
            print(f"✗ Failed to create database record: {e}")
            current_run_id = None

    thread = threading.Thread(target=run_simulation, args=(config,))
    thread.daemon = True
    thread.start()

    emit('simulation_started', {'status': 'running', 'run_id': current_run_id})


@socketio.on('pause_simulation')
def handle_pause():
    global is_running
    is_running = False
    emit('simulation_paused')


@socketio.on('reset_simulation')
def handle_reset():
    global is_running, simulator_fcfs, simulator_optimal, current_run_id

    # Update database if run exists
    if db_manager and current_run_id:
        try:
            db_manager.update_simulation_run(current_run_id, status='reset')
        except Exception as e:
            print(f"✗ Failed to update database: {e}")

    is_running = False
    simulator_fcfs = None
    simulator_optimal = None
    current_run_id = None
    emit('simulation_reset')


def load_config():
    try:
        with open('config_yaml.txt', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Warning: config_yaml.txt not found")
        return {
            'simulation': {'duration': 300, 'initial_drivers': 25, 'random_seed': 42},
            'carpooling': {'capacity': 3, 'detour_max': 1.5, 'destination_cluster_radius_km': 1.0},
            'region': {'bounds': {'lat_min': 15.6, 'lat_max': 22.1, 'lon_min': 72.6, 'lon_max': 80.9}},
            'osrm': {'server_url': 'http://127.0.0.1:5000', 'cache_size': 10000},
            'costs': {'waiting_cost_per_sec': 0.5, 'quit_penalty': 100, 'detour_penalty_per_sec': 2},
            'driver_types': [
                {'id': 1, 'name': 'Fast', 'base_cost': 20, 'arrival_rate': 0.1, 'speed_multiplier': 1.2},
                {'id': 2, 'name': 'Normal', 'base_cost': 15, 'arrival_rate': 0.15, 'speed_multiplier': 1.0},
                {'id': 3, 'name': 'Economy', 'base_cost': 10, 'arrival_rate': 0.2, 'speed_multiplier': 0.9}
            ],
            'requests': {'arrival_rate': 0.05, 'weibull_shape': 2.0, 'weibull_scale': 300},
            'metrics': {'update_interval': 10, 'output_file': 'metrics.json'}
        }


def save_metrics_periodically(sim_fcfs, sim_optimal, run_id, interval=10):
    """Background thread to save metrics to database periodically"""
    global is_running

    while is_running:
        try:
            if db_manager and run_id:
                # Get current metrics
                fcfs_metrics = sim_fcfs.metrics.get_current_metrics(sim_fcfs.time)
                optimal_metrics = sim_optimal.metrics.get_current_metrics(sim_optimal.time)

                # Get entity locations
                fcfs_entities = get_entities(sim_fcfs)
                optimal_entities = get_entities(sim_optimal)

                # Save to database
                db_manager.save_metrics_snapshot(run_id, 'fcfs', fcfs_metrics, sim_fcfs.time)
                db_manager.save_metrics_snapshot(run_id, 'optimal', optimal_metrics, sim_optimal.time)
                db_manager.save_entity_locations(run_id, 'fcfs', fcfs_entities, sim_fcfs.time)
                db_manager.save_entity_locations(run_id, 'optimal', optimal_entities, sim_optimal.time)

                print(f"✓ Saved metrics at t={sim_fcfs.time:.1f}s")
        except Exception as e:
            print(f"✗ Error saving periodic metrics: {e}")

        time.sleep(interval)


def run_simulation(config):
    global simulator_fcfs, simulator_optimal, is_running, current_run_id

    print("\nInitializing dual simulation...")

    try:
        from simulation.dual_simulator import DualSimulator

        dual_sim = DualSimulator(config)
        simulator_fcfs = dual_sim.sim_fcfs
        simulator_optimal = dual_sim.sim_optimal

        socketio.emit('simulation_initialized', {'status': 'ready'})

        # Start background metrics saver if database is available
        metrics_thread = None
        if db_manager and current_run_id:
            metrics_interval = config.get('metrics', {}).get('update_interval', 10)
            metrics_thread = threading.Thread(
                target=save_metrics_periodically,
                args=(simulator_fcfs, simulator_optimal, current_run_id, metrics_interval)
            )
            metrics_thread.daemon = True
            metrics_thread.start()
            print(f"✓ Started background metrics saver (interval: {metrics_interval}s)")

        print("Running simulation...")
        duration = config['simulation']['duration']
        dual_sim.run(duration)

        is_running = False
        print("\nSimulation complete")

        # Update database with completion status
        if db_manager and current_run_id:
            try:
                db_manager.update_simulation_run(
                    current_run_id,
                    status='completed',
                    duration=duration
                )
                print(f"✓ Simulation run #{current_run_id} marked as completed")
            except Exception as e:
                print(f"✗ Failed to update completion status: {e}")

        summary = {
            'fcfs': simulator_fcfs.get_summary(),
            'optimal': simulator_optimal.get_summary()
        }

        socketio.emit('simulation_complete', {
            'run_id': current_run_id,
            **summary
        })

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

        # Mark as failed in database
        if db_manager and current_run_id:
            try:
                db_manager.update_simulation_run(current_run_id, status='failed')
            except:
                pass

        is_running = False
        socketio.emit('simulation_error', {'error': str(e)})


if __name__ == '__main__':
    print("=" * 60)
    print("WebSocket Server with Database Integration")
    print("=" * 60)

    # Initialize database
    init_database()

    print("Starting on port 5001...")
    print("Connect frontend to: http://localhost:5001")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)