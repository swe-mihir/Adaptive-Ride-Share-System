const { useState, useEffect, useRef } = React;

// Main App Component
function App() {
    const [viewMode, setViewMode] = useState('comparison'); // 'fcfs', 'optimal', 'comparison'
    const [settings, setSettings] = useState({
        detourMax: 1.5,
        clusterRadius: 1.0,
        capacity: 3
    });
    const [metrics, setMetrics] = useState({
        fcfs: null,
        optimal: null
    });
    const [isRunning, setIsRunning] = useState(false);
    const [socket, setSocket] = useState(null);
    
    // Initialize WebSocket connection
    useEffect(() => {
        const newSocket = io('http://localhost:5001');
        
        newSocket.on('connect', () => {
            console.log('Connected to server');
        });
        
        newSocket.on('fcfs_event', (event) => {
            console.log('FCFS Event:', event);
            // Handle FCFS events
        });
        
        newSocket.on('optimal_event', (event) => {
            console.log('Optimal Event:', event);
            // Handle Optimal events
        });
        
        newSocket.on('simulation_complete', (data) => {
            console.log('Simulation complete:', data);
            setIsRunning(false);
        });
        
        setSocket(newSocket);
        
        return () => newSocket.close();
    }, []);
    
    // Fetch metrics periodically
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const response = await fetch('http://localhost:5001/api/metrics');
                const data = await response.json();
                setMetrics(data);
            } catch (error) {
                console.error('Error fetching metrics:', error);
            }
        }, 1000);
        
        return () => clearInterval(interval);
    }, []);
    
    const handleStartSimulation = () => {
        if (socket) {
            socket.emit('start_simulation', { config: settings });
            setIsRunning(true);
        }
    };
    
    const handlePauseSimulation = () => {
        if (socket) {
            socket.emit('pause_simulation');
            setIsRunning(false);
        }
    };
    
    const handleResetSimulation = () => {
        if (socket) {
            socket.emit('reset_simulation');
            setIsRunning(false);
            setMetrics({ fcfs: null, optimal: null });
        }
    };
    
    return (
        <div className="min-h-screen bg-slate-900 text-slate-100">
            {/* Header */}
            <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
                <h1 className="text-2xl font-bold text-white">Adaptive Ride-Sharing System</h1>
                
                {/* View Mode Selector */}
                <div className="mt-4 flex gap-2">
                    <select 
                        value={viewMode}
                        onChange={(e) => setViewMode(e.target.value)}
                        className="setting-input"
                    >
                        <option value="comparison">Split View: FCFS vs Optimal</option>
                        <option value="fcfs">FCFS Carpooling Only</option>
                        <option value="optimal">Optimal Carpooling Only</option>
                    </select>
                </div>
            </header>
            
            {/* Main Content */}
            <div className="flex h-[calc(100vh-120px)]">
                {/* Left Sidebar - Settings */}
                <aside className="w-64 bg-slate-800 border-r border-slate-700 p-4 overflow-y-auto">
                    <h2 className="text-lg font-semibold mb-4">Settings</h2>
                    
                    {/* Distance Settings */}
                    <div className="metric-card">
                        <label className="metric-label">Max Detour</label>
                        <input 
                            type="number"
                            step="0.1"
                            value={settings.detourMax}
                            onChange={(e) => setSettings({...settings, detourMax: parseFloat(e.target.value)})}
                            className="setting-input mt-2"
                        />
                        <p className="text-xs text-slate-400 mt-1">Maximum detour ratio (e.g., 1.5 = 50% longer)</p>
                    </div>
                    
                    <div className="metric-card">
                        <label className="metric-label">Cluster Radius (km)</label>
                        <input 
                            type="number"
                            step="0.1"
                            value={settings.clusterRadius}
                            onChange={(e) => setSettings({...settings, clusterRadius: parseFloat(e.target.value)})}
                            className="setting-input mt-2"
                        />
                        <p className="text-xs text-slate-400 mt-1">Destination clustering radius</p>
                    </div>
                    
                    {/* Capacity Settings */}
                    <div className="metric-card">
                        <label className="metric-label">Vehicle Capacity</label>
                        <div className="flex gap-2 mt-2">
                            {[2, 3, 4].map(cap => (
                                <button
                                    key={cap}
                                    onClick={() => setSettings({...settings, capacity: cap})}
                                    className={`btn flex-1 ${settings.capacity === cap ? 'btn-primary' : 'bg-slate-700'}`}
                                >
                                    {cap}
                                </button>
                            ))}
                        </div>
                    </div>
                    
                    {/* Controls */}
                    <div className="metric-card">
                        <label className="metric-label">Controls</label>
                        <div className="flex flex-col gap-2 mt-2">
                            {!isRunning ? (
                                <button onClick={handleStartSimulation} className="btn btn-primary">
                                    ▶️ Start Simulation
                                </button>
                            ) : (
                                <button onClick={handlePauseSimulation} className="btn bg-yellow-600">
                                    ⏸️ Pause
                                </button>
                            )}
                            <button onClick={handleResetSimulation} className="btn bg-slate-700">
                                🔄 Reset
                            </button>
                        </div>
                    </div>
                </aside>
                
                {/* Center - Maps */}
                <main className="flex-1 p-4">
                    {viewMode === 'comparison' && (
                        <div className="grid grid-cols-2 gap-4 h-full">
                            <MapView title="FCFS Algorithm" algorithm="fcfs" metrics={metrics.fcfs} />
                            <MapView title="Optimal Algorithm" algorithm="optimal" metrics={metrics.optimal} />
                        </div>
                    )}
                    {viewMode === 'fcfs' && (
                        <MapView title="FCFS Carpooling" algorithm="fcfs" metrics={metrics.fcfs} fullscreen />
                    )}
                    {viewMode === 'optimal' && (
                        <MapView title="Optimal Carpooling" algorithm="optimal" metrics={metrics.optimal} fullscreen />
                    )}
                </main>
                
                {/* Right Sidebar - Metrics */}
                <aside className="w-72 bg-slate-800 border-l border-slate-700 p-4 overflow-y-auto">
                    <h2 className="text-lg font-semibold mb-4">Live Metrics</h2>
                    
                    {viewMode === 'comparison' ? (
                        <ComparisonMetrics fcfs={metrics.fcfs} optimal={metrics.optimal} />
                    ) : (
                        <SingleMetrics data={metrics[viewMode]} algorithm={viewMode} />
                    )}
                </aside>
            </div>
        </div>
    );
}

// Map View Component
function MapView({ title, algorithm, metrics, fullscreen }) {
    const mapRef = useRef(null);
    const mapInstanceRef = useRef(null);
    
    useEffect(() => {
        if (!mapInstanceRef.current && mapRef.current) {
            // Initialize map
            const map = L.map(mapRef.current).setView([19.0760, 72.8777], 7);
            
            // Add OpenStreetMap tiles
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            
            mapInstanceRef.current = map;
        }
        
        return () => {
            if (mapInstanceRef.current) {
                mapInstanceRef.current.remove();
                mapInstanceRef.current = null;
            }
        };
    }, []);
    
    // Update markers based on metrics
    useEffect(() => {
        if (mapInstanceRef.current && metrics) {
            // Clear existing markers
            mapInstanceRef.current.eachLayer((layer) => {
                if (layer instanceof L.Marker) {
                    mapInstanceRef.current.removeLayer(layer);
                }
            });
            
            // Add request markers (blue dots)
            if (metrics.live) {
                // This will be populated from WebSocket events
            }
        }
    }, [metrics]);
    
    return (
        <div className={`flex flex-col ${fullscreen ? 'h-full' : 'h-full'}`}>
            <div className="bg-slate-800 px-4 py-2 rounded-t-lg border border-slate-700">
                <h3 className="font-semibold">{title}</h3>
            </div>
            <div ref={mapRef} className="map-container flex-1"></div>
        </div>
    );
}

// Comparison Metrics Component
function ComparisonMetrics({ fcfs, optimal }) {
    if (!fcfs || !optimal) {
        return <div className="text-slate-400 text-center">Waiting for simulation...</div>;
    }
    
    return (
        <div>
            {/* Active Stats */}
            <div className="metric-card">
                <div className="metric-label">Active Requests</div>
                <div className="flex justify-between mt-2">
                    <div>
                        <div className="text-sm text-slate-400">FCFS</div>
                        <div className="text-xl font-bold">{fcfs.live?.active_requests || 0}</div>
                    </div>
                    <div>
                        <div className="text-sm text-slate-400">Optimal</div>
                        <div className="text-xl font-bold">{optimal.live?.active_requests || 0}</div>
                    </div>
                </div>
            </div>
            
            <div className="metric-card">
                <div className="metric-label">Available Drivers</div>
                <div className="flex justify-between mt-2">
                    <div>
                        <div className="text-sm text-slate-400">FCFS</div>
                        <div className="text-xl font-bold">
                            {fcfs.live?.available_drivers ? 
                                Object.values(fcfs.live.available_drivers).reduce((a,b) => a+b, 0) : 0}
                        </div>
                    </div>
                    <div>
                        <div className="text-sm text-slate-400">Optimal</div>
                        <div className="text-xl font-bold">
                            {optimal.live?.available_drivers ? 
                                Object.values(optimal.live.available_drivers).reduce((a,b) => a+b, 0) : 0}
                        </div>
                    </div>
                </div>
            </div>
            
            {/* Cost Comparison */}
            <div className="metric-card">
                <div className="metric-label">Total Cost</div>
                <div className="flex justify-between mt-2">
                    <div>
                        <div className="text-sm text-slate-400">FCFS</div>
                        <div className="text-xl font-bold">₹{fcfs.cumulative?.total_cost?.toFixed(0) || 0}</div>
                    </div>
                    <div>
                        <div className="text-sm text-slate-400">Optimal</div>
                        <div className="text-xl font-bold text-green-400">
                            ₹{optimal.cumulative?.total_cost?.toFixed(0) || 0}
                        </div>
                    </div>
                </div>
            </div>
            
            {/* Match Rate */}
            <div className="metric-card">
                <div className="metric-label">Match Rate</div>
                <div className="flex justify-between mt-2">
                    <div>
                        <div className="text-sm text-slate-400">FCFS</div>
                        <div className="text-xl font-bold">
                            {((fcfs.cumulative?.match_rate || 0) * 100).toFixed(1)}%
                        </div>
                    </div>
                    <div>
                        <div className="text-sm text-slate-400">Optimal</div>
                        <div className="text-xl font-bold text-green-400">
                            {((optimal.cumulative?.match_rate || 0) * 100).toFixed(1)}%
                        </div>
                    </div>
                </div>
            </div>
            
            {/* Pool Size */}
            <div className="metric-card">
                <div className="metric-label">Avg Pool Size</div>
                <div className="flex justify-between mt-2">
                    <div>
                        <div className="text-sm text-slate-400">FCFS</div>
                        <div className="text-xl font-bold">
                            {(fcfs.carpooling?.avg_pool_size || 0).toFixed(2)}
                        </div>
                    </div>
                    <div>
                        <div className="text-sm text-slate-400">Optimal</div>
                        <div className="text-xl font-bold text-green-400">
                            {(optimal.carpooling?.avg_pool_size || 0).toFixed(2)}
                        </div>
                    </div>
                </div>
            </div>
            
            {/* Time */}
            <div className="metric-card">
                <div className="metric-label">Simulation Time</div>
                <div className="metric-value">
                    {Math.floor((fcfs.simulation_time || 0) / 60)}:{String(Math.floor((fcfs.simulation_time || 0) % 60)).padStart(2, '0')}
                </div>
            </div>
        </div>
    );
}

// Single Metrics Component
function SingleMetrics({ data, algorithm }) {
    if (!data) {
        return <div className="text-slate-400 text-center">Waiting for simulation...</div>;
    }
    
    return (
        <div>
            <div className="metric-card">
                <div className="metric-label">Active Requests</div>
                <div className="metric-value">{data.live?.active_requests || 0}</div>
            </div>
            
            <div className="metric-card">
                <div className="metric-label">Available Drivers</div>
                <div className="metric-value">
                    {data.live?.available_drivers ? 
                        Object.values(data.live.available_drivers).reduce((a,b) => a+b, 0) : 0}
                </div>
            </div>
            
            <div className="metric-card">
                <div className="metric-label">Total Cost</div>
                <div className="metric-value">₹{data.cumulative?.total_cost?.toFixed(0) || 0}</div>
            </div>
            
            <div className="metric-card">
                <div className="metric-label">Match Rate</div>
                <div className="metric-value">
                    {((data.cumulative?.match_rate || 0) * 100).toFixed(1)}%
                </div>
            </div>
        </div>
    );
}

// Render App
ReactDOM.render(<App />, document.getElementById('root'));