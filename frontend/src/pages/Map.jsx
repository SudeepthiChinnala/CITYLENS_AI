import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { getAreas, getClusters, getComplaints, getImpactPriority, getPublicComplaints } from '../services/api';
import { classifyConcentration } from '../services/criticality';

const HYDERABAD_CENTER = [17.385, 78.4867];
const CRITICALITY_COLOR = {
  CRITICAL: '#dc2626',
  HIGH: '#ea580c',
  MEDIUM: '#d97706',
  LOW: '#16a34a',
};

function errorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (error?.response) return `Server error (${error.response.status})`;
  return 'Could not reach the CityLens AI backend. Is it running?';
}

function MapPage({ embedded = false, audience = 'admin' }) {
  const [clusters, setClusters] = useState([]);
  const [complaints, setComplaints] = useState([]);
  const [areas, setAreas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [impactByComplaint, setImpactByComplaint] = useState({});
  const [impactLoadingIds, setImpactLoadingIds] = useState({});
  const requestedImpactIds = useRef(new Set());

  const loadImpactPriority = complaintId => {
    if (audience !== 'admin' || requestedImpactIds.current.has(complaintId)) return;
    requestedImpactIds.current.add(complaintId);
    setImpactLoadingIds(current => ({ ...current, [complaintId]: true }));
    getImpactPriority(complaintId)
      .then(result => setImpactByComplaint(current => ({ ...current, [complaintId]: result })))
      .catch(err => setImpactByComplaint(current => ({ ...current, [complaintId]: { error: errorMessage(err) } })))
      .finally(() => setImpactLoadingIds(current => ({ ...current, [complaintId]: false })));
  };

  useEffect(() => {
    let active = true;
    const mapData = audience === 'citizen'
      ? Promise.all([getClusters(), getPublicComplaints()])
      : Promise.all([getClusters(), getComplaints(), getAreas()]);
    mapData
      .then(([clusterData, complaintData, adminAreaData = []]) => {
        if (!active) return;
        setClusters(clusterData);
        setComplaints(complaintData);
        if (audience === 'citizen') {
          const counts = {};
          complaintData.forEach(complaint => {
            const area = complaint.area || 'Unknown';
            counts[area] = (counts[area] || 0) + 1;
          });
          setAreas(Object.entries(counts).map(([area, total]) => ({ area, total })));
        } else {
          setAreas(adminAreaData);
        }
      })
      .catch(err => {
        if (active) setError(errorMessage(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [audience]);

  const validComplaints = useMemo(() => complaints.filter(complaint => (
    Number.isFinite(Number(complaint.latitude)) && Number.isFinite(Number(complaint.longitude))
  )), [complaints]);

  const validClusters = useMemo(() => clusters.filter(cluster => (
    cluster?.geometry?.coordinates?.length === 2 &&
    Number.isFinite(Number(cluster.geometry.coordinates[0])) &&
    Number.isFinite(Number(cluster.geometry.coordinates[1]))
  )), [clusters]);

  const areaConcentrations = useMemo(() => {
    const max = Math.max(...areas.map(area => Number(area.total) || 0), 0);
    return Object.fromEntries(areas.map(area => [area.area, classifyConcentration(area.total, max)]));
  }, [areas]);

  const clusterConcentrations = useMemo(() => {
    const max = Math.max(...validClusters.map(cluster => Number(cluster.properties?.count) || 0), 0);
    return Object.fromEntries(validClusters.map(cluster => [cluster.properties?.cluster_id, classifyConcentration(cluster.properties?.count, max)]));
  }, [validClusters]);

  const leadingArea = useMemo(() => {
    const highest = [...areas].filter(area => Number(area.total) > 0)
      .sort((a, b) => Number(b.total) - Number(a.total))[0];
    if (!highest) return null;
    return { ...highest, concentration: areaConcentrations[highest.area] };
  }, [areas, areaConcentrations]);

  if (loading) return <p className="placeholder">Loading live problem map…</p>;
  if (error) return <div className="error">Could not load map data: {error}</div>;

  return (
    <div className={embedded ? 'map-page embedded-map' : 'map-page'}>
      {!embedded && (
        <div className="page-header">
          <div>
            <h2>{audience === 'citizen' ? 'Civic Issue Map' : 'Risk & Hotspot Map'}</h2>
            <div className="sub">Complaint locations and existing DBSCAN hotspots across Hyderabad.</div>
          </div>
        </div>
      )}

      <div className="panel">
        <div className="map-toolbar">
          <div className="map-legend">
            <span className="legend-item"><span className="legend-dot complaint-dot" /> Complaint location</span>
            <span className="legend-item"><span className="legend-dot hotspot-dot" /> DBSCAN hotspot</span>
            <span className="legend-item">Red: critical · orange: high · yellow: medium · green: low</span>
            {audience === 'admin' && <span className="legend-item">Colors remain area concentration; after inspection, larger markers indicate higher estimated impact.</span>}
          </div>
          <span className="map-count">{validComplaints.length} complaints · {validClusters.length} hotspots</span>
          {audience === 'citizen' && <span className="map-privacy-note">Public issue details only · personal information hidden</span>}
          {leadingArea && (
            <span className="map-count">
              Most affected: {leadingArea.area} · {leadingArea.concentration.complaintCount} complaints · {leadingArea.concentration.percentageOfMaximum}% of max
            </span>
          )}
        </div>
        {validComplaints.length === 0 && validClusters.length === 0 && (
          <p className="placeholder map-empty-note">No complaint or hotspot coordinates are available yet.</p>
        )}
        <MapContainer center={HYDERABAD_CENTER} zoom={11} scrollWheelZoom className="city-map">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {validComplaints.map(complaint => {
            const concentration = areaConcentrations[complaint.area] || { complaintCount: 0, percentageOfMaximum: 0, level: null };
            const impact = impactByComplaint[complaint.id];
            const impactScore = impact?.impact_priority_score;
            const impactLevel = impactScore == null ? null : (impactScore >= 80 ? 'CRITICAL' : impactScore >= 60 ? 'HIGH' : impactScore >= 40 ? 'MEDIUM' : 'LOW');
            const concentrationLevel = concentration.level || 'LOW';
            const color = CRITICALITY_COLOR[concentrationLevel];
            const markerRadius = impactLevel ? (impactScore >= 80 ? 9 : impactScore >= 60 ? 8 : impactScore >= 40 ? 7 : 6) : 5;
            return (
              <CircleMarker
                key={`complaint-${complaint.id}`}
                center={[Number(complaint.latitude), Number(complaint.longitude)]}
                radius={markerRadius}
                pathOptions={{ color, fillColor: color, fillOpacity: 0.8, weight: impactLevel ? 2.5 : 1 }}
                eventHandlers={audience === 'admin' ? { click: () => loadImpactPriority(complaint.id) } : undefined}
              >
                <Popup>
                  <strong>Complaint #{complaint.id}</strong><br />
                  Area: {complaint.area || 'Unknown'}<br />
                  Area concentration: {concentrationLevel}<br />
                  Area complaints: {concentration.complaintCount} ({concentration.percentageOfMaximum}% of max)<br />
                  Problem: {complaint.problem_type || 'Other'}<br />
                  Severity: {complaint.severity || '—'}<br />
                  Status: {complaint.status || '—'}<br />
                  Priority: {complaint.priority_score != null ? complaint.priority_score.toFixed(1) : '—'}
                  {audience === 'admin' && <><br /><strong>Estimated Impact Priority:</strong> {impactLoadingIds[complaint.id] ? 'checking nearby OSM features…' : impact?.impact_priority_score != null ? `${impact.impact_priority_score}/100 (${impactLevel})` : impact?.fallback_reason || impact?.error || 'select marker to calculate'}
                    {impact?.impact_priority_score != null && <><br />Exposure: {impact.exposure_score}/100 · schools {impact.nearby_schools} · hospitals {impact.nearby_hospitals} · stops {impact.nearby_bus_stops} · major road {impact.major_road_proximity ? 'yes' : 'no'}<br />Related stored incidents: {impact.recurrence_count}<br /><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">© OpenStreetMap contributors</a></>}
                  </>}
                </Popup>
              </CircleMarker>
            );
          })}
          {validClusters.map(cluster => {
            const properties = cluster.properties || {};
            const [longitude, latitude] = cluster.geometry.coordinates;
            const concentration = clusterConcentrations[properties.cluster_id] || { complaintCount: 0, percentageOfMaximum: 0, level: null };
            const level = concentration.level || 'LOW';
            const color = CRITICALITY_COLOR[level];
            const radius = Math.min(20, 8 + Math.sqrt(Number(properties.count) || 1) * 3);
            return (
              <CircleMarker
                key={`cluster-${properties.cluster_id}`}
                center={[Number(latitude), Number(longitude)]}
                radius={radius}
                pathOptions={{ color, fillColor: color, fillOpacity: 0.55, weight: 2 }}
              >
                <Popup>
                  <strong>Hotspot #{properties.cluster_id}</strong><br />
                  Criticality: {level}<br />
                  Cluster size: {concentration.complaintCount} complaints ({concentration.percentageOfMaximum}% of max)<br />
                  Main problem: {properties.problem_type || '—'}<br />
                  Average severity: {properties.avg_severity ?? '—'}
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
}

export default MapPage;
