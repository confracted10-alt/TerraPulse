TERRAPULSE — CLEAN REBUILD

1. Extract this entire ZIP into a normal folder (not inside the ZIP preview).
2. Install Python 3.12 from https://www.python.org/downloads/ if it is not already installed.
   During installation, enable "Add Python to PATH".
3. Double-click START_TERRAPULSE.bat.
4. Wait while packages install. The first launch needs an internet connection.
5. Open http://localhost:8501 if the browser does not open automatically.
6. Keep the black terminal window open while using TerraPulse. Close it to stop the app.

START WITH THE INCLUDED SAMPLE DATA:
The sample data option works without a NASA key. Live NASA FIRMS data is optional.
For live data, enter your own FIRMS MAP_KEY inside the app. Never share the key in chat,
screenshots, source code, or a public repository.

IMPORTANT:
- Use Python 3.12. The launcher prefers Python 3.12 if installed.
- Basemap tiles need internet access. If tiles are blocked by your network, the map area
  may appear blank even though the app itself is running.
- This version uses Folium-generated maps rather than custom hand-written map JavaScript.
- The map displays a sample of up to 5,000 records for responsiveness; analysis and CSV
  exports use the complete filtered dataset.
- FIRMS detections are thermal anomalies, not automatically confirmed wildfires.
