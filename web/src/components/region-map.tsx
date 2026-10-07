"use client";
import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { Region, SubregionCollection } from "@/lib/types";

function subregionStyle(feature: GeoJSON.Feature | undefined, selectedLocality: string): L.PathOptions {
  const selected = feature?.properties?.name === selectedLocality;
  return {
    color: selected ? "#125841" : "#447b68",
    weight: 1.5,
    opacity: 0.9,
    fillColor: selected ? "#55a883" : "#91c9ad",
    fillOpacity: 0.28,
  };
}

export default function RegionMap({ regions, selected, onSelect, subregions, selectedLocality, onSelectLocality }: { regions: Region[]; selected: string; onSelect: (code: string) => void; subregions: SubregionCollection | null; selectedLocality: string; onSelectLocality: (name: string) => void }) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef<L.LayerGroup | null>(null);
  const boundaries = useRef<L.GeoJSON | null>(null);
  const selectedLocalityRef = useRef(selectedLocality);
  const onSelectLocalityRef = useRef(onSelectLocality);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!element.current) return;
    const instance = L.map(element.current, { scrollWheelZoom: true, minZoom: 5, maxZoom: 12, zoomSnap: 0.25 });
    instance.fitBounds([[33.15, 125.9], [38.55, 129.7]], { padding: [25, 25] });
    map.current = instance;
    const tile = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' }).addTo(instance);
    tile.on("tileerror", () => setError(true));
    markers.current = L.layerGroup().addTo(instance);
    const observer = new ResizeObserver(() => instance.invalidateSize());
    observer.observe(element.current);
    return () => { observer.disconnect(); instance.remove(); map.current = null; markers.current = null; };
  }, []);
  useEffect(() => {
    selectedLocalityRef.current = selectedLocality;
    onSelectLocalityRef.current = onSelectLocality;
    boundaries.current?.setStyle(feature => subregionStyle(feature, selectedLocality));
  }, [selectedLocality, onSelectLocality]);
  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    boundaries.current?.remove();
    boundaries.current = null;
    if (!subregions) return;
    const layer = L.geoJSON(subregions as GeoJSON.GeoJsonObject, {
      style: feature => subregionStyle(feature, selectedLocalityRef.current),
      onEachFeature: (feature, polygon) => {
        const props = feature.properties as { name?: string; count?: number };
        if (props.name) {
          const tooltip = document.createElement("span");
          tooltip.textContent = `${props.name} · ${props.count ?? 0}건`;
          polygon.bindTooltip(tooltip, { sticky: true });
          polygon.on("click", () => {
            onSelectLocalityRef.current(props.name!);
            const center = (polygon as L.Polygon).getBounds().getCenter();
            instance.panTo(center, { animate: true, duration: 0.35 });
          });
        }
      },
    }).addTo(instance);
    boundaries.current = layer;
    const bounds = layer.getBounds();
    if (bounds.isValid()) instance.fitBounds(bounds, { padding: [20, 20], maxZoom: 11 });
    return () => { layer.remove(); if (boundaries.current === layer) boundaries.current = null; };
  }, [subregions]);
  useEffect(() => {
    const instance = map.current;
    const markerLayer = markers.current;
    if (!instance || !markerLayer) return;
    const renderMarkers = () => {
      markerLayer.clearLayers();
      const pending = regions.map(region => ({ region, position: L.latLng(region.latitude, region.longitude) }))
        .sort((a, b) => Number(b.region.code === selected) - Number(a.region.code === selected) || a.region.code.localeCompare(b.region.code));
      const clusterRadius = 88;
      while (pending.length) {
        const anchor = pending.shift()!;
        const anchorPoint = instance.latLngToContainerPoint(anchor.position);
        const nearby = pending.filter(item => anchorPoint.distanceTo(instance.latLngToContainerPoint(item.position)) <= clusterRadius);
        const nearbyCodes = new Set(nearby.map(item => item.region.code));
        for (let index = pending.length - 1; index >= 0; index--) {
          if (nearbyCodes.has(pending[index].region.code)) pending.splice(index, 1);
        }
        const group = [anchor, ...nearby];
        const center = L.latLng(
          group.reduce((sum, item) => sum + item.position.lat, 0) / group.length,
          group.reduce((sum, item) => sum + item.position.lng, 0) / group.length,
        );
        const selectedInGroup = group.some(item => item.region.code === selected);

        if (group.length > 1) {
          const names = group.map(item => item.region.short_name);
          const button = document.createElement("button");
          button.type = "button";
          button.className = `region-cluster ${selectedInGroup ? "selected" : ""}`;
          button.setAttribute("aria-label", `${names.join(", ")} ${group.length}개 지역 묶음, 눌러서 확대`);
          button.title = `${names.join(" · ")} — 눌러서 지역별로 보기`;
          const count = document.createElement("strong"); count.textContent = String(group.length);
          const label = document.createElement("span"); label.textContent = "지역";
          button.append(count, label);
          button.onclick = () => instance.fitBounds(L.latLngBounds(group.map(item => item.position)), { padding: [70, 70], maxZoom: 12 });
          L.marker(center, { keyboard: false, icon: L.divIcon({ html: button, className: "region-overlay", iconSize: [48, 48], iconAnchor: [24, 24] }) }).addTo(markerLayer);
          continue;
        }

        const region = anchor.region;
        const isSelected = region.code === selected;
        const button = document.createElement("button");
        button.type = "button";
        button.className = `map-marker ${isSelected ? "selected" : ""}`;
        button.setAttribute("aria-label", `${region.name} ${region.count}건 선택`);
        button.setAttribute("aria-pressed", String(isSelected));
        const label = document.createElement("span"); label.textContent = region.short_name;
        const count = document.createElement("strong"); count.textContent = `${isSelected ? "✓ " : ""}${region.count}`;
        button.append(label, count);
        button.onclick = () => onSelect(region.code);
        L.marker(anchor.position, { keyboard: false, icon: L.divIcon({ html: button, className: "region-overlay", iconSize: [84, 40], iconAnchor: [42, 20] }) }).addTo(markerLayer);
      }
    };
    renderMarkers();
    instance.on("zoomend moveend resize", renderMarkers);
    return () => { instance.off("zoomend moveend resize", renderMarkers); };
  }, [regions, selected, onSelect]);
  return <div className="map-wrap"><div ref={element} className="map-canvas" aria-label="대한민국 관련 지역별 뉴스 지도" />{error && <div className="tile-error" role="status">지도 배경을 불러오지 못했습니다. 지역 선택과 뉴스 목록은 계속 사용할 수 있습니다.</div>}</div>;
}
