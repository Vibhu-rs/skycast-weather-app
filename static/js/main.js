/*
 * main.js
 * -------
 * Search form, rendering weather + forecast, switching the page's
 * "sky" to match conditions, the Leaflet radar map, and error toasts.
 */

const form = document.getElementById('search-form');
const input = document.getElementById('city-input');
const loading = document.getElementById('loading');
const resultSection = document.getElementById('weather-result');
const toast = document.getElementById('toast');

// Leaflet can't create a second map on the same <div>, so these are
// created once and reused across searches.
let map = null;
let radarLayer = null;
let cityMarker = null;
let toastTimer = null;

function showToast(message) {
    toast.textContent = message;
    toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add('hidden'), 4500);
}

// Maps OpenWeatherMap's condition + icon (suffix "d" or "n") to one of
// the sky themes defined in style.css.
function applySky(weatherMain, icon) {
    const night = icon.endsWith('n');
    let sky;
    switch (weatherMain) {
        case 'Clear': sky = night ? 'clear-night' : 'clear-day'; break;
        case 'Clouds': sky = 'clouds'; break;
        case 'Rain':
        case 'Drizzle': sky = 'rain'; break;
        case 'Thunderstorm': sky = 'storm'; break;
        case 'Snow': sky = 'snow'; break;
        default: sky = 'mist'; // Mist, Haze, Fog, Smoke, Dust, etc.
    }
    document.body.dataset.sky = sky;
    // clear-night already has its own dark palette; others get darkened.
    document.body.dataset.night = night && sky !== 'clear-night' ? '1' : '0';
}

function initMap(lat, lon, cityLabel) {
    if (!map) {
        map = L.map('map', { maxZoom: 10 }).setView([lat, lon], 6);
        // Plain OpenStreetMap tiles need no API key. The "base-tiles" class
        // lets style.css darken ONLY this layer, not the radar on top.
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 18,
            className: 'base-tiles',
        }).addTo(map);
        // Separate pane so the radar draws above the (filtered) base map.
        map.createPane('radar').style.zIndex = 250;
    } else {
        map.setView([lat, lon], 6);
    }
    // Pin the searched city so people can see where the radar is centred.
    if (cityMarker) map.removeLayer(cityMarker);
    cityMarker = L.circleMarker([lat, lon], {
        radius: 7, color: '#fff', weight: 2, fillColor: '#ff5a5f', fillOpacity: 1,
    }).addTo(map).bindTooltip(cityLabel, { permanent: true, direction: 'top', offset: [0, -6] });

    // The map was hidden when created/last shown, so Leaflet needs to
    // re-measure its container or it renders grey patches.
    setTimeout(() => map.invalidateSize(), 50);
    loadRadarLayer();
}

function loadRadarLayer() {
    // RainViewer frames refresh every ~10 minutes, so re-fetch each search.
    fetch('/api/radar')
        .then(response => response.json())
        .then(data => {
            if (radarLayer) map.removeLayer(radarLayer);
            const latestFrame = data.past_frames[data.past_frames.length - 1];
            const tileUrl = `${data.host}${latestFrame.path}/256/{z}/{x}/{y}/2/1_1.png`;
            document.getElementById('radar-time').textContent =
                'Radar image from ' + new Date(latestFrame.time * 1000)
                    .toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + '.';
            radarLayer = L.tileLayer(tileUrl, { opacity: 0.75, pane: 'radar', maxNativeZoom: 7 }).addTo(map);
        })
        .catch(() => console.warn('Radar layer could not be loaded.'));
}

const AQI_COLORS = ['#5fd38d', '#f2d45c', '#f5a04a', '#ef6b6b', '#b97ae0', '#c2475d'];
const AQI_ADVICE = [
    'The air is clean. Enjoy time outside.',
    'Fine for most people. Unusually sensitive people may notice effects.',
    'Children, older adults and people with asthma or heart conditions should limit long time outdoors.',
    'Everyone should cut back on hard exercise outside. A fitted N95 mask helps.',
    'Avoid exercising outdoors and keep windows closed.',
    'Stay indoors if you can and run an air purifier.',
];
const POLLUTANTS = [
    ['pm2_5', 'Fine particles (PM2.5)'], ['pm10', 'Coarse particles (PM10)'],
    ['o3', 'Ozone (O\u2083)'], ['no2', 'Nitrogen dioxide (NO\u2082)'],
    ['so2', 'Sulphur dioxide (SO\u2082)'], ['co', 'Carbon monoxide (CO)'],
];

function renderAir(air) {
    const panel = document.getElementById('air');
    const missing = document.getElementById('air-missing');
    if (!air) {
        panel.classList.add('hidden');
        missing.classList.remove('hidden');
        return;
    }
    missing.classList.add('hidden');
    panel.classList.remove('hidden');

    document.getElementById('aqi-value').textContent = air.aqi;
    const label = document.getElementById('aqi-label');
    label.textContent = air.category;
    label.style.color = AQI_COLORS[air.level];
    // The bar spans AQI 0-300; anything worse pins to the right end.
    document.getElementById('aqi-marker').style.left = `${Math.min(air.aqi, 300) / 3}%`;
    document.getElementById('aqi-advice').textContent = AQI_ADVICE[air.level];

    const list = document.getElementById('air-list');
    list.innerHTML = '';
    POLLUTANTS.forEach(([key, name]) => {
        const row = document.createElement('div');
        const dt = document.createElement('dt');
        const dd = document.createElement('dd');
        dt.textContent = name;
        dd.textContent = `${air.pollutants[key]} \u00B5g/m\u00B3`;
        row.append(dt, dd);
        list.appendChild(row);
    });
}

function renderWeather(data) {
    const c = data.current;
    applySky(c.weather_main, c.icon);
    document.body.classList.add('has-result');

    document.getElementById('city-name').textContent = `${data.city}, ${data.country}`;
    document.getElementById('temperature').textContent = Math.round(c.temperature);
    document.getElementById('description').textContent = c.weather_description;
    const icon = document.getElementById('weather-icon');
    icon.src = `https://openweathermap.org/img/wn/${c.icon}@2x.png`;
    icon.alt = c.weather_main;

    document.getElementById('feels-like').textContent = `${Math.round(c.feels_like)}\u00B0C`;
    document.getElementById('humidity').textContent = `${c.humidity}%`;
    document.getElementById('wind').textContent = `${c.wind_speed} m/s`;
    // Wind direction is where the wind comes FROM; the arrow shows where it blows TO.
    document.getElementById('wind-arrow').style.transform = `rotate(${(c.wind_direction || 0) + 180}deg)`;
    document.getElementById('pressure').textContent = `${c.pressure} hPa`;
    document.getElementById('visibility').textContent = `${(c.visibility / 1000).toFixed(1)} km`;

    const forecastEl = document.getElementById('forecast');
    forecastEl.innerHTML = '';
    data.forecast.forEach(day => {
        const date = new Date(day.datetime);
        const el = document.createElement('div');
        el.className = 'forecast-day';

        const wd = document.createElement('p');
        wd.className = 'wd';
        wd.textContent = date.toLocaleDateString(undefined, { weekday: 'short' });

        const img = document.createElement('img');
        img.src = `https://openweathermap.org/img/wn/${day.icon}@2x.png`;
        img.alt = day.weather_main;

        const t = document.createElement('p');
        t.className = 't';
        t.textContent = `${Math.round(day.temperature)}\u00B0`;

        el.append(wd, img, t);
        forecastEl.appendChild(el);
    });

    resultSection.classList.remove('hidden');
    renderAir(data.air_quality);
    initMap(data.lat, data.lon, data.city);
}

async function search(city, place) {
    loading.classList.remove('hidden');
    resultSection.classList.add('hidden');

    try {
        let url = `/api/weather?city=${encodeURIComponent(city)}`;
        // A picked suggestion carries exact coordinates, so we don't re-guess the place.
        if (place) url += `&lat=${place.lat}&lon=${place.lon}&country=${encodeURIComponent(place.country)}`;
        const response = await fetch(url);
        const data = await response.json();
        // The backend sends { "error": "..." } on failure; show it as-is.
        if (!response.ok) throw new Error(data.error || 'Something went wrong.');
        renderWeather(data);
    } catch (err) {
        showToast(err.message);
        // If a previous result existed, bring it back after a failed search.
        if (document.body.classList.contains('has-result')) {
            resultSection.classList.remove('hidden');
        }
    } finally {
        loading.classList.add('hidden');
    }
}

form.addEventListener('submit', (event) => {
    event.preventDefault();
    const city = input.value.trim();
    closeSuggestions();
    if (city) search(city);
});

// --- Autocomplete ---------------------------------------------------
const list = document.getElementById('suggestions');
let suggestions = [];
let activeIndex = -1;
let debounceTimer = null;
let inflight = null;

function closeSuggestions() {
    list.classList.add('hidden');
    list.innerHTML = '';
    suggestions = [];
    activeIndex = -1;
    input.setAttribute('aria-expanded', 'false');
}

function setActive(index) {
    activeIndex = index;
    [...list.children].forEach((li, i) => li.setAttribute('aria-selected', String(i === index)));
}

function pick(place) {
    input.value = place.name;
    closeSuggestions();
    search(place.name, place);
}

function renderSuggestions(places) {
    suggestions = places;
    list.innerHTML = '';
    if (!places.length) { closeSuggestions(); return; }
    places.forEach((place, i) => {
        const li = document.createElement('li');
        li.setAttribute('role', 'option');
        li.setAttribute('aria-selected', 'false');
        const name = document.createElement('span');
        name.textContent = place.name;
        const where = document.createElement('small');
        where.textContent = [place.state, place.country].filter(Boolean).join(', ');
        li.append(name, where);
        // mousedown (not click) so it fires before the input loses focus
        li.addEventListener('mousedown', (e) => { e.preventDefault(); pick(place); });
        li.addEventListener('mousemove', () => setActive(i));
        list.appendChild(li);
    });
    activeIndex = -1;
    list.classList.remove('hidden');
    input.setAttribute('aria-expanded', 'true');
}

async function fetchSuggestions(query) {
    if (inflight) inflight.abort();           // drop stale requests
    inflight = new AbortController();
    try {
        const response = await fetch(`/api/suggest?q=${encodeURIComponent(query)}`, { signal: inflight.signal });
        if (!response.ok) return closeSuggestions();
        renderSuggestions(await response.json());
    } catch (err) {
        if (err.name !== 'AbortError') closeSuggestions();
    }
}

input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const query = input.value.trim();
    if (query.length < 2) { closeSuggestions(); return; }
    debounceTimer = setTimeout(() => fetchSuggestions(query), 250);
});

input.addEventListener('keydown', (e) => {
    if (list.classList.contains('hidden')) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((activeIndex + 1) % suggestions.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((activeIndex - 1 + suggestions.length) % suggestions.length); }
    else if (e.key === 'Enter' && activeIndex >= 0) { e.preventDefault(); pick(suggestions[activeIndex]); }
    else if (e.key === 'Escape') closeSuggestions();
});

input.addEventListener('blur', closeSuggestions);

document.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', () => {
        input.value = chip.textContent;
        search(chip.textContent);
    });
});
