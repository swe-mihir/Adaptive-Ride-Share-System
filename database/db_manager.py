"""
Database manager for storing simulation metrics
"""
import psycopg2
from psycopg2.extras import Json
from database.config import config
import json
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.current_run_id = None
        self.connect()
    
    def connect(self):
        """Establish database connection"""
        try:
            params = config()
            self.connection = psycopg2.connect(**params)
            print("✓ Database connected successfully")
        except (Exception, psycopg2.DatabaseError) as error:
            print(f"✗ Database connection error: {error}")
            raise
    
    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("Database connection closed")
    
    def create_simulation_run(self, config_dict):
        """Create a new simulation run record"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT INTO simulation_runs (config_json, status)
                VALUES (%s, %s)
                RETURNING id
                """,
                (Json(config_dict), 'running')
            )
            run_id = cursor.fetchone()[0]
            self.connection.commit()
            cursor.close()
            self.current_run_id = run_id
            print(f"✓ Created simulation run #{run_id}")
            return run_id
        except Exception as e:
            print(f"✗ Error creating simulation run: {e}")
            self.connection.rollback()
            raise
    
    def update_simulation_run(self, run_id, status='completed', duration=None):
        """Update simulation run status"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                UPDATE simulation_runs
                SET status = %s,
                    end_time = CURRENT_TIMESTAMP,
                    duration_seconds = %s
                WHERE id = %s
                """,
                (status, duration, run_id)
            )
            self.connection.commit()
            cursor.close()
            print(f"✓ Updated simulation run #{run_id} - Status: {status}")
        except Exception as e:
            print(f"✗ Error updating simulation run: {e}")
            self.connection.rollback()
    
    def save_metrics_snapshot(self, run_id, sim_type, metrics, sim_time):
        """Save a metrics snapshot"""
        try:
            cursor = self.connection.cursor()
            
            live = metrics.get('live', {})
            cumulative = metrics.get('cumulative', {})
            
            cursor.execute(
                """
                INSERT INTO metrics_snapshots (
                    run_id, simulation_type, simulation_time,
                    active_drivers, active_requests, active_trips, total_passengers,
                    total_requests, completed_trips, cancelled_requests,
                    total_revenue, total_waiting_time, total_trip_time, avg_utilization
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id, sim_type, sim_time,
                    live.get('active_drivers', 0),
                    live.get('active_requests', 0),
                    live.get('active_trips', 0),
                    live.get('total_passengers', 0),
                    cumulative.get('total_requests', 0),
                    cumulative.get('completed_trips', 0),
                    cumulative.get('cancelled_requests', 0),
                    cumulative.get('total_revenue', 0.0),
                    cumulative.get('total_waiting_time', 0.0),
                    cumulative.get('total_trip_time', 0.0),
                    cumulative.get('avg_utilization', 0.0)
                )
            )
            self.connection.commit()
            cursor.close()
        except Exception as e:
            print(f"✗ Error saving metrics snapshot: {e}")
            self.connection.rollback()
    
    def save_entity_locations(self, run_id, sim_type, entities, sim_time):
        """Save entity locations for map visualization"""
        try:
            cursor = self.connection.cursor()
            
            # Save drivers
            for driver in entities.get('drivers', []):
                cursor.execute(
                    """
                    INSERT INTO entity_locations (
                        run_id, simulation_type, simulation_time,
                        entity_type, entity_id, lat, lon, status, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id, sim_type, sim_time,
                        'driver', driver['id'],
                        driver['lat'], driver['lon'],
                        driver['status'], Json({'type': driver['type']})
                    )
                )
            
            # Save requests
            for request in entities.get('requests', []):
                cursor.execute(
                    """
                    INSERT INTO entity_locations (
                        run_id, simulation_type, simulation_time,
                        entity_type, entity_id, lat, lon, status, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id, sim_type, sim_time,
                        'request', request['id'],
                        request['origin_lat'], request['origin_lon'],
                        request['status'],
                        Json({
                            'dest_lat': request['dest_lat'],
                            'dest_lon': request['dest_lon']
                        })
                    )
                )
            
            # Save trips
            for trip in entities.get('trips', []):
                cursor.execute(
                    """
                    INSERT INTO entity_locations (
                        run_id, simulation_type, simulation_time,
                        entity_type, entity_id, lat, lon, status, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id, sim_type, sim_time,
                        'trip', trip['id'],
                        trip['driver_lat'], trip['driver_lon'],
                        'active',
                        Json({
                            'driver_id': trip['driver_id'],
                            'passenger_count': trip['passenger_count'],
                            'route': trip['route'],
                            'destination': trip['destination']
                        })
                    )
                )
            
            self.connection.commit()
            cursor.close()
        except Exception as e:
            print(f"✗ Error saving entity locations: {e}")
            self.connection.rollback()
    
    def save_trip(self, run_id, sim_type, trip_data):
        """Save completed trip details"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                INSERT INTO trips (
                    run_id, simulation_type, trip_id, driver_id,
                    passenger_count, origin_lat, origin_lon, dest_lat, dest_lon,
                    request_time, pickup_time, dropoff_time,
                    waiting_time, trip_duration, detour_time, revenue, completed
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id, sim_type,
                    trip_data['trip_id'], trip_data['driver_id'],
                    trip_data['passenger_count'],
                    trip_data['origin_lat'], trip_data['origin_lon'],
                    trip_data['dest_lat'], trip_data['dest_lon'],
                    trip_data['request_time'], trip_data['pickup_time'],
                    trip_data['dropoff_time'],
                    trip_data['waiting_time'], trip_data['trip_duration'],
                    trip_data['detour_time'], trip_data['revenue'],
                    trip_data['completed']
                )
            )
            self.connection.commit()
            cursor.close()
        except Exception as e:
            print(f"✗ Error saving trip: {e}")
            self.connection.rollback()
    
    def get_simulation_runs(self, limit=10):
        """Get recent simulation runs"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                """
                SELECT id, start_time, end_time, duration_seconds, status
                FROM simulation_runs
                ORDER BY start_time DESC
                LIMIT %s
                """,
                (limit,)
            )
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception as e:
            print(f"✗ Error fetching simulation runs: {e}")
            return []
    
    def get_metrics_history(self, run_id, sim_type=None):
        """Get metrics history for a simulation run"""
        try:
            cursor = self.connection.cursor()
            if sim_type:
                cursor.execute(
                    """
                    SELECT * FROM metrics_snapshots
                    WHERE run_id = %s AND simulation_type = %s
                    ORDER BY simulation_time
                    """,
                    (run_id, sim_type)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM metrics_snapshots
                    WHERE run_id = %s
                    ORDER BY simulation_time
                    """,
                    (run_id,)
                )
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception as e:
            print(f"✗ Error fetching metrics history: {e}")
            return []