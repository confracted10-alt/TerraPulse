import io
import os
from datetime import date, timedelta

import folium
import numpy as np
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="TerraPulse | Fire & Ecosystem Explorer", layout="wide")

# --------------------------- Visual system ---------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap');
:root {--bg:#101d17;--panel:#1b2c22;--panel2:#24392c;--line:#34483a;--text:#edf1e7;--muted:#b5c1b0;--sage:#c4d4b5;}
.stApp {background:linear-gradient(160deg,#101d17,#17271e 75%);color:var(--text);font-family:'DM Sans',sans-serif}
[data-testid="stHeader"] {background:rgba(16,29,23,.94)}
[data-testid="stMainBlockContainer"] {max-width:1500px;padding-top:1.2rem}
h1,h2,h3 {color:var(--text)!important}
h1 {font-family:'DM Serif Display',serif!important;font-weight:400!important}
p,label,.stMarkdown {color:var(--text)}
[data-testid="stMetric"] {background:var(--panel);border:1px solid var(--line);padding:13px 16px;border-radius:13px}
[data-testid="stMetricLabel"] {color:var(--muted)}
[data-testid="stMetricValue"] {color:var(--text)}
.stButton button,.stDownloadButton button {background:#2c4836;color:#f5f5ec;border:1px solid #58705a;border-radius:9px}
.stButton button:hover,.stDownloadButton button:hover {background:#3a5a43;color:white;border-color:#a8bd9b}
[data-testid="stSidebar"] {background:#17271e;border-right:1px solid var(--line)}
[data-testid="stSidebar"] * {color:var(--text)}
div[data-testid="stTabs"] button {color:var(--text)}
.tp-kicker {font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:var(--sage);font-weight:700}
.tp-sub {color:var(--muted);max-width:900px;line-height:1.6}
.tp-panel {background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
footer {visibility:hidden}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="tp-kicker">NASA Earth observation · Active fire intelligence</div>', unsafe_allow_html=True)
st.title("TerraPulse")
st.markdown('<div class="tp-sub">Explore satellite-observed thermal anomalies, compare sensors, and investigate the ecosystems around them. TerraPulse separates what satellites detect from what those detections can actually prove.</div>', unsafe_allow_html=True)

FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCES = {
    "MODIS Terra/Aqua": "MODIS_NRT",
    "VIIRS Suomi-NPP": "VIIRS_SNPP_NRT",
    "VIIRS NOAA-20": "VIIRS_NOAA20_NRT",
    "VIIRS NOAA-21": "VIIRS_NOAA21_NRT",
}

def normalise(df, source="Uploaded data"):
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    aliases = {
        "Acquisition date":"acq_date", "Acquisition time":"acq_time",
        "FIRMS source":"sensor_source", "Satellite":"satellite",
        "Latitude":"latitude", "Longitude":"longitude",
        "Original confidence":"confidence", "Display score (approx.)":"confidence_score",
        "Thermal brightness (K)":"brightness", "FRP (MW)":"frp",
        "Day/night":"daynight"
    }
    d = d.rename(columns={k:v for k,v in aliases.items() if k in d.columns})
    for c in ["latitude","longitude","frp","brightness","confidence_score","scan","track"]:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")
    if "confidence_score" not in d:
        raw = d["confidence"].astype(str).str.lower() if "confidence" in d else pd.Series("",index=d.index)
        numeric = pd.to_numeric(raw, errors="coerce")
        d["confidence_score"] = numeric.fillna(raw.map({"l":30,"low":30,"n":60,"nominal":60,"h":90,"high":90}))
    if "confidence" not in d: d["confidence"] = "Not supplied"
    if "frp" not in d: d["frp"] = np.nan
    if "brightness" not in d: d["brightness"] = np.nan
    if "sensor_source" not in d: d["sensor_source"] = source
    if "satellite" not in d: d["satellite"] = d["sensor_source"]
    if "acq_date" in d: d["acq_date"] = pd.to_datetime(d["acq_date"], errors="coerce")
    else: d["acq_date"] = pd.NaT
    if "acq_time" not in d: d["acq_time"] = "—"
    if "daynight" not in d: d["daynight"] = "Unknown"
    return d.dropna(subset=["latitude","longitude"]).query("latitude >= -90 and latitude <= 90 and longitude >= -180 and longitude <= 180").reset_index(drop=True)

@st.cache_data(ttl=900, show_spinner=False)
def load_sample():
    path = os.path.join(os.path.dirname(__file__), "sample_data", "terrapulse_sample.csv")
    return normalise(pd.read_csv(path))

@st.cache_data(ttl=900, show_spinner=False)
def fetch_firms(api_key, source, days):
    url = f"{FIRMS_URL}/{api_key}/{source}/world/{days}"
    response = requests.get(url, timeout=(10,45))
    response.raise_for_status()
    body = response.text.strip()
    if not body or body.lower().startswith(("invalid","error","no data")):
        raise RuntimeError(body[:200] or "NASA FIRMS returned no data.")
    return normalise(pd.read_csv(io.StringIO(body)), source)

# --------------------------- Data source ---------------------------
with st.sidebar:
    st.markdown("## Data & filters")
    st.caption("Start with the included sample snapshot. Live NASA data is optional.")
    source_mode = st.radio("Data source", ["Included sample data", "Upload FIRMS CSV", "Live NASA FIRMS feed"], index=0)
    data = pd.DataFrame()
    if source_mode == "Included sample data":
        data = load_sample()
    elif source_mode == "Upload FIRMS CSV":
        uploaded = st.file_uploader("Choose a NASA FIRMS CSV", type=["csv"])
        if uploaded is not None:
            try: data = normalise(pd.read_csv(uploaded))
            except Exception as e: st.error(f"Could not read that CSV: {e}")
    else:
        api_key = st.text_input("NASA FIRMS MAP_KEY", type="password", help="Enter your key here. Do not share it in chat or publish it.")
        selected_source = st.selectbox("Satellite product", list(SOURCES.keys()))
        days = st.slider("Recent days", 1, 5, 2)
        if st.button("Fetch latest observations", use_container_width=True):
            if not api_key.strip():
                st.warning("Enter your FIRMS key first.")
            else:
                try:
                    with st.spinner("Requesting data from NASA FIRMS…"):
                        st.session_state["live_data"] = fetch_firms(api_key.strip(), SOURCES[selected_source], days)
                    st.session_state["live_label"] = f"{selected_source} · last {days} days"
                except requests.exceptions.Timeout:
                    st.error("NASA FIRMS timed out. Your app is still running; try again later or use the sample data.")
                except Exception as e:
                    st.error(f"NASA FIRMS request failed: {e}")
        data = st.session_state.get("live_data", pd.DataFrame())
        if data.empty: st.info("Fetch the feed to load live observations. The sample dataset remains available from the first option.")

    st.divider()
    st.markdown("### Observation filters")
    if not data.empty:
        sensors = sorted(data["sensor_source"].dropna().astype(str).unique().tolist())
        chosen_sensors = st.multiselect("Satellite source", sensors, default=sensors)
        confidence = st.slider("Minimum approximate confidence", 0, 100, 0)
        dates = data["acq_date"].dropna()
        if not dates.empty:
            min_d, max_d = dates.min().date(), dates.max().date()
            date_range = st.date_input("Acquisition date range", value=(min_d,max_d), min_value=min_d, max_value=max_d)
        else:
            date_range = None
    else:
        chosen_sensors, confidence, date_range = [], 0, None

if data.empty:
    st.info("No observations are loaded yet. Choose the sample dataset, upload a FIRMS CSV, or fetch live data.")
    st.stop()

filtered = data[data["sensor_source"].astype(str).isin(chosen_sensors)].copy()
filtered = filtered[filtered["confidence_score"].fillna(0) >= confidence]
if date_range and isinstance(date_range, (tuple,list)) and len(date_range)==2:
    filtered = filtered[filtered["acq_date"].isna() | filtered["acq_date"].dt.date.between(date_range[0],date_range[1])]

# --------------------------- Map controls ---------------------------
map_col, controls_col = st.columns([4.4,1.15], gap="large")
with controls_col:
    st.markdown("### Map controls")
    map_style = st.selectbox("Basemap", ["Street map", "Satellite imagery", "Terrain"])
    map_center_mode = st.selectbox("Initial view", ["Global", "Data extent", "Saudi Arabia"])
    map_limit = st.select_slider("Markers shown", options=[500,1000,2500,5000], value=2500)
    st.caption("The map is a visual sample when the dataset is large. Metrics, analysis, and downloads use every filtered record.")
    st.download_button("Download filtered CSV", filtered.to_csv(index=False).encode("utf-8"), "terrapulse_filtered_observations.csv", "text/csv", use_container_width=True)

with map_col:
    st.markdown("### Geographic observation map")
    st.caption("Select a marker for its satellite, acquisition time, confidence, and FRP.")
    if map_center_mode == "Saudi Arabia":
        center, zoom = [24.0,45.0], 5
    elif map_center_mode == "Data extent" and not filtered.empty:
        center = [float(filtered.latitude.mean()),float(filtered.longitude.mean())]
        zoom = 4
    else:
        center, zoom = [15,0], 2
    m = folium.Map(location=center, zoom_start=zoom, tiles=None, control_scale=True, prefer_canvas=True)
    if map_style == "Street map":
        folium.TileLayer("OpenStreetMap", name="Street map", control=False).add_to(m)
    elif map_style == "Terrain":
        folium.TileLayer("CartoDB positron", name="Light geographic map", control=False).add_to(m)
    else:
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles © Esri", name="Satellite imagery", control=False
        ).add_to(m)
    # Optional layer switch remains available if the user wants to switch basemaps.
    folium.TileLayer("OpenStreetMap", name="Street map", show=False).add_to(m)
    folium.TileLayer("CartoDB positron", name="Light geographic map", show=False).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri", name="Satellite imagery", show=False
    ).add_to(m)
    points = filtered
    if len(points) > map_limit:
        points = points.sample(map_limit, random_state=17)
    marker_group = folium.FeatureGroup(name="NASA FIRMS observations", show=True)
    for row in points.itertuples(index=False):
        lat, lon = float(row.latitude), float(row.longitude)
        score = getattr(row,"confidence_score",np.nan)
        frp = getattr(row,"frp",np.nan)
        color = "#6f8f78" if pd.isna(score) or score < 50 else ("#b7a66d" if score < 80 else "#c1d2a8")
        date_text = row.acq_date.strftime("%Y-%m-%d") if pd.notna(row.acq_date) else "Not supplied"
        popup = (
            f"<b>Satellite observation</b><br>Satellite: {str(row.satellite)}<br>"
            f"Source: {str(row.sensor_source)}<br>Date: {date_text}<br>Time: {str(row.acq_time)}<br>"
            f"Confidence: {str(row.confidence)}<br>FRP: {frp if pd.notna(frp) else 'Not supplied'} MW"
        )
        folium.CircleMarker([lat,lon], radius=4, color=color, weight=1, fill=True,
                            fill_color=color, fill_opacity=.82,
                            popup=folium.Popup(popup,max_width=300)).add_to(marker_group)
    marker_group.add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    components.html(m.get_root().render(), height=650, scrolling=False)
    st.caption(f"Displaying {len(points):,} of {len(filtered):,} filtered observations. A FIRMS detection is a satellite-observed thermal anomaly, not automatically a confirmed wildfire.")

# --------------------------- Overview ---------------------------
st.divider()
st.markdown("## Observation overview")
a,b,c,d = st.columns(4)
a.metric("Filtered detections", f"{len(filtered):,}")
b.metric("Satellite sources", f"{filtered.sensor_source.nunique():,}")
frp_values = pd.to_numeric(filtered.frp,errors="coerce").dropna()
c.metric("Median FRP", f"{frp_values.median():.2f} MW" if not frp_values.empty else "Not available")
d.metric("High-confidence records", f"{(filtered.confidence_score >= 80).sum():,}")

overview_tab, compare_tab, ecosystem_tab, guide_tab = st.tabs(["Analysis","Sensor comparison","Ecosystem context","Field guide"])
with overview_tab:
    left,right = st.columns(2)
    with left:
        st.markdown("### Detections by satellite source")
        st.bar_chart(filtered["sensor_source"].value_counts())
    with right:
        st.markdown("### FRP distribution")
        if not frp_values.empty:
            hist = pd.cut(frp_values, bins=12).value_counts().sort_index()
            hist.index = hist.index.astype(str)
            st.bar_chart(hist)
        else: st.info("FRP values are not present in this dataset.")
    st.markdown("### Highest FRP observations")
    if not frp_values.empty:
        top = filtered.assign(_frp=pd.to_numeric(filtered.frp,errors="coerce")).nlargest(15,"_frp")
        show_cols = [c for c in ["acq_date","satellite","latitude","longitude","frp","confidence"] if c in top]
        st.dataframe(top[show_cols], use_container_width=True, hide_index=True)
    st.caption("FRP is the rate of radiant energy released from a detected pixel at observation time. It is not temperature, burned area, or a direct measure of ecological damage.")

with compare_tab:
    st.markdown("### Cross-sensor observation comparison")
    st.write("This screen looks for detections from different satellite products that occur near each other in space and time. A pair is a possible cross-sensor match, not proof that both sensors observed the exact same fire event.")
    dist_km = st.slider("Maximum separation (km)", 1, 20, 5)
    time_mins = st.slider("Maximum acquisition-time difference (minutes)", 1, 120, 30)
    compare = filtered.dropna(subset=["acq_date","latitude","longitude"]).copy()
    time_digits = pd.to_numeric(compare["acq_time"].astype(str).str.extract(r"(\d{1,4})", expand=False), errors="coerce").fillna(0).astype(int)
    compare["minute_of_day"] = (time_digits // 100) * 60 + (time_digits % 100)
    compare["absolute_minute"] = compare["acq_date"].dt.date.map(lambda x: x.toordinal() * 1440) + compare["minute_of_day"]
    compare = compare.head(3000).reset_index(drop=True)
    if len(compare)>1 and compare.sensor_source.nunique()>1:
        coords = np.radians(compare[["latitude","longitude"]].to_numpy())
        sources_array = compare.sensor_source.astype(str).to_numpy()
        absolute_minutes = compare.absolute_minute.to_numpy()
        pairs=[]
        # Bounded-memory row-wise matching; avoids a large N x N matrix.
        for i in range(len(compare)-1):
            candidates = np.arange(i+1, len(compare))
            candidates = candidates[sources_array[candidates] != sources_array[i]]
            if not len(candidates):
                continue
            dlat = coords[candidates,0] - coords[i,0]
            dlon = coords[candidates,1] - coords[i,1]
            aa = np.sin(dlat/2)**2 + np.cos(coords[i,0])*np.cos(coords[candidates,0])*np.sin(dlon/2)**2
            distances = 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(aa,0,1)))
            time_diffs = np.abs(absolute_minutes[candidates] - absolute_minutes[i])
            valid = (distances <= dist_km) & (time_diffs <= time_mins)
            for pos in np.where(valid)[0][:3]:
                j = candidates[pos]
                pairs.append({"Source A":sources_array[i],"Source B":sources_array[j],
                              "Date":compare.iloc[i].acq_date.date(),"Distance (km)":round(float(distances[pos]),2),
                              "Time difference (min)":int(time_diffs[pos]),"Latitude":round(float(compare.iloc[i].latitude),4),
                              "Longitude":round(float(compare.iloc[i].longitude),4)})
                if len(pairs) >= 500:
                    break
            if len(pairs) >= 500:
                break
        pair_df=pd.DataFrame(pairs)
        st.metric("Potential cross-sensor pairs",f"{len(pair_df):,}")
        if not pair_df.empty:
            st.dataframe(pair_df,use_container_width=True,hide_index=True)
            st.download_button("Download pairs",pair_df.to_csv(index=False).encode(), "terrapulse_sensor_pairs.csv","text/csv")
        else: st.info("No pairs met the selected thresholds.")
    else:
        st.info("Load at least two satellite sources with acquisition dates to compare observations.")

with ecosystem_tab:
    st.markdown("### Add ecological context")
    st.write("Upload supporting data to investigate where detections overlap mapped habitats or how vegetation-index values change over time.")
    geojson_file=st.file_uploader("Habitat or protected-area GeoJSON",type=["geojson","json"],key="geo")
    if geojson_file:
        try:
            import json
            from shapely.geometry import shape, Point
            geo=json.load(geojson_file)
            features=geo.get("features",[]) if geo.get("type")=="FeatureCollection" else [{"geometry":geo,"properties":{}}]
            polygons=[]
            for feat in features:
                if feat.get("geometry"):
                    props=feat.get("properties") or {}
                    label=props.get("name") or props.get("NAME") or props.get("species") or "Mapped area"
                    polygons.append((str(label),shape(feat["geometry"])))
            rows=[]
            for r in filtered.itertuples(index=False):
                p=Point(float(r.longitude),float(r.latitude))
                for name,poly in polygons:
                    if poly.is_valid and poly.intersects(p):
                        rows.append({"Mapped area":name,"Date":r.acq_date.date() if pd.notna(r.acq_date) else "Unknown","Satellite":r.sensor_source,"Latitude":r.latitude,"Longitude":r.longitude})
            overlap=pd.DataFrame(rows)
            st.metric("Detections inside uploaded polygons",f"{len(overlap):,}")
            if not overlap.empty: st.dataframe(overlap,use_container_width=True,hide_index=True)
            st.caption("Point-in-polygon overlap is a screening result. It does not establish that wildlife was harmed or that a fire caused ecological change.")
        except ImportError:
            st.error("Install the optional Shapely package to calculate polygon overlap.")
        except Exception as e: st.error(f"Could not process this GeoJSON: {e}")
    st.divider()
    veg_file=st.file_uploader("Vegetation-index CSV (needs date and NDVI columns)",type=["csv"],key="veg")
    if veg_file:
        try:
            veg=pd.read_csv(veg_file)
            cols={c.lower():c for c in veg.columns}
            dc=next((cols[x] for x in ["date","acq_date","timestamp"] if x in cols),None)
            nc=next((cols[x] for x in ["ndvi","mean_ndvi","value"] if x in cols),None)
            if not dc or not nc: st.warning("Required columns: date and NDVI.")
            else:
                veg[dc]=pd.to_datetime(veg[dc],errors="coerce"); veg[nc]=pd.to_numeric(veg[nc],errors="coerce")
                veg=veg.dropna(subset=[dc,nc]).sort_values(dc)
                if not veg.empty:
                    st.line_chart(veg.set_index(dc)[nc])
                    st.caption("NDVI is a vegetation-greenness index. Changes can reflect season, rainfall, clouds, land management, and sensor differences—not only fire effects.")
        except Exception as e: st.error(f"Could not read vegetation CSV: {e}")

with guide_tab:
    st.markdown("### Read the observations carefully")
    guide = [
        ("Thermal anomaly","A satellite pixel with a thermal signal consistent with a heat source. It is not automatically a confirmed wildfire."),
        ("FRP — Fire Radiative Power","The rate at which detected fire radiates energy, usually reported in megawatts. It is not fire temperature or burned area."),
        ("Confidence","A sensor/product-specific confidence field. TerraPulse preserves the original value and only uses an approximate numeric score for filtering."),
        ("MODIS and VIIRS","Different instruments with different spatial resolutions, overpass times, and detection characteristics. Raw counts should not be treated as a direct performance contest."),
        ("NDVI","A vegetation greenness index. It is useful for monitoring change but cannot independently prove fire damage or ecosystem recovery."),
        ("Habitat overlap","A spatial screening result showing detections inside uploaded polygons. Proximity or overlap does not prove wildlife exposure or harm."),
    ]
    for term,desc in guide:
        with st.expander(term): st.write(desc)

st.divider()
st.caption("TerraPulse is an educational analysis tool. Verify important findings against authoritative fire reports, satellite products, weather, land-cover data, and field evidence.")
