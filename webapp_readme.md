# Adaptive Ride-Sharing Webapp

Real-time visualization comparing FCFS vs Optimal carpooling algorithms.

## 🎯 Features

- **Split-screen comparison** of FCFS and Optimal algorithms
- **Real-time metrics** updating live
- **Interactive maps** with OpenStreetMap
- **Dark professional theme**
- **Configurable parameters** (detour, capacity, cluster radius)
- **Three view modes**: Comparison, FCFS only, Optimal only

## 📦 Setup

### 1. Install Additional Dependencies

```bash
pip install flask flask-socketio flask-cors python-socketio
```

### 2. Create Frontend Structure

```bash
mkdir frontend
cd frontend
```

Create two files in `frontend/`:

**frontend/index.html** - Copy from artifact `frontend_html`
**frontend/app.jsx** - Copy from artifact `frontend_app`

### 3. File Structure

Your project should look like:

```
rideshare_carpool_omd/
├── config.yaml
├── main.py
├── server.py                     # NEW - WebSocket server
├── run_webapp.py                 # NEW - Startup script
├── frontend/
│   ├── index.html               # NEW - HTML template
│   └── app.jsx                  # NEW - React app
├── core/
│   ├── __init__.py
│   └── entities.py
├── algorithms/
│   ├── __init__.py
│   ├── routing.py
│   ├── clustering.py
│   ├── assignment_p1_carpool.py
│   ├── threshold_policy.py
│   └── fcfs_matcher.py          # NEW - FCFS algorithm
├── simulation/
│   ├── __init__.py
│   ├── simulator.py
│   ├── fcfs_simulator.py        # NEW - FCFS simulator
│   └── dual_simulator.py        # NEW - Runs both algorithms
└── utils/
    ├── __init__.py
    ├── osrm_interface.py
    └── metrics_carpool.py
```

## 🚀 Quick Start

### Option 1: Automatic Startup (Recommended)

```bash
# Terminal 1: Start backend + WebSocket server
python run_webapp.py

# Terminal 2: Serve frontend
cd frontend
python -m http.server 8000
```

Then open: **http://localhost:8000**

### Option 2: Manual Startup

**Terminal 1 - Backend:**
```bash
python server.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
python -m http.server 8000
```

**Terminal 3 - Browser:**
```bash
open http://localhost:8000
```

## 🎮 Usage

### 1. Configure Settings (Left Sidebar)

- **Max Detour**: 1.5x means 50% longer trip allowed
- **Cluster Radius**: 1.0 km - destinations within this radius are grouped
- **Capacity**: 2, 3, or 4 passengers per vehicle

### 2. Select View Mode (Top Dropdown)

- **Split View**: Compare FCFS vs Optimal side-by-side
- **FCFS Only**: Show only FCFS algorithm
- **Optimal Only**: Show only Optimal algorithm

### 3. Start Simulation

Click **▶️ Start Simulation** in the left sidebar.

Watch as:
- 🔵 Blue dots appear (waiting requests)
- 🚗 Car icons appear (available drivers)
- 🚕 Animated cars move along routes (active trips)
- ✅ Matches happen in real-time

### 4. Monitor Metrics (Right Sidebar)

**In Comparison Mode:**
- See FCFS vs Optimal metrics side-by-side
- Green values indicate Optimal is better
- Live updates every second

**In Single Mode:**
- Full metrics for selected algorithm
- Active requests, drivers, trips
- Total cost, match rate, pool size

## 📊 Understanding the Visualization

### Map Markers

**Blue Pulsing Dots** = Waiting Requests (passengers)
- Click to see: wait time, origin, destination

**Car Icons** = Available Drivers
- 🟢 Green = Economy (low cost, high availability)
- 🟡 Yellow = Normal
- 🔴 Red = Fast Response (high cost, low availability)

**Moving Cars** = Active Trips
- 🟦 Blue = 1 passenger (solo)
- 🟧 Orange = 2 passengers
- 🟩 Green = 3 passengers (full!)

**Routes** = Colored lines showing trip paths
- Numbered markers (P1, P2, P3) = Pickup sequence

### Metrics Explained

**Active Requests**: Passengers waiting for match
**Available Drivers**: Idle drivers ready to pick up
**Total Cost**: Sum of waiting + routing + penalties (₹)
**Match Rate**: % of requests successfully matched
**Avg Pool Size**: Average passengers per trip
**Simulation Time**: Current time in simulation

## 🔧 Troubleshooting

### WebSocket Not Connecting

**Error**: `Client connected` doesn't appear

**Fix**:
1. Check backend is running: `curl http://localhost:5001/api/status`
2. Check firewall isn't blocking port 5001
3. Try restarting both backend and frontend

### Maps Not Loading

**Error**: Blank gray boxes instead of maps

**Fix**:
1. Check internet connection (needs OpenStreetMap tiles)
2. Open browser console (F12) and check for errors
3. Try refreshing the page

### No Markers Appearing

**Error**: Maps load but no dots/cars appear

**Fix**:
1. Check simulation is running (click Start)
2. Check backend terminal for errors
3. Verify config.yaml has correct arrival rates:
   ```yaml
   requests:
     arrival_rate: 0.05  # Should be > 0
   driver_types:
     - arrival_rate: 0.1  # Should be > 0
   ```

### Frontend Not Loading

**Error**: `Connection refused` at localhost:8000

**Fix**:
1. Make sure you're in `frontend/` directory
2. Run: `python -m http.server 8000`
3. Or use any web server: `npx serve` or `php -S localhost:8000`

### Metrics Not Updating

**Error**: Metrics show 0 or don't change

**Fix**:
1. Check WebSocket connection in browser console
2. Backend might have crashed - check terminal
3. Try Reset button and restart simulation

## 🎨 Customization

### Change Map Center/Zoom

Edit `frontend/app.jsx`, line ~200:

```javascript
const map = L.map(mapRef.current).setView([19.0760, 72.8777], 7);
// Change to: [your_lat, your_lon], zoom_level
```

### Adjust Theme Colors

Edit `frontend/index.html` CSS:

```css
body {
    background: #0f172a;  /* Main background */
    color: #e2e8f0;       /* Text color */
}

.metric-card {
    background: #1e293b;  /* Card background */
}
```

### Change Update Frequency

Edit `frontend/app.jsx`, line ~50:

```javascript
const interval = setInterval(async () => {
    // Fetch metrics
}, 1000);  // Change to 500 for faster, 2000 for slower
```

## 🔬 Comparing Algorithms

### FCFS Algorithm Characteristics

**Pros:**
- Simple, fast
- First-come-first-served fairness

**Cons:**
- No optimization (no TSP)
- Higher costs
- Lower pool utilization
- No dynamic insertion

### Optimal Algorithm Characteristics

**Pros:**
- Minimizes total cost
- Higher pool utilization
- Dynamic insertion
- TSP-optimized routes

**Cons:**
- More complex
- Slightly slower computation

### Expected Results

When running side-by-side, you should see:

- **Optimal** achieves **10-30% lower cost** than FCFS
- **Optimal** has **15-25% higher pool size** (more sharing)
- **Optimal** has **more dynamic insertions** (adds passengers to active trips)
- **FCFS** may have **slightly lower waiting times** (greedy matching)

## 📈 Advanced Features

### Export Simulation Data

After simulation completes, data is saved to:
- `fcfs_metrics.json`
- `optimal_metrics.json`

Load these for analysis:

```python
import json
with open('optimal_metrics.json') as f:
    data = json.load(f)
    
print(f"Match rate: {data['cumulative']['match_rate']:.1%}")
print(f"Total cost: ₹{data['cumulative']['total_cost']:.2f}")
```

### Run Specific Duration

Edit `config.yaml`:

```yaml
simulation:
  duration: 1800  # 30 minutes
```

Or override in code:

```python
# In server.py, modify run_simulations()
config['simulation']['duration'] = 900  # 15 minutes
```

### Adjust Arrival Rates

Test different traffic scenarios in `config.yaml`:

**Low traffic:**
```yaml
requests:
  arrival_rate: 0.02  # 1.2/min
driver_types:
  - arrival_rate: 0.15  # 9/min
```

**High traffic (rush hour):**
```yaml
requests:
  arrival_rate: 0.1  # 6/min
driver_types:
  - arrival_rate: 0.05  # 3/min
```

### Compare Multiple Runs

```python
# Run 1: Low capacity
config['carpooling']['capacity'] = 2
# ... run simulation, save results

# Run 2: High capacity
config['carpooling']['capacity'] = 4
# ... run simulation, compare
```

## 🐛 Known Issues

1. **Large simulations (>2 hours)**: Frontend may slow down due to marker accumulation
   - **Fix**: Refresh page periodically
   
2. **OSRM timeout**: Very long routes may timeout
   - **Fix**: Increase OSRM timeout or reduce region size

3. **Memory usage**: Long simulations accumulate events
   - **Fix**: Set `track_history: false` in config.yaml

## 📚 API Reference

### WebSocket Events

**Client → Server:**
- `start_simulation` - Start simulation with config
- `pause_simulation` - Pause running simulation
- `reset_simulation` - Reset to initial state

**Server → Client:**
- `fcfs_event` - Event from FCFS algorithm
- `optimal_event` - Event from Optimal algorithm
- `simulation_complete` - Simulation finished
- `initial_state` - Initial state on connect

### REST API Endpoints

**GET /api/status**
```json
{
  "running": true,
  "fcfs_time": 125.5,
  "optimal_time": 125.5
}
```

**GET /api/state**
```json
{
  "fcfs": {
    "time": 125.5,
    "active_requests": [...],
    "available_drivers": [...],
    "active_trips": [...]
  },
  "optimal": { ... }
}
```

**GET /api/metrics**
```json
{
  "fcfs": { "cumulative": {...}, "carpooling": {...} },
  "optimal": { "cumulative": {...}, "carpooling": {...} }
}
```

## 🎓 Educational Use

This webapp is perfect for:

- **Algorithm comparison** demos
- **Research presentations**
- **Classroom teaching** (ride-sharing optimization)
- **Student projects** (extend with new features)

### Demo Tips

1. Start with **comparison view** to show both algorithms
2. Point out **cost difference** in real-time
3. Highlight **dynamic insertions** (⚡ in Optimal)
4. Show **pool utilization** metrics
5. Switch to **single view** for detailed analysis

## 🚀 Future Enhancements

Potential additions:

- [ ] Heatmap of request density
- [ ] Replay mode with timeline scrubber
- [ ] Export visualization as video
- [ ] Multiple algorithm comparison (3-way split)
- [ ] Real-time cost graph
- [ ] Driver earning statistics
- [ ] Passenger satisfaction metrics

## 📝 License

MIT License - Feel free to use for research and education!

## 🤝 Contributing

Want to improve the webapp?

1. Add your feature
2. Test with `python run_webapp.py`
3. Share your improvements!

## 📞 Support

Issues? Questions?

- Check troubleshooting section above
- Review browser console for errors
- Verify backend is running without errors

---

**Enjoy visualizing adaptive ride-sharing! 🚗✨**