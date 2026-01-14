"use strict";

/**
 * Streaming GeoJSON Loader with Progress Feedback
 *
 * MINIFICATION:
 * After editing this file, regenerate the minified version:
 *   npx terser streaming-geojson.js -o streaming-geojson.min.js -c -m
 *
 * Or using online tools like https://javascript-minifier.com/
 * 
 * Fetches GeoJSON data from a streaming endpoint and provides progress updates.
 * Works with the CachedGeoJSONMixin streaming response.
 * 
 * Usage:
 *   const loader = new StreamingGeoJSONLoader({
 *     onProgress: (loaded, total) => updateProgressBar(loaded, total),
 *     onComplete: (geojson) => renderFeatures(geojson),
 *     onError: (error) => displayErrorMessage(error)
 *   });
 *   loader.fetch(url);
 */

class StreamingGeoJSONLoader {
    constructor(options = {}) {
        this.onProgress = options.onProgress || (() => { });
        this.onComplete = options.onComplete || (() => { });
        this.onError = options.onError || console.error;
        this.abortController = null;
    }

    abort() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
    }

    async fetch(url) {
        this.abort();
        this.abortController = new AbortController();

        try {
            const response = await fetch(url, {
                signal: this.abortController.signal,
                headers: { 'Accept': 'application/geo+json, application/json' }
            });

            if (!response.ok) {
                // Handle rate limiting (429) with specific error message
                if (response.status === 429) {
                    const retryAfter = response.headers.get('Retry-After');
                    const waitTime = retryAfter ? parseInt(retryAfter, 10) : 60;
                    const error = new Error(
                        `Rate limit exceeded. Please wait ${waitTime} seconds before trying again.`
                    );
                    error.isRateLimited = true;
                    error.retryAfter = waitTime;
                    throw error;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const totalCount = parseInt(response.headers.get('X-Total-Count') || '0', 10);
            const cacheStatus = response.headers.get('X-Cache-Status') || 'UNKNOWN';
            const contentLength = parseInt(response.headers.get('Content-Length') || '0', 10);
            const dataVersion = response.headers.get('X-Data-Version') || null;

            console.log(`GeoJSON response: cache=${cacheStatus}, total=${totalCount}, contentLength=${contentLength}, version=${dataVersion}`);

            // If not streaming or small dataset, use regular JSON parsing
            if (cacheStatus !== 'STREAM' || totalCount <= 100) {
                const data = await response.json();
                this.onProgress(totalCount, totalCount);
                this.onComplete(data, dataVersion);
                return data;
            }

            // Streaming response - parse incrementally
            return await this._parseStreamingResponse(response, totalCount, contentLength, dataVersion);

        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('GeoJSON fetch aborted');
                return null;
            }
            this.onError(error);
            throw error;
        }
    }

    async _parseStreamingResponse(response, totalCount, contentLength = 0, dataVersion = null) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        const features = [];
        let bytesReceived = 0;

        // Report initial progress
        this.onProgress(0, totalCount);

        // Parser state - GeoJSON structure is: {"type":"FeatureCollection","features":[{...},{...}]}
        // braceDepth 0 = outside, 1 = inside FeatureCollection, 2 = inside a Feature
        let braceDepth = 0;
        let bracketDepth = 0;
        let inString = false;
        let escapeNext = false;
        let featureStart = -1;

        try {
            let chunkCount = 0;
            while (true) {
                const { done, value } = await reader.read();

                if (done) break;

                chunkCount++;
                bytesReceived += value.length;
                const chunk = decoder.decode(value, { stream: true });

                // Estimate average bytes per feature for progress calculation
                // Typical GeoJSON feature is ~2-5KB, use 3KB as estimate
                const estimatedBytesPerFeature = contentLength > 0 ? contentLength / totalCount : 3000;
                const estimatedProgress = Math.min(
                    Math.round(bytesReceived / estimatedBytesPerFeature),
                    totalCount
                );

                // Update progress on every chunk based on bytes received
                this.onProgress(estimatedProgress, totalCount);

                console.log(`Chunk ${chunkCount}: ${chunk.length} bytes, total: ${bytesReceived}, est progress: ${estimatedProgress}/${totalCount}`);

                // Process each character in the chunk
                for (let i = 0; i < chunk.length; i++) {
                    const char = chunk[i];
                    buffer += char;

                    // Handle escape sequences in strings
                    if (escapeNext) {
                        escapeNext = false;
                        continue;
                    }

                    if (char === '\\' && inString) {
                        escapeNext = true;
                        continue;
                    }

                    // Toggle string state
                    if (char === '"') {
                        inString = !inString;
                        continue;
                    }

                    // Skip if inside a string
                    if (inString) continue;

                    // Track bracket depth for features array
                    if (char === '[') {
                        bracketDepth++;
                    } else if (char === ']') {
                        bracketDepth--;
                    }

                    // Track brace depth for feature extraction
                    // Features are objects inside the features array (bracketDepth >= 1)
                    if (char === '{') {
                        braceDepth++;
                        // Start of a feature: we're at depth 2 (inside FeatureCollection, inside features array)
                        if (braceDepth === 2 && bracketDepth >= 1) {
                            featureStart = buffer.length - 1;
                        }
                    } else if (char === '}') {
                        // End of a feature
                        if (braceDepth === 2 && bracketDepth >= 1 && featureStart >= 0) {
                            const featureStr = buffer.substring(featureStart);
                            try {
                                const feature = JSON.parse(featureStr);
                                if (feature.type === 'Feature') {
                                    features.push(feature);
                                    this.onProgress(features.length, totalCount);
                                }
                            } catch (e) {
                                console.warn('Failed to parse feature:', e);
                            }
                            // Clear processed data from buffer to save memory
                            buffer = '';
                            featureStart = -1;
                        }
                        braceDepth--;
                    }
                }
            }

            // Handle any remaining data
            decoder.decode(); // Flush

            const geojson = {
                type: 'FeatureCollection',
                features: features
            };

            this.onProgress(features.length, totalCount);
            this.onComplete(geojson, dataVersion);
            return geojson;

        } catch (error) {
            this.onError(error);
            throw error;
        }
    }
}

/**
 * Progress bar helper for map loading
 */
function createMapProgressBar(containerId = 'map-progress-container') {
    let container = document.getElementById(containerId);

    if (!container) {
        // Create progress container if it doesn't exist
        container = document.createElement('div');
        container.id = containerId;
        container.className = 'position-absolute top-50 start-50 translate-middle';
        container.style.cssText = 'z-index: 1000; width: 300px; display: none;';
        container.innerHTML = `
            <div class="card shadow">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between mb-1">
                        <small class="text-muted">Loading map data...</small>
                        <small class="text-muted" id="map-progress-text">0%</small>
                    </div>
                    <div class="progress" style="height: 8px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                             role="progressbar" 
                             id="map-progress-bar"
                             style="width: 0%"
                             aria-valuenow="0" 
                             aria-valuemin="0" 
                             aria-valuemax="100">
                        </div>
                    </div>
                    <small class="text-muted" id="map-progress-count"></small>
                </div>
            </div>
        `;

        // Append to map container if available
        const mapContainer = document.getElementById('map') || document.body;
        mapContainer.style.position = 'relative';
        mapContainer.appendChild(container);
    }

    return {
        show() {
            container.style.display = 'block';
        },
        hide() {
            container.style.display = 'none';
        },
        update(loaded, total) {
            const percent = total > 0 ? Math.round((loaded / total) * 100) : 0;
            const bar = document.getElementById('map-progress-bar');
            const text = document.getElementById('map-progress-text');
            const count = document.getElementById('map-progress-count');

            if (bar) {
                bar.style.width = `${percent}%`;
                bar.setAttribute('aria-valuenow', percent);
            }
            if (text) {
                text.textContent = `${percent}%`;
            }
            if (count) {
                count.textContent = `${loaded.toLocaleString()} / ${total.toLocaleString()} features`;
            }
        }
    };
}

/**
 * Enhanced fetchFeatureGeometries with streaming support and progress
 * 
 * Drop-in replacement for the standard fetchFeatureGeometries function.
 * Falls back to regular fetch for cached responses.
 */
async function fetchFeatureGeometriesWithProgress(params) {
    hideMapOverlay();

    const finalParams = mapConfig.featuresId ? { id: mapConfig.featuresId } : params;
    const url = buildUrl(mapConfig.featuresLayerGeometriesUrl, finalParams);
    const cacheKey = normalizeUrl(url);

    console.log('Fetching features with progress for URL:', url);

    // Check local cache first (getFromIndexedDB returns full entry object with .data property)
    try {
        const cached = await getFromIndexedDB(cacheKey);
        if (cached && cached.data) {
            console.log('Cache hit for feature data');
            renderFeatures(cached.data);
            return;
        }
    } catch (e) {
        console.warn('IndexedDB cache check failed:', e);
    }

    // Create progress bar
    const progressBar = createMapProgressBar();
    progressBar.show();
    progressBar.update(0, 0);

    const loader = new StreamingGeoJSONLoader({
        onProgress: (loaded, total) => {
            progressBar.update(loaded, total);
        },
        onComplete: async (geojson, version) => {
            progressBar.hide();

            // Cache the result with version for future validation
            try {
                await storeInIndexedDB(cacheKey, geojson, version);
                await cleanupCache();
            } catch (e) {
                console.warn('Failed to cache GeoJSON:', e);
            }

            renderFeatures(geojson);
        },
        onError: (error) => {
            progressBar.hide();
            console.error('Error fetching feature geometries:', error);

            // Display user-friendly message for rate limiting
            if (error.isRateLimited) {
                const message = `Too many requests. Please wait ${error.retryAfter} seconds and try again.`;
                if (typeof displayErrorMessage === 'function') {
                    displayErrorMessage({ message });
                } else {
                    alert(message);
                }
            } else if (typeof displayErrorMessage === 'function') {
                displayErrorMessage(error);
            }
        }
    });

    try {
        await loader.fetch(url);
    } catch (error) {
        progressBar.hide();
        throw error;
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.StreamingGeoJSONLoader = StreamingGeoJSONLoader;
    window.createMapProgressBar = createMapProgressBar;
    window.fetchFeatureGeometriesWithProgress = fetchFeatureGeometriesWithProgress;
}
