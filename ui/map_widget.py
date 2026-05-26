import json
import os
import tempfile
from typing import Callable

import numpy as np
from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QVBoxLayout, QWidget

_BASEMAPS = {
    "简洁灰": {
        "url": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "attribution": "CartoDB",
        "maxZoom": 19,
        "subdomains": "abcd",
    },
    "深色": {
        "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "attribution": "CartoDB",
        "maxZoom": 19,
        "subdomains": "abcd",
    },
    "OpenStreetMap": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "OpenStreetMap",
        "maxZoom": 19,
        "subdomains": "abc",
    },
    "卫星影像": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri",
        "maxZoom": 18,
        "subdomains": "",
    },
    "地形图": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri",
        "maxZoom": 18,
        "subdomains": "",
    },
    "无底图": {
        "url": "",
        "attribution": "",
        "maxZoom": 20,
        "subdomains": "",
    },
}

_MAP_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  html, body, #map { width:100%; height:100%; margin:0; padding:0; background:#ECEFF1; }
  .leaflet-control-attribution { font-size:10px; }
  #coords-bar {
    position: absolute; bottom: 0; left: 0; right: 0;
    background: rgba(38,50,56,0.85); color: #B0BEC5;
    font-size: 11px; font-family: monospace;
    padding: 3px 10px; z-index: 1000; pointer-events: none;
  }
</style>
</head>
<body>
<div id="map"></div>
<div id="coords-bar">经度: -- 纬度: -- | 缩放: --</div>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
var map = L.map('map', {
  center: [75, 0],
  zoom: 3,
  zoomControl: true,
  attributionControl: true
});

var basemapConfigs = BASEMAP_JSON;
var activeLayers = {};
var activeBasemap = null;
var coordsBar = document.getElementById('coords-bar');

function applyBasemap(name) {
  if (activeBasemap) { map.removeLayer(activeBasemap); activeBasemap = null; }
  var cfg = basemapConfigs[name];
  if (!cfg || !cfg.url) return;
  var opts = { attribution: cfg.attribution, maxZoom: cfg.maxZoom };
  if (cfg.subdomains) opts.subdomains = cfg.subdomains;
  activeBasemap = L.tileLayer(cfg.url, opts).addTo(map);
}

applyBasemap('简洁灰');

map.on('mousemove', function(e) {
  coordsBar.textContent = '经度: ' + e.latlng.lng.toFixed(4)
    + '  纬度: ' + e.latlng.lat.toFixed(4)
    + '  |  缩放: ' + map.getZoom();
});

map.on('click', function(e) {
  if (window.bridge) window.bridge.on_click(e.latlng.lat, e.latlng.lng);
});

function setBasemap(name) { applyBasemap(name); }

function addImageOverlay(layerId, dataUrl, southWest, northEast, opacity) {
  removeLayer(layerId);
  var bounds = [[southWest[0], southWest[1]], [northEast[0], northEast[1]]];
  var layer = L.imageOverlay(dataUrl, bounds, {opacity: opacity, interactive: false});
  layer.addTo(map);
  activeLayers[layerId] = layer;
  map.fitBounds(bounds, {padding: [20, 20]});
}

function addPolyline(layerId, pointsJson, color, weight, opacity) {
  removeLayer(layerId);
  var pts = JSON.parse(pointsJson);
  var layer = L.polyline(pts, {color: color, weight: weight, opacity: opacity});
  layer.addTo(map);
  activeLayers[layerId] = layer;
  map.fitBounds(layer.getBounds(), {padding: [20, 20]});
}

function addMarkers(layerId, markersJson) {
  removeLayer(layerId);
  var markers = JSON.parse(markersJson);
  var group = L.layerGroup();
  markers.forEach(function(m) {
    var mk = L.circleMarker([m.lat, m.lng], {
      radius: m.radius || 5,
      color: m.color || '#00838F',
      fillColor: m.fill || '#00ACC1',
      fillOpacity: 0.8,
      weight: 1.5
    });
    if (m.popup) mk.bindPopup(m.popup);
    mk.addTo(group);
  });
  group.addTo(map);
  activeLayers[layerId] = group;
}

function addGeoJson(layerId, geojsonStr, style) {
  removeLayer(layerId);
  var data = JSON.parse(geojsonStr);
  var layer = L.geoJSON(data, {style: style || {}});
  layer.addTo(map);
  activeLayers[layerId] = layer;
  map.fitBounds(layer.getBounds(), {padding: [20, 20]});
}

function removeLayer(layerId) {
  if (activeLayers[layerId]) {
    map.removeLayer(activeLayers[layerId]);
    delete activeLayers[layerId];
  }
}

function setLayerOpacity(layerId, opacity) {
  if (activeLayers[layerId] && activeLayers[layerId].setOpacity) {
    activeLayers[layerId].setOpacity(opacity);
  }
}

function flyTo(lat, lng, zoom) {
  map.flyTo([lat, lng], zoom || map.getZoom(), {duration: 1.0});
}

function clearAllLayers() {
  Object.keys(activeLayers).forEach(function(id) {
    map.removeLayer(activeLayers[id]);
  });
  activeLayers = {};
}

new QWebChannel(qt.webChannelTransport, function(channel) {
  window.bridge = channel.objects.bridge;
});
</script>
</body>
</html>
"""


class _MapBridge(QObject):
    clicked = pyqtSignal(float, float)

    @pyqtSlot(float, float)
    def on_click(self, lat: float, lng: float):
        self.clicked.emit(lat, lng)


class MapWidget(QWidget):
    map_clicked = pyqtSignal(float, float)
    basemaps = list(_BASEMAPS.keys())

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = QWebEngineView()
        self._channel = QWebChannel()
        self._bridge = _MapBridge()
        self._bridge.clicked.connect(self.map_clicked)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        html = _MAP_HTML.replace("BASEMAP_JSON", json.dumps(_BASEMAPS, ensure_ascii=False))
        self._view.setHtml(html, QUrl("about:blank"))

    def _js(self, script: str):
        self._view.page().runJavaScript(script)

    def set_basemap(self, name: str):
        if name in _BASEMAPS:
            self._js(f"setBasemap({json.dumps(name)});")

    def add_image_overlay(self, layer_id: str, data_url: str,
                          south: float, west: float, north: float, east: float,
                          opacity: float = 0.8):
        self._js(
            f"addImageOverlay({json.dumps(layer_id)}, {json.dumps(data_url)}, "
            f"[{south},{west}], [{north},{east}], {opacity});"
        )

    def add_geotiff_layer(self, layer_id: str, filepath: str,
                          colormap: str = "viridis", opacity: float = 0.8,
                          vmin=None, vmax=None):
        try:
            arr, bounds = _load_geotiff(filepath)
        except Exception as e:
            print(f"[地图] GeoTIFF加载失败: {e}")
            return
        data_url = _array_to_data_url(arr, colormap, vmin, vmax)
        s, w, n, e = bounds
        self.add_image_overlay(layer_id, data_url, s, w, n, e, opacity)

    def add_polyline(self, layer_id: str, points: list[tuple],
                     color: str = "#00838F", weight: int = 2, opacity: float = 0.9):
        pts_json = json.dumps([[p[0], p[1]] for p in points])
        self._js(f"addPolyline({json.dumps(layer_id)}, {json.dumps(pts_json)}, "
                 f"{json.dumps(color)}, {weight}, {opacity});")

    def add_markers(self, layer_id: str, markers: list[dict]):
        mk_json = json.dumps(markers)
        self._js(f"addMarkers({json.dumps(layer_id)}, {json.dumps(mk_json)});")

    def add_geojson(self, layer_id: str, geojson: dict, style: dict = None):
        geo_str = json.dumps(geojson)
        style_str = json.dumps(style or {})
        self._js(f"addGeoJson({json.dumps(layer_id)}, {json.dumps(geo_str)}, {style_str});")

    def remove_layer(self, layer_id: str):
        self._js(f"removeLayer({json.dumps(layer_id)});")

    def set_layer_opacity(self, layer_id: str, opacity: float):
        self._js(f"setLayerOpacity({json.dumps(layer_id)}, {opacity});")

    def fly_to(self, lat: float, lng: float, zoom: int = None):
        zoom_str = str(zoom) if zoom else "undefined"
        self._js(f"flyTo({lat}, {lng}, {zoom_str});")

    def clear_all(self):
        self._js("clearAllLayers();")


def _load_geotiff(filepath: str) -> tuple[np.ndarray, tuple]:
    try:
        import rasterio
        from rasterio.warp import calculate_default_transform, reproject, Resampling

        with rasterio.open(filepath) as src:
            if src.crs and src.crs.to_epsg() != 4326:
                transform, width, height = calculate_default_transform(
                    src.crs, "EPSG:4326", src.width, src.height, *src.bounds
                )
                data = np.zeros((height, width), dtype=np.float32)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=data,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs="EPSG:4326",
                    resampling=Resampling.bilinear,
                )
                left, bottom = transform * (0, height)
                right, top = transform * (width, 0)
            else:
                data = src.read(1).astype(np.float32)
                b = src.bounds
                left, bottom, right, top = b.left, b.bottom, b.right, b.top

            nodata = src.nodata
            if nodata is not None:
                data[data == nodata] = np.nan

        return data, (bottom, left, top, right)

    except ImportError:
        from PIL import Image
        img = Image.open(filepath)
        data = np.array(img).astype(np.float32)
        if data.ndim == 3:
            data = data.mean(axis=2)
        return data, (-90, -180, 90, 180)


def _array_to_data_url(arr: np.ndarray, colormap: str = "viridis",
                        vmin=None, vmax=None) -> str:
    import base64
    import io
    import matplotlib.pyplot as plt
    from PIL import Image

    valid = arr[~np.isnan(arr)]
    lo = float(valid.min()) if vmin is None else vmin
    hi = float(valid.max()) if vmax is None else vmax
    if lo == hi:
        hi = lo + 1

    norm = (arr - lo) / (hi - lo)
    norm = np.clip(norm, 0, 1)

    cmap = plt.get_cmap(colormap)
    rgba = cmap(norm)
    rgba[np.isnan(arr)] = (0, 0, 0, 0)

    img_arr = (rgba * 255).astype(np.uint8)
    img = Image.fromarray(img_arr, "RGBA")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"
