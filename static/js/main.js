/*
 * main.js
 * -------
 * Handles: the search form, rendering weather + forecast into the
 * DOM, initializing the Leaflet radar map, and surfacing errors to
 * the user via a toast instead of a browser alert() popup.
 */

const form = document.getElementById('search-form');
const input = document.getElementById('city-input');
const loading = document.getElementById('loading');
const resultSection = document.getElementById('weather-result');
const toast = document.getElementById('toast');

// Leaflet doesn't allow creating a second map on the same <div>, so
// these are declared once, outside any function, and reused across
// searches instead of being recreated every time.
let map = null;
let radarLayer = null;

function showToast(message) {
    toast.textContent = message;
    toast.classList.remove('hidden');
    // Auto-hide after a few seconds so error messages don't
    // permanently clutter the screen.
    setTimeout(() => toast.classList.add('hidden'), 4000);
}

function initMap(lat, lon) {
    if (!map) {
        map = L.map('map').setView([lat, lon], 6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(map);
    } else {
        map.setView([lat, lon], 6);
    }
    loadRadarLayer();
}

function loadRadarLayer() {
    // Radar frame timestamps change over time (RainViewer refreshes
    // every ~10 minutes), so we re-fetch on every search rather than
    // caching the frame list once.
    fetch('/api/radar')
        .then(response => response.json())
        .then(data => {
            if (radarLayer) {
                map.removeLayer(radarLayer);
            }
            const latestFrame = data.past_frames[data.past_frames.length - 1];
            // RainViewer's documented tile URL pattern:
            // {host}{path}/{size}/{z}/{x}/{y}/{color}/{options}.png
            const tileUrl = `${data.host}${latestFrame.path}/256/{z}/{x}/{y}/2/1_1.png`;
            radarLayer = L.tileLayer(tileUrl, { opacity: 0.6 }).addTo(map);
        })
        .catch(() => {
            // If radar fails, the rest of the page must keep working -
            // we just skip the overlay instead of throwing.
            console.warn('Radar layer could not be loaded.');
        });
}

function renderWeather(data) {
    document.getElementById('city-name').textContent = `${data.city}, ${data.country}`;
    document.getElementById('temperature').textContent = `${Math.round(data.current.temperature)}\u00B0C`;
    document.getElementById('description').textContent = data.current.weather_description;
    document.getElementById('weather-icon').src =
        `https://openweathermap.org/img/wn/${data.current.icon}@2x.png`;

    document.getElementById('feels-like').textContent = `${Math.round(data.current.feels_like)}\u00B0C`;
    document.getElementById('humidity').textContent = `${data.current.humidity}%`;
    document.getElementById('wind').textContent = `${data.current.wind_speed} m/s`;
    document.getElementById('pressure').textContent = `${data.current.pressure} hPa`;
    document.getElementById('visibility').textContent = `${(data.current.visibility / 1000).toFixed(1)} km`;

    const forecastEl = document.getElementById('forecast');
    forecastEl.innerHTML = '';
    data.forecast.forEach(day => {
        const date = new Date(day.datetime);
        const card = document.createElement('div');
        card.className = 'forecast-day';
        card.innerHTML = `
            <p>${date.toLocaleDateString(undefined, { weekday: 'short' })}</p>
            <img src="https://openweathermap.org/img/wn/${day.icon}.png" alt="${day.weather_main}">
            <p>${Math.round(day.temperature)}\u00B0C</p>
        `;
        forecastEl.appendChild(card);
    });

    resultSection.classList.remove('hidden');
    initMap(data.lat, data.lon);
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const city = input.value.trim();
    if (!city) return;

    loading.classList.remove('hidden');
    resultSection.classList.add('hidden');

    try {
        const response = await fetch(`/api/weather?city=${encodeURIComponent(city)}`);
        const data = await response.json();

        if (!response.ok) {
            // The backend always sends { "error": "..." } with a
            // 4xx/5xx status on failure - we show that exact message
            // (e.g. `No city found matching "Lonodn".`) instead of a
            // generic "something went wrong", so the user knows
            // exactly what to fix.
            throw new Error(data.error || 'Something went wrong.');
        }

        renderWeather(data);
    } catch (err) {
        showToast(err.message);
    } finally {
        loading.classList.add('hidden');
    }
});
