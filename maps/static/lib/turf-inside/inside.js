"use strict"; 
(function(f) {
    if (typeof exports === "object" && typeof module !== "undefined") {
        module.exports = f();
    } else if (typeof define === "function" && define.amd) {
        define([], f);
    } else {
        let g;
        if (typeof window !== "undefined") {
            g = window;
        } else if (typeof global !== "undefined") {
            g = global;
        } else if (typeof self !== "undefined") {
            g = self;
        } else {
            g = this;
        }
        g.turf = f();
    }
})(function() {
    let define, module, exports;
    return (function() {
        function r(e, n, t) {
            function o(i, f) {
                if (!n[i]) {
                    if (!e[i]) {
                        const c = "function" === typeof require && require;
                        if (!f && c) {
                            return c(i, !0);
                        }
                        if (u) {
                            return u(i, !0);
                        }
                        const a = new Error("Cannot find module '" + i + "'");
                        throw a.code = "MODULE_NOT_FOUND", a;
                    }
                    const p = n[i] = {exports: {}};
                    e[i][0].call(p.exports, function(r) {
                        const n = e[i][1][r];
                        return o(n || r);
                    }, p, p.exports, r, e, n, t);
                }
                return n[i].exports;
            }

            for (var u = "function" === typeof require && require, i = 0; i < t.length; i++) {
                o(t[i]);
            }
            return o;
        }

        return r;
    })()({
        1: [function(require, module, exports) {
            module.exports = {
                inside: require('@turf/inside'),
            };
        }, {"@turf/inside": 3}], 2: [function(require, module, exports) {

            Object.defineProperty(exports, '__esModule', {value: true});

            /**
             * Earth Radius used with the Harvesine formula and approximates using a spherical (non-ellipsoid) Earth.
             */
            const earthRadius = 6371008.8;

            /**
             * Unit of measurement factors using a spherical (non-ellipsoid) earth radius.
             */
            const factors = {
                meters: earthRadius,
                metres: earthRadius,
                millimeters: earthRadius * 1000,
                millimetres: earthRadius * 1000,
                centimeters: earthRadius * 100,
                centimetres: earthRadius * 100,
                kilometers: earthRadius / 1000,
                kilometres: earthRadius / 1000,
                miles: earthRadius / 1609.344,
                nauticalmiles: earthRadius / 1852,
                inches: earthRadius * 39.370,
                yards: earthRadius / 1.0936,
                feet: earthRadius * 3.28084,
                radians: 1,
                degrees: earthRadius / 111325,
            };

            /**
             * Units of measurement factors based on 1 meter.
             */
            const unitsFactors = {
                meters: 1,
                metres: 1,
                millimeters: 1000,
                millimetres: 1000,
                centimeters: 100,
                centimetres: 100,
                kilometers: 1 / 1000,
                kilometres: 1 / 1000,
                miles: 1 / 1609.344,
                nauticalmiles: 1 / 1852,
                inches: 39.370,
                yards: 1 / 1.0936,
                feet: 3.28084,
                radians: 1 / earthRadius,
                degrees: 1 / 111325,
            };

            /**
             * Area of measurement factors based on 1 square meter.
             */
            const areaFactors = {
                meters: 1,
                metres: 1,
                millimeters: 1000000,
                millimetres: 1000000,
                centimeters: 10000,
                centimetres: 10000,
                kilometers: 0.000001,
                kilometres: 0.000001,
                acres: 0.000247105,
                miles: 3.86e-7,
                yards: 1.195990046,
                feet: 10.763910417,
                inches: 1550.003100006
            };

            /**
             * Wraps a GeoJSON {@link Geometry} in a GeoJSON {@link Feature}.
             *
             * @name feature
             * @param {Geometry} geometry input geometry
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the Feature
             * @returns {Feature} a GeoJSON Feature
             * @example
             * var geometry = {
             *   "type": "Point",
             *   "coordinates": [110, 50]
             * };
             *
             * var feature = turf.feature(geometry);
             *
             * //=feature
             */
            function feature(geometry, properties, options) {
                // Optional Parameters
                options = options || {};
                if (!isObject(options)) {
                    throw new Error('options is invalid');
                }
                const bbox = options.bbox;
                const id = options.id;

                // Validation
                if (geometry === undefined) {
                    throw new Error('geometry is required');
                }
                if (properties && properties.constructor !== Object) {
                    throw new Error('properties must be an Object');
                }
                if (bbox) {
                    validateBBox(bbox);
                }
                if (id) {
                    validateId(id);
                }

                // Main
                const feat = {type: 'Feature'};
                if (id) {
                    feat.id = id;
                }
                if (bbox) {
                    feat.bbox = bbox;
                }
                feat.properties = properties || {};
                feat.geometry = geometry;
                return feat;
            }

            /**
             * Creates a GeoJSON {@link Geometry} from a Geometry string type & coordinates.
             * For GeometryCollection type use `helpers.geometryCollection`
             *
             * @name geometry
             * @param {string} type Geometry Type
             * @param {Array<number>} coordinates Coordinates
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Geometry
             * @returns {Geometry} a GeoJSON Geometry
             * @example
             * var type = 'Point';
             * var coordinates = [110, 50];
             *
             * var geometry = turf.geometry(type, coordinates);
             *
             * //=geometry
             */
            function geometry(type, coordinates, options) {
                // Optional Parameters
                options = options || {};
                if (!isObject(options)) {
                    throw new Error('options is invalid');
                }
                const bbox = options.bbox;

                // Validation
                if (!type) {
                    throw new Error('type is required');
                }
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }
                if (!Array.isArray(coordinates)) {
                    throw new Error('coordinates must be an Array');
                }
                if (bbox) {
                    validateBBox(bbox);
                }

                // Main
                let geom;
                switch (type) {
                case 'Point':
                    geom = point(coordinates).geometry;
                    break;
                case 'LineString':
                    geom = lineString(coordinates).geometry;
                    break;
                case 'Polygon':
                    geom = polygon(coordinates).geometry;
                    break;
                case 'MultiPoint':
                    geom = multiPoint(coordinates).geometry;
                    break;
                case 'MultiLineString':
                    geom = multiLineString(coordinates).geometry;
                    break;
                case 'MultiPolygon':
                    geom = multiPolygon(coordinates).geometry;
                    break;
                default:
                    throw new Error(type + ' is invalid');
                }
                if (bbox) {
                    geom.bbox = bbox;
                }
                return geom;
            }

            /**
             * Creates a {@link Point} {@link Feature} from a Position.
             *
             * @name point
             * @param {Array<number>} coordinates longitude, latitude position (each in decimal degrees)
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the Feature
             * @returns {Feature<Point>} a Point feature
             * @example
             * var point = turf.point([-75.343, 39.984]);
             *
             * //=point
             */
            function point(coordinates, properties, options) {
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }
                if (!Array.isArray(coordinates)) {
                    throw new Error('coordinates must be an Array');
                }
                if (coordinates.length < 2) {
                    throw new Error('coordinates must be at least 2 numbers long');
                }
                if (!isNumber(coordinates[0]) || !isNumber(coordinates[1])) {
                    throw new Error('coordinates must contain numbers');
                }

                return feature({
                    type: 'Point', coordinates: coordinates
                }, properties, options);
            }

            /**
             * Creates a {@link Point} {@link FeatureCollection} from an Array of Point coordinates.
             *
             * @name points
             * @param {Array<Array<number>>} coordinates an array of Points
             * @param {Object} [properties={}] Translate these properties to each Feature
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the FeatureCollection
             * @param {string|number} [options.id] Identifier associated with the FeatureCollection
             * @returns {FeatureCollection<Point>} Point Feature
             * @example
             * var points = turf.points([
             *   [-75, 39],
             *   [-80, 45],
             *   [-78, 50]
             * ]);
             *
             * //=points
             */
            function points(coordinates, properties, options) {
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }
                if (!Array.isArray(coordinates)) {
                    throw new Error('coordinates must be an Array');
                }

                return featureCollection(coordinates.map(function(coords) {
                    return point(coords, properties);
                }), options);
            }

            /**
             * Creates a {@link Polygon} {@link Feature} from an Array of LinearRings.
             *
             * @name polygon
             * @param {Array<Array<Array<number>>>} coordinates an array of LinearRings
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the Feature
             * @returns {Feature<Polygon>} Polygon Feature
             * @example
             * var polygon = turf.polygon([[[-5, 52], [-4, 56], [-2, 51], [-7, 54], [-5, 52]]], { name: 'poly1' });
             *
             * //=polygon
             */
            function polygon(coordinates, properties, options) {
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }

                for (let i = 0; i < coordinates.length; i++) {
                    const ring = coordinates[i];
                    if (ring.length < 4) {
                        throw new Error('Each LinearRing of a Polygon must have 4 or more Positions.');
                    }
                    for (let j = 0; j < ring[ring.length - 1].length; j++) {
                        // Check if first point of Polygon contains two numbers
                        if (i === 0 && j === 0 && !isNumber(ring[0][0]) || !isNumber(ring[0][1])) {
                            throw new Error('coordinates must contain numbers');
                        }
                        if (ring[ring.length - 1][j] !== ring[0][j]) {
                            throw new Error('First and last Position are not equivalent.');
                        }
                    }
                }

                return feature({
                    type: 'Polygon', coordinates: coordinates
                }, properties, options);
            }

            /**
             * Creates a {@link Polygon} {@link FeatureCollection} from an Array of Polygon coordinates.
             *
             * @name polygons
             * @param {Array<Array<Array<Array<number>>>>} coordinates an array of Polygon coordinates
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the FeatureCollection
             * @returns {FeatureCollection<Polygon>} Polygon FeatureCollection
             * @example
             * var polygons = turf.polygons([
             *   [[[-5, 52], [-4, 56], [-2, 51], [-7, 54], [-5, 52]]],
             *   [[[-15, 42], [-14, 46], [-12, 41], [-17, 44], [-15, 42]]],
             * ]);
             *
             * //=polygons
             */
            function polygons(coordinates, properties, options) {
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }
                if (!Array.isArray(coordinates)) {
                    throw new Error('coordinates must be an Array');
                }

                return featureCollection(coordinates.map(function(coords) {
                    return polygon(coords, properties);
                }), options);
            }

            /**
             * Creates a {@link LineString} {@link Feature} from an Array of Positions.
             *
             * @name lineString
             * @param {Array<Array<number>>} coordinates an array of Positions
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the Feature
             * @returns {Feature<LineString>} LineString Feature
             * @example
             * var linestring1 = turf.lineString([[-24, 63], [-23, 60], [-25, 65], [-20, 69]], {name: 'line 1'});
             * var linestring2 = turf.lineString([[-14, 43], [-13, 40], [-15, 45], [-10, 49]], {name: 'line 2'});
             *
             * //=linestring1
             * //=linestring2
             */
            function lineString(coordinates, properties, options) {
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }
                if (coordinates.length < 2) {
                    throw new Error('coordinates must be an array of two or more positions');
                }
                // Check if first point of LineString contains two numbers
                if (!isNumber(coordinates[0][1]) || !isNumber(coordinates[0][1])) {
                    throw new Error('coordinates must contain numbers');
                }

                return feature({
                    type: 'LineString', coordinates: coordinates
                }, properties, options);
            }

            /**
             * Creates a {@link LineString} {@link FeatureCollection} from an Array of LineString coordinates.
             *
             * @name lineStrings
             * @param {Array<Array<number>>} coordinates an array of LinearRings
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the FeatureCollection
             * @param {string|number} [options.id] Identifier associated with the FeatureCollection
             * @returns {FeatureCollection<LineString>} LineString FeatureCollection
             * @example
             * var linestrings = turf.lineStrings([
             *   [[-24, 63], [-23, 60], [-25, 65], [-20, 69]],
             *   [[-14, 43], [-13, 40], [-15, 45], [-10, 49]]
             * ]);
             *
             * //=linestrings
             */
            function lineStrings(coordinates, properties, options) {
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }
                if (!Array.isArray(coordinates)) {
                    throw new Error('coordinates must be an Array');
                }

                return featureCollection(coordinates.map(function(coords) {
                    return lineString(coords, properties);
                }), options);
            }

            /**
             * Takes one or more {@link Feature|Features} and creates a {@link FeatureCollection}.
             *
             * @name featureCollection
             * @param {Feature[]} features input features
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the Feature
             * @returns {FeatureCollection} FeatureCollection of Features
             * @example
             * var locationA = turf.point([-75.343, 39.984], {name: 'Location A'});
             * var locationB = turf.point([-75.833, 39.284], {name: 'Location B'});
             * var locationC = turf.point([-75.534, 39.123], {name: 'Location C'});
             *
             * var collection = turf.featureCollection([
             *   locationA,
             *   locationB,
             *   locationC
             * ]);
             *
             * //=collection
             */
            function featureCollection(features, options) {
                // Optional Parameters
                options = options || {};
                if (!isObject(options)) {
                    throw new Error('options is invalid');
                }
                const bbox = options.bbox;
                const id = options.id;

                // Validation
                if (!features) {
                    throw new Error('No features passed');
                }
                if (!Array.isArray(features)) {
                    throw new Error('features must be an Array');
                }
                if (bbox) {
                    validateBBox(bbox);
                }
                if (id) {
                    validateId(id);
                }

                // Main
                const fc = {type: 'FeatureCollection'};
                if (id) {
                    fc.id = id;
                }
                if (bbox) {
                    fc.bbox = bbox;
                }
                fc.features = features;
                return fc;
            }

            /**
             * Creates a {@link Feature<MultiLineString>} based on a
             * coordinate array. Properties can be added optionally.
             *
             * @name multiLineString
             * @param {Array<Array<Array<number>>>} coordinates an array of LineStrings
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the Feature
             * @returns {Feature<MultiLineString>} a MultiLineString feature
             * @throws {Error} if no coordinates are passed
             * @example
             * var multiLine = turf.multiLineString([[[0,0],[10,10]]]);
             *
             * //=multiLine
             */
            function multiLineString(coordinates, properties, options) {
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }

                return feature({
                    type: 'MultiLineString', coordinates: coordinates
                }, properties, options);
            }

            /**
             * Creates a {@link Feature<MultiPoint>} based on a
             * coordinate array. Properties can be added optionally.
             *
             * @name multiPoint
             * @param {Array<Array<number>>} coordinates an array of Positions
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the Feature
             * @returns {Feature<MultiPoint>} a MultiPoint feature
             * @throws {Error} if no coordinates are passed
             * @example
             * var multiPt = turf.multiPoint([[0,0],[10,10]]);
             *
             * //=multiPt
             */
            function multiPoint(coordinates, properties, options) {
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }

                return feature({
                    type: 'MultiPoint', coordinates: coordinates
                }, properties, options);
            }

            /**
             * Creates a {@link Feature<MultiPolygon>} based on a
             * coordinate array. Properties can be added optionally.
             *
             * @name multiPolygon
             * @param {Array<Array<Array<Array<number>>>>} coordinates an array of Polygons
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the Feature
             * @returns {Feature<MultiPolygon>} a multipolygon feature
             * @throws {Error} if no coordinates are passed
             * @example
             * var multiPoly = turf.multiPolygon([[[[0,0],[0,10],[10,10],[10,0],[0,0]]]]);
             *
             * //=multiPoly
             *
             */
            function multiPolygon(coordinates, properties, options) {
                if (!coordinates) {
                    throw new Error('coordinates is required');
                }

                return feature({
                    type: 'MultiPolygon', coordinates: coordinates
                }, properties, options);
            }

            /**
             * Creates a {@link Feature<GeometryCollection>} based on a
             * coordinate array. Properties can be added optionally.
             *
             * @name geometryCollection
             * @param {Array<Geometry>} geometries an array of GeoJSON Geometries
             * @param {Object} [properties={}] an Object of key-value pairs to add as properties
             * @param {Object} [options={}] Optional Parameters
             * @param {Array<number>} [options.bbox] Bounding Box Array [west, south, east, north] associated with the Feature
             * @param {string|number} [options.id] Identifier associated with the Feature
             * @returns {Feature<GeometryCollection>} a GeoJSON GeometryCollection Feature
             * @example
             * var pt = {
             *     "type": "Point",
             *       "coordinates": [100, 0]
             *     };
             * var line = {
             *     "type": "LineString",
             *     "coordinates": [ [101, 0], [102, 1] ]
             *   };
             * var collection = turf.geometryCollection([pt, line]);
             *
             * //=collection
             */
            function geometryCollection(geometries, properties, options) {
                if (!geometries) {
                    throw new Error('geometries is required');
                }
                if (!Array.isArray(geometries)) {
                    throw new Error('geometries must be an Array');
                }

                return feature({
                    type: 'GeometryCollection', geometries: geometries
                }, properties, options);
            }

            /**
             * Round number to precision
             *
             * @param {number} num Number
             * @param {number} [precision=0] Precision
             * @returns {number} rounded number
             * @example
             * turf.round(120.4321)
             * //=120
             *
             * turf.round(120.4321, 2)
             * //=120.43
             */
            function round(num, precision) {
                if (num === undefined || num === null || isNaN(num)) {
                    throw new Error('num is required');
                }
                if (precision && !(precision >= 0)) {
                    throw new Error('precision must be a positive number');
                }
                const multiplier = Math.pow(10, precision || 0);
                return Math.round(num * multiplier) / multiplier;
            }

            /**
             * Convert a distance measurement (assuming a spherical Earth) from radians to a more friendly unit.
             * Valid units: miles, nauticalmiles, inches, yards, meters, metres, kilometers, centimeters, feet
             *
             * @name radiansToLength
             * @param {number} radians in radians across the sphere
             * @param {string} [units='kilometers'] can be degrees, radians, miles, or kilometers inches, yards, metres, meters, kilometres, kilometers.
             * @returns {number} distance
             */
            function radiansToLength(radians, units) {
                if (radians === undefined || radians === null) {
                    throw new Error('radians is required');
                }

                if (units && typeof units !== 'string') {
                    throw new Error('units must be a string');
                }
                const factor = factors[units || 'kilometers'];
                if (!factor) {
                    throw new Error(units + ' units is invalid');
                }
                return radians * factor;
            }

            /**
             * Convert a distance measurement (assuming a spherical Earth) from a real-world unit into radians
             * Valid units: miles, nauticalmiles, inches, yards, meters, metres, kilometers, centimeters, feet
             *
             * @name lengthToRadians
             * @param {number} distance in real units
             * @param {string} [units='kilometers'] can be degrees, radians, miles, or kilometers inches, yards, metres, meters, kilometres, kilometers.
             * @returns {number} radians
             */
            function lengthToRadians(distance, units) {
                if (distance === undefined || distance === null) {
                    throw new Error('distance is required');
                }

                if (units && typeof units !== 'string') {
                    throw new Error('units must be a string');
                }
                const factor = factors[units || 'kilometers'];
                if (!factor) {
                    throw new Error(units + ' units is invalid');
                }
                return distance / factor;
            }

            /**
             * Convert a distance measurement (assuming a spherical Earth) from a real-world unit into degrees
             * Valid units: miles, nauticalmiles, inches, yards, meters, metres, centimeters, kilometres, feet
             *
             * @name lengthToDegrees
             * @param {number} distance in real units
             * @param {string} [units='kilometers'] can be degrees, radians, miles, or kilometers inches, yards, metres, meters, kilometres, kilometers.
             * @returns {number} degrees
             */
            function lengthToDegrees(distance, units) {
                return radiansToDegrees(lengthToRadians(distance, units));
            }

            /**
             * Converts any bearing angle from the north line direction (positive clockwise)
             * and returns an angle between 0-360 degrees (positive clockwise), 0 being the north line
             *
             * @name bearingToAzimuth
             * @param {number} bearing angle, between -180 and +180 degrees
             * @returns {number} angle between 0 and 360 degrees
             */
            function bearingToAzimuth(bearing) {
                if (bearing === null || bearing === undefined) {
                    throw new Error('bearing is required');
                }

                let angle = bearing % 360;
                if (angle < 0) {
                    angle += 360;
                }
                return angle;
            }

            /**
             * Converts an angle in radians to degrees
             *
             * @name radiansToDegrees
             * @param {number} radians angle in radians
             * @returns {number} degrees between 0 and 360 degrees
             */
            function radiansToDegrees(radians) {
                if (radians === null || radians === undefined) {
                    throw new Error('radians is required');
                }

                const degrees = radians % (2 * Math.PI);
                return degrees * 180 / Math.PI;
            }

            /**
             * Converts an angle in degrees to radians
             *
             * @name degreesToRadians
             * @param {number} degrees angle between 0 and 360 degrees
             * @returns {number} angle in radians
             */
            function degreesToRadians(degrees) {
                if (degrees === null || degrees === undefined) {
                    throw new Error('degrees is required');
                }

                const radians = degrees % 360;
                return radians * Math.PI / 180;
            }

            /**
             * Converts a length to the requested unit.
             * Valid units: miles, nauticalmiles, inches, yards, meters, metres, kilometers, centimeters, feet
             *
             * @param {number} length to be converted
             * @param {string} originalUnit of the length
             * @param {string} [finalUnit='kilometers'] returned unit
             * @returns {number} the converted length
             */
            function convertLength(length, originalUnit, finalUnit) {
                if (length === null || length === undefined) {
                    throw new Error('length is required');
                }
                if (!(length >= 0)) {
                    throw new Error('length must be a positive number');
                }

                return radiansToLength(lengthToRadians(length, originalUnit), finalUnit || 'kilometers');
            }

            /**
             * Converts a area to the requested unit.
             * Valid units: kilometers, kilometres, meters, metres, centimetres, millimeters, acres, miles, yards, feet, inches
             * @param {number} area to be converted
             * @param {string} [originalUnit='meters'] of the distance
             * @param {string} [finalUnit='kilometers'] returned unit
             * @returns {number} the converted distance
             */
            function convertArea(area, originalUnit, finalUnit) {
                if (area === null || area === undefined) {
                    throw new Error('area is required');
                }
                if (!(area >= 0)) {
                    throw new Error('area must be a positive number');
                }

                const startFactor = areaFactors[originalUnit || 'meters'];
                if (!startFactor) {
                    throw new Error('invalid original units');
                }

                const finalFactor = areaFactors[finalUnit || 'kilometers'];
                if (!finalFactor) {
                    throw new Error('invalid final units');
                }

                return (area / startFactor) * finalFactor;
            }

            /**
             * isNumber
             *
             * @param {*} num Number to validate
             * @returns {boolean} true/false
             * @example
             * turf.isNumber(123)
             * //=true
             * turf.isNumber('foo')
             * //=false
             */
            function isNumber(num) {
                return !isNaN(num) && num !== null && !Array.isArray(num);
            }

            /**
             * isObject
             *
             * @param {*} input variable to validate
             * @returns {boolean} true/false
             * @example
             * turf.isObject({elevation: 10})
             * //=true
             * turf.isObject('foo')
             * //=false
             */
            function isObject(input) {
                return (!!input) && (input.constructor === Object);
            }

            /**
             * Validate BBox
             *
             * @private
             * @param {Array<number>} bbox BBox to validate
             * @returns {void}
             * @throws Error if BBox is not valid
             * @example
             * validateBBox([-180, -40, 110, 50])
             * //=OK
             * validateBBox([-180, -40])
             * //=Error
             * validateBBox('Foo')
             * //=Error
             * validateBBox(5)
             * //=Error
             * validateBBox(null)
             * //=Error
             * validateBBox(undefined)
             * //=Error
             */
            function validateBBox(bbox) {
                if (!bbox) {
                    throw new Error('bbox is required');
                }
                if (!Array.isArray(bbox)) {
                    throw new Error('bbox must be an Array');
                }
                if (bbox.length !== 4 && bbox.length !== 6) {
                    throw new Error('bbox must be an Array of 4 or 6 numbers');
                }
                bbox.forEach(function(num) {
                    if (!isNumber(num)) {
                        throw new Error('bbox must only contain numbers');
                    }
                });
            }

            /**
             * Validate Id
             *
             * @private
             * @param {string|number} id Id to validate
             * @returns {void}
             * @throws Error if Id is not valid
             * @example
             * validateId([-180, -40, 110, 50])
             * //=Error
             * validateId([-180, -40])
             * //=Error
             * validateId('Foo')
             * //=OK
             * validateId(5)
             * //=OK
             * validateId(null)
             * //=Error
             * validateId(undefined)
             * //=Error
             */
            function validateId(id) {
                if (!id) {
                    throw new Error('id is required');
                }
                if (['string', 'number'].indexOf(typeof id) === -1) {
                    throw new Error('id must be a number or a string');
                }
            }

            // Deprecated methods
            function radians2degrees() {
                throw new Error('method has been renamed to `radiansToDegrees`');
            }

            function degrees2radians() {
                throw new Error('method has been renamed to `degreesToRadians`');
            }

            function distanceToDegrees() {
                throw new Error('method has been renamed to `lengthToDegrees`');
            }

            function distanceToRadians() {
                throw new Error('method has been renamed to `lengthToRadians`');
            }

            function radiansToDistance() {
                throw new Error('method has been renamed to `radiansToLength`');
            }

            function bearingToAngle() {
                throw new Error('method has been renamed to `bearingToAzimuth`');
            }

            function convertDistance() {
                throw new Error('method has been renamed to `convertLength`');
            }

            exports.earthRadius = earthRadius;
            exports.factors = factors;
            exports.unitsFactors = unitsFactors;
            exports.areaFactors = areaFactors;
            exports.feature = feature;
            exports.geometry = geometry;
            exports.point = point;
            exports.points = points;
            exports.polygon = polygon;
            exports.polygons = polygons;
            exports.lineString = lineString;
            exports.lineStrings = lineStrings;
            exports.featureCollection = featureCollection;
            exports.multiLineString = multiLineString;
            exports.multiPoint = multiPoint;
            exports.multiPolygon = multiPolygon;
            exports.geometryCollection = geometryCollection;
            exports.round = round;
            exports.radiansToLength = radiansToLength;
            exports.lengthToRadians = lengthToRadians;
            exports.lengthToDegrees = lengthToDegrees;
            exports.bearingToAzimuth = bearingToAzimuth;
            exports.radiansToDegrees = radiansToDegrees;
            exports.degreesToRadians = degreesToRadians;
            exports.convertLength = convertLength;
            exports.convertArea = convertArea;
            exports.isNumber = isNumber;
            exports.isObject = isObject;
            exports.validateBBox = validateBBox;
            exports.validateId = validateId;
            exports.radians2degrees = radians2degrees;
            exports.degrees2radians = degrees2radians;
            exports.distanceToDegrees = distanceToDegrees;
            exports.distanceToRadians = distanceToRadians;
            exports.radiansToDistance = radiansToDistance;
            exports.bearingToAngle = bearingToAngle;
            exports.convertDistance = convertDistance;

        }, {}], 3: [function(require, module, exports) {

            const invariant = require('@turf/invariant');

            // http://en.wikipedia.org/wiki/Even%E2%80%93odd_rule
            // modified from: https://github.com/substack/point-in-polygon/blob/master/index.js
            // which was modified from http://www.ecse.rpi.edu/Homepages/wrf/Research/Short_Notes/pnpoly.html

            /**
             * Takes a {@link Point} and a {@link Polygon} or {@link MultiPolygon} and determines if the point resides inside the polygon. The polygon can
             * be convex or concave. The function accounts for holes.
             *
             * @name inside
             * @param {Feature<Point>} point input point
             * @param {Feature<Polygon|MultiPolygon>} polygon input polygon or multipolygon
             * @param {Object} [options={}] Optional parameters
             * @param {boolean} [options.ignoreBoundary=false] True if polygon boundary should be ignored when determining if the point is inside the polygon otherwise false.
             * @returns {boolean} `true` if the Point is inside the Polygon; `false` if the Point is not inside the Polygon
             * @example
             * var pt = turf.point([-77, 44]);
             * var poly = turf.polygon([[
             *   [-81, 41],
             *   [-81, 47],
             *   [-72, 47],
             *   [-72, 41],
             *   [-81, 41]
             * ]]);
             *
             * turf.inside(pt, poly);
             * //= true
             */
            function inside(point, polygon, options) {
                // Optional parameters
                options = options || {};
                if (typeof options !== 'object') {
                    throw new Error('options is invalid');
                }
                const ignoreBoundary = options.ignoreBoundary;

                // validation
                if (!point) {
                    throw new Error('point is required');
                }
                if (!polygon) {
                    throw new Error('polygon is required');
                }

                const pt = invariant.getCoord(point);
                let polys = invariant.getCoords(polygon);
                const type = (polygon.geometry) ? polygon.geometry.type : polygon.type;
                const bbox = polygon.bbox;

                // Quick elimination if point is not inside bbox
                if (bbox && inBBox(pt, bbox) === false) {
                    return false;
                }

                // normalize to multipolygon
                if (type === 'Polygon') {
                    polys = [polys];
                }

                for (var i = 0, insidePoly = false; i < polys.length && !insidePoly; i++) {
                    // check if it is in the outer ring first
                    if (inRing(pt, polys[i][0], ignoreBoundary)) {
                        let inHole = false;
                        let k = 1;
                        // check for the point in any of the holes
                        while (k < polys[i].length && !inHole) {
                            if (inRing(pt, polys[i][k], !ignoreBoundary)) {
                                inHole = true;
                            }
                            k++;
                        }
                        if (!inHole) {
                            insidePoly = true;
                        }
                    }
                }
                return insidePoly;
            }

            /**
             * inRing
             *
             * @private
             * @param {Array<number>} pt [x,y]
             * @param {Array<Array<number>>} ring [[x,y], [x,y],..]
             * @param {boolean} ignoreBoundary ignoreBoundary
             * @returns {boolean} inRing
             */
            function inRing(pt, ring, ignoreBoundary) {
                let isInside = false;
                if (ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]) {
                    ring = ring.slice(0, ring.length - 1);
                }

                for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
                    const xi = ring[i][0], yi = ring[i][1];
                    const xj = ring[j][0], yj = ring[j][1];
                    const onBoundary = (pt[1] * (xi - xj) + yi * (xj - pt[0]) + yj * (pt[0] - xi) === 0) && ((xi - pt[0]) * (xj - pt[0]) <= 0) && ((yi - pt[1]) * (yj - pt[1]) <= 0);
                    if (onBoundary) {
                        return !ignoreBoundary;
                    }
                    const intersect = ((yi > pt[1]) !== (yj > pt[1])) && (pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi);
                    if (intersect) {
                        isInside = !isInside;
                    }
                }
                return isInside;
            }

            /**
             * inBBox
             *
             * @private
             * @param {Array<number>} pt point [x,y]
             * @param {Array<number>} bbox BBox [west, south, east, north]
             * @returns {boolean} true/false if point is inside BBox
             */
            function inBBox(pt, bbox) {
                return bbox[0] <= pt[0] && bbox[1] <= pt[1] && bbox[2] >= pt[0] && bbox[3] >= pt[1];
            }

            module.exports = inside;
            module.exports.default = inside;

        }, {"@turf/invariant": 4}], 4: [function(require, module, exports) {

            Object.defineProperty(exports, '__esModule', {value: true});

            const helpers = require('@turf/helpers');

            /**
             * Unwrap a coordinate from a Point Feature, Geometry or a single coordinate.
             *
             * @name getCoord
             * @param {Array<number>|Geometry<Point>|Feature<Point>} coord GeoJSON Point or an Array of numbers
             * @returns {Array<number>} coordinates
             * @example
             * var pt = turf.point([10, 10]);
             *
             * var coord = turf.getCoord(pt);
             * //= [10, 10]
             */
            function getCoord(coord) {
                if (!coord) {
                    throw new Error('coord is required');
                }
                if (coord.type === 'Feature' && coord.geometry !== null && coord.geometry.type === 'Point') {
                    return coord.geometry.coordinates;
                }
                if (coord.type === 'Point') {
                    return coord.coordinates;
                }
                if (Array.isArray(coord) && coord.length >= 2 && coord[0].length === undefined && coord[1].length === undefined) {
                    return coord;
                }

                throw new Error('coord must be GeoJSON Point or an Array of numbers');
            }

            /**
             * Unwrap coordinates from a Feature, Geometry Object or an Array
             *
             * @name getCoords
             * @param {Array<any>|Geometry|Feature} coords Feature, Geometry Object or an Array
             * @returns {Array<any>} coordinates
             * @example
             * var poly = turf.polygon([[[119.32, -8.7], [119.55, -8.69], [119.51, -8.54], [119.32, -8.7]]]);
             *
             * var coords = turf.getCoords(poly);
             * //= [[[119.32, -8.7], [119.55, -8.69], [119.51, -8.54], [119.32, -8.7]]]
             */
            function getCoords(coords) {
                if (!coords) {
                    throw new Error('coords is required');
                }

                // Feature
                if (coords.type === 'Feature' && coords.geometry !== null) {
                    return coords.geometry.coordinates;
                }

                // Geometry
                if (coords.coordinates) {
                    return coords.coordinates;
                }

                // Array of numbers
                if (Array.isArray(coords)) {
                    return coords;
                }

                throw new Error('coords must be GeoJSON Feature, Geometry Object or an Array');
            }

            /**
             * Checks if coordinates contains a number
             *
             * @name containsNumber
             * @param {Array<any>} coordinates GeoJSON Coordinates
             * @returns {boolean} true if Array contains a number
             */
            function containsNumber(coordinates) {
                if (coordinates.length > 1 && helpers.isNumber(coordinates[0]) && helpers.isNumber(coordinates[1])) {
                    return true;
                }

                if (Array.isArray(coordinates[0]) && coordinates[0].length) {
                    return containsNumber(coordinates[0]);
                }
                throw new Error('coordinates must only contain numbers');
            }

            /**
             * Enforce expectations about types of GeoJSON objects for Turf.
             *
             * @name geojsonType
             * @param {GeoJSON} value any GeoJSON object
             * @param {string} type expected GeoJSON type
             * @param {string} name name of calling function
             * @throws {Error} if value is not the expected type.
             */
            function geojsonType(value, type, name) {
                if (!type || !name) {
                    throw new Error('type and name required');
                }

                if (!value || value.type !== type) {
                    throw new Error('Invalid input to ' + name + ': must be a ' + type + ', given ' + value.type);
                }
            }

            /**
             * Enforce expectations about types of {@link Feature} inputs for Turf.
             * Internally this uses {@link geojsonType} to judge geometry types.
             *
             * @name featureOf
             * @param {Feature} feature a feature with an expected geometry type
             * @param {string} type expected GeoJSON type
             * @param {string} name name of calling function
             * @throws {Error} error if value is not the expected type.
             */
            function featureOf(feature, type, name) {
                if (!feature) {
                    throw new Error('No feature passed');
                }
                if (!name) {
                    throw new Error('.featureOf() requires a name');
                }
                if (!feature || feature.type !== 'Feature' || !feature.geometry) {
                    throw new Error('Invalid input to ' + name + ', Feature with geometry required');
                }
                if (!feature.geometry || feature.geometry.type !== type) {
                    throw new Error('Invalid input to ' + name + ': must be a ' + type + ', given ' + feature.geometry.type);
                }
            }

            /**
             * Enforce expectations about types of {@link FeatureCollection} inputs for Turf.
             * Internally this uses {@link geojsonType} to judge geometry types.
             *
             * @name collectionOf
             * @param {FeatureCollection} featureCollection a FeatureCollection for which features will be judged
             * @param {string} type expected GeoJSON type
             * @param {string} name name of calling function
             * @throws {Error} if value is not the expected type.
             */
            function collectionOf(featureCollection, type, name) {
                if (!featureCollection) {
                    throw new Error('No featureCollection passed');
                }
                if (!name) {
                    throw new Error('.collectionOf() requires a name');
                }
                if (!featureCollection || featureCollection.type !== 'FeatureCollection') {
                    throw new Error('Invalid input to ' + name + ', FeatureCollection required');
                }
                for (let i = 0; i < featureCollection.features.length; i++) {
                    const feature = featureCollection.features[i];
                    if (!feature || feature.type !== 'Feature' || !feature.geometry) {
                        throw new Error('Invalid input to ' + name + ', Feature with geometry required');
                    }
                    if (!feature.geometry || feature.geometry.type !== type) {
                        throw new Error('Invalid input to ' + name + ': must be a ' + type + ', given ' + feature.geometry.type);
                    }
                }
            }

            /**
             * Get Geometry from Feature or Geometry Object
             *
             * @param {Feature|Geometry} geojson GeoJSON Feature or Geometry Object
             * @returns {Geometry|null} GeoJSON Geometry Object
             * @throws {Error} if geojson is not a Feature or Geometry Object
             * @example
             * var point = {
             *   "type": "Feature",
             *   "properties": {},
             *   "geometry": {
             *     "type": "Point",
             *     "coordinates": [110, 40]
             *   }
             * }
             * var geom = turf.getGeom(point)
             * //={"type": "Point", "coordinates": [110, 40]}
             */
            function getGeom(geojson) {
                if (!geojson) {
                    throw new Error('geojson is required');
                }
                if (geojson.geometry !== undefined) {
                    return geojson.geometry;
                }
                if (geojson.coordinates || geojson.geometries) {
                    return geojson;
                }
                throw new Error('geojson must be a valid Feature or Geometry Object');
            }

            /**
             * Get Geometry Type from Feature or Geometry Object
             *
             * @throws {Error} **DEPRECATED** in v5.0.0 in favor of getType
             */
            function getGeomType() {
                throw new Error('invariant.getGeomType has been deprecated in v5.0 in favor of invariant.getType');
            }

            /**
             * Get GeoJSON object's type, Geometry type is prioritize.
             *
             * @param {GeoJSON} geojson GeoJSON object
             * @param {string} [name="geojson"] name of the variable to display in error message
             * @returns {string} GeoJSON type
             * @example
             * var point = {
             *   "type": "Feature",
             *   "properties": {},
             *   "geometry": {
             *     "type": "Point",
             *     "coordinates": [110, 40]
             *   }
             * }
             * var geom = turf.getType(point)
             * //="Point"
             */
            function getType(geojson, name) {
                if (!geojson) {
                    throw new Error((name || 'geojson') + ' is required');
                }
                // GeoJSON Feature & GeometryCollection
                if (geojson.geometry && geojson.geometry.type) {
                    return geojson.geometry.type;
                }
                // GeoJSON Geometry & FeatureCollection
                if (geojson.type) {
                    return geojson.type;
                }
                throw new Error((name || 'geojson') + ' is invalid');
            }

            exports.getCoord = getCoord;
            exports.getCoords = getCoords;
            exports.containsNumber = containsNumber;
            exports.geojsonType = geojsonType;
            exports.featureOf = featureOf;
            exports.collectionOf = collectionOf;
            exports.getGeom = getGeom;
            exports.getGeomType = getGeomType;
            exports.getType = getType;

        }, {"@turf/helpers": 2}]
    }, {}, [1])(1);
});
