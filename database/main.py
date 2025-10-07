"""
Script to initialize database tables for simulation metrics
Run this once before starting the server
"""
import psycopg2
from config import config

def init_database():
    """Create all necessary tables"""

    # SQL commands to create tables
    commands = [
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id SERIAL PRIMARY KEY,
            config_json JSONB NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            duration_seconds INTEGER,
            status VARCHAR(20) DEFAULT 'running'
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS metrics_snapshots (
            id SERIAL PRIMARY KEY,
            run_id INTEGER REFERENCES simulation_runs(id) ON DELETE CASCADE,
            simulation_type VARCHAR(20) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            simulation_time FLOAT NOT NULL,
            active_drivers INTEGER,
            active_requests INTEGER,
            active_trips INTEGER,
            total_passengers INTEGER,
            total_requests INTEGER,
            completed_trips INTEGER,
            cancelled_requests INTEGER,
            total_revenue FLOAT,
            total_waiting_time FLOAT,
            total_trip_time FLOAT,
            avg_utilization FLOAT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS entity_locations (
            id SERIAL PRIMARY KEY,
            run_id INTEGER REFERENCES simulation_runs(id) ON DELETE CASCADE,
            simulation_type VARCHAR(20) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            simulation_time FLOAT NOT NULL,
            entity_type VARCHAR(20) NOT NULL,
            entity_id VARCHAR(50) NOT NULL,
            lat FLOAT,
            lon FLOAT,
            status VARCHAR(20),
            metadata JSONB
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS trips (
            id SERIAL PRIMARY KEY,
            run_id INTEGER REFERENCES simulation_runs(id) ON DELETE CASCADE,
            simulation_type VARCHAR(20) NOT NULL,
            trip_id VARCHAR(50) NOT NULL,
            driver_id VARCHAR(50) NOT NULL,
            passenger_count INTEGER,
            origin_lat FLOAT,
            origin_lon FLOAT,
            dest_lat FLOAT,
            dest_lon FLOAT,
            request_time FLOAT,
            pickup_time FLOAT,
            dropoff_time FLOAT,
            waiting_time FLOAT,
            trip_duration FLOAT,
            detour_time FLOAT,
            revenue FLOAT,
            completed BOOLEAN DEFAULT FALSE
        )
        """,
        # Create indexes
        "CREATE INDEX IF NOT EXISTS idx_metrics_run_id ON metrics_snapshots(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_metrics_sim_type ON metrics_snapshots(simulation_type)",
        "CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics_snapshots(simulation_time)",
        "CREATE INDEX IF NOT EXISTS idx_entities_run_id ON entity_locations(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_entities_sim_type ON entity_locations(simulation_type)",
        "CREATE INDEX IF NOT EXISTS idx_entities_time ON entity_locations(simulation_time)",
        "CREATE INDEX IF NOT EXISTS idx_trips_run_id ON trips(run_id)",
        "CREATE INDEX IF NOT EXISTS idx_trips_sim_type ON trips(simulation_type)"
    ]

    connection = None
    try:
        # Connect to database
        params = config()
        print("Connecting to PostgreSQL database...")
        connection = psycopg2.connect(**params)
        cursor = connection.cursor()

        # Get database version
        cursor.execute("SELECT version()")
        db_version = cursor.fetchone()
        print(f"PostgreSQL version: {db_version[0]}\n")

        # Execute commands
        print("Creating tables...")
        for command in commands:
            cursor.execute(command)
            # Print progress based on command type
            if "CREATE TABLE" in command:
                table_name = command.split("CREATE TABLE IF NOT EXISTS")[1].split("(")[0].strip()
                print(f"✓ Created table: {table_name}")
            elif "CREATE INDEX" in command:
                index_name = command.split("CREATE INDEX IF NOT EXISTS")[1].split("ON")[0].strip()
                print(f"✓ Created index: {index_name}")

        # Commit changes
        connection.commit()
        cursor.close()

        print("\n" + "="*60)
        print("✓ Database initialized successfully!")
        print("="*60)
        print("\nTables created:")
        print("  • simulation_runs")
        print("  • metrics_snapshots")
        print("  • entity_locations")
        print("  • trips")
        print("\nYou can now start the server.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"\n✗ Error: {error}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    init_database()