"use strict";

//--------------------------------------------------
// Globals
//--------------------------------------------------

var Genealogy = {
	heatmapData: {
		max: 1,
		min: 0,
		data: []
	},	
	baseLayer: L.tileLayer(
		'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			attribution: 'Daniel Hedren 2018',
			maxZoom: 18
		}
	),	
	heatmapCfg: {
		"radius": 50,
		"maxOpacity": .8,
		"blur": 1,
		"scaleRadius": false,
		"useLocalExtrema": true,
		latField: 'lat',
		lngField: 'lng',
		valueField: 'count'
	},
	birthLayer: L.layerGroup([]),
	residenceLayer: L.layerGroup([]),
	deathLayer: L.layerGroup([]),
	clusterLayer: L.layerGroup([]),
	places: {},
	map: null,
	Persons: [],
	minimumYear: 0,
	maximumYear: 0,
	reloaded: false,
	pickingAddress: null,
	currentStartYear: 0,
	currentEndYear: 0,
	apiUri: "api"
}
Genealogy.heatmapLayer = new HeatmapOverlay(Genealogy.heatmapCfg)

//--------------------------------------------------
// Class definitions
//--------------------------------------------------

class Person {
	constructor() {
		this.givenName = null;
		this.surname = null;
		this.birth = null;
		this.death = null;
		this.sex = null;
		this.events = [];
	}

	addEvent(event) {
		// Do this while waiting for the server in requestPlaces
		// event.year = this.getEventYear(event);
		// event.text = this.getEventText(event);
		
		this.events.push(event);

		if (event.type === "birth") this.birth = event.date;
		else if (event.type === "death") this.death = event.date;
	}

	getEventText(event) {
		var eventStr = this.givenName + " " + this.surname;
		if (event.date != null) eventStr += "<br>" + event.date;
		eventStr += "<br>" + event.place;
		eventStr += "<br><a href=\"#\" onclick=\"pickMissingPlace(\'" + encodeString(event.place) + "\');\">Change location</a></td></tr>"

		return eventStr;
	}

	getEventYear(event) {
		var year = 0;
		if (event.date != null) {
			for (var part of event.date.split(" ")) {
				if (part.length == 4) {
					year = Number(part);
					break;
				}
			}
		}
		return year;
	}
}

//--------------------------------------------------
// File handling
//--------------------------------------------------

function loadDemoData() {
	Genealogy.t0 = performance.now();

	var xmlHttp = new XMLHttpRequest();
	xmlHttp.onreadystatechange = function() { 
		if (xmlHttp.readyState == 4 && xmlHttp.status == 200) {
			parseGED(xmlHttp.response);
		}
	}
	xmlHttp.open("GET", "/EnglishTudorHouse.ged", true); // true for asynchronous
	xmlHttp.send();

	document.getElementById('modal-getstarted').style.display='none';
	document.getElementById('modal-loading').style.display='block';
}

document.addEventListener("DOMContentLoaded", function(event) {
	document.getElementById("file-input").onchange = function(event) {
		var fileList = document.getElementById("file-input").files;
		handleFile(fileList[0]);
	}
});

function dropHandler(ev) {
	ev.preventDefault();

	var file = null;

	if (ev.dataTransfer.items) {
		if (ev.dataTransfer.items[0].kind === 'file') {
			file = ev.dataTransfer.items[0].getAsFile();
		}
	} else {
		file = ev.dataTransfer.files[0];
	}

	handleFile(file);

	removeDragData(ev)
}

function dragOverHandler(ev) {
	ev.preventDefault();
}

function removeDragData(ev) {
	if (ev.dataTransfer.items) {
		ev.dataTransfer.items.clear();
	} else {
		ev.dataTransfer.clearData();
	}
}

function handleFile(file) {
	// TODO: check for correctly formatted GEDCON file instead of .ged extension
	if (file == null || file.name.split(".").pop().toLowerCase() != "ged") return;

	Genealogy.t0 = performance.now();

	var fileReader = new FileReader();
	fileReader.onload = function (e) {
			parseGED(e.target.result);
	};
	fileReader.readAsText(file);

	document.getElementById('modal-getstarted').style.display='none';
	document.getElementById('modal-loading').style.display='block';
}

//--------------------------------------------------
// GEDCOM parsing
//--------------------------------------------------

function parseGED(string) {
	var t0 = performance.now();

	Genealogy.Persons = []
	var lines = string.split('\r\n');
	var places = [];

	for (var i = 0; i < lines.length; i++) {
		if (lines[i].substr(lines[i].length - 4) === "INDI") {
			var p = new Person();
			Genealogy.Persons.push(p);
			var currentTag = null;
			var currentEvent = null;

			while (!(lines[++i].charAt(0) === '0')) {
				var gedconTag = lines[i].substr(2, 4);

				if (gedconTag === "BIRT") {
					currentTag = "BIRT";
					currentEvent = {type: "birth"}
				} else if (gedconTag === "DEAT") {
					currentTag = "DEAT";
					currentEvent = {type: "death"}
				} else if (gedconTag === "RESI") {
					currentTag = "RESI";
					currentEvent = {type: "residence"}
				} else if (gedconTag  === "GIVN") {
					p.givenName = lines[i].substr(7);
				} else if (gedconTag  === "SURN") {
					p.surname = lines[i].substr(7);
				} else if (gedconTag  === "SEX ") {
					p.sex = lines[i].substr(lines[i].length - 1);
				} else if (gedconTag === "DATE") {
					if (currentTag == null || currentEvent == null) {
						// Skip for unimplemented tags
					} else {
						currentEvent.date = lines[i].substr(7);
					}
				} else if (gedconTag === "PLAC") {
					if (currentTag == null || currentEvent == null) {
						// Skip for unimplemented tags
					} else {
						currentEvent.place = lines[i].substr(7);
					}
				} else if (gedconTag === "ADDR") {
					if (currentTag == null || currentEvent == null) {
						// Skip for unimplemented tags
					} else if (currentTag === "RESI") {
						currentEvent.place = lines[i].substr(7);
					}
				}

				// Push an event when the next line is a new tag
				if (currentEvent != null && lines[i + 1].charAt(0) === '1') {
					p.addEvent(Object.assign({}, currentEvent));
					currentEvent = null;
				}
			}

			// Don't consume the ending row -- it might be an INDI
			--i;
		}
	}

	Genealogy.reloaded = false;

	console.log("PERFORMANCE: parseGED took " + (performance.now() - t0) + " milliseconds.")

	requestPlaces();
}

//--------------------------------------------------
// Data handling
//--------------------------------------------------

function encodeString(string) {
	string = encodeURI(string)
	string = string.replace("'", "%AAA");
	string = string.replace('"', "%AAB");
	return string;
}

function decodeString(string) {
	string = string.replace("%AAA", "'");
	string = string.replace("%AAB", '"');
	string = decodeURI(string)
	return string
}

function requestPlaces() {
	var t0 = performance.now();

	var places = [];

	for (var p in Genealogy.Persons) {
		for (var e in Genealogy.Persons[p].events) {
			if (Genealogy.Persons[p].events[e].place != null) {
				places.push(Genealogy.Persons[p].events[e].place.toLowerCase());
			}
		}
	}

	var xmlHttp = new XMLHttpRequest();
	xmlHttp.onreadystatechange = function() {
		if (xmlHttp.readyState == 4 && xmlHttp.status == 200) {
			console.log("PERFORMANCE: requestPlaces:xmlHttp took " + (performance.now() - t0) + " milliseconds.")
			var jsonResponse;

			// Break if response is unparseable
			try {
				jsonResponse = JSON.parse(xmlHttp.response);
			} catch (e) {
				return;
			}

			if (!Genealogy.reloaded && jsonResponse.queue_current != -1 && jsonResponse.queue_current < jsonResponse.queue_target) {
				setTimeout(function() {
					queuePoller(jsonResponse.queue_target)
				}, 1000);
			}
			
			for (var location in jsonResponse.data) {
				Genealogy.places[jsonResponse.data[location].address] = [Number(jsonResponse.data[location].latitude), Number(jsonResponse.data[location].longitude)];
			}

			receivedPlacesCallback();
		}
	}
	xmlHttp.open("POST", Genealogy.apiUri + "/geocodepost", true); // true for asynchronous
	xmlHttp.setRequestHeader("Content-Type", "application/json");
	xmlHttp.send(JSON.stringify(places));

	// Do some stuff here, we have about 15ms before the server responds

	Genealogy.minimumYear = 10000;
	Genealogy.maximumYear = -1;

	for (var p in Genealogy.Persons) {
		for (var e in Genealogy.Persons[p].events) {
			var event = Genealogy.Persons[p].events[e];

			event.year = Genealogy.Persons[p].getEventYear(event);
			event.text = Genealogy.Persons[p].getEventText(event);

			if (event.year != 0) {
				if (event.year > Genealogy.maximumYear) Genealogy.maximumYear = event.year;
				if (event.year < Genealogy.minimumYear) Genealogy.minimumYear = event.year;
			}
		}
	}

	document.getElementById("dateStart").min = Genealogy.minimumYear;
	document.getElementById("dateStart").max = Genealogy.maximumYear;
	document.getElementById("dateRange").max = Genealogy.maximumYear - Genealogy.minimumYear;
	document.getElementById("dateRange").value = document.getElementById("dateRange").max;

	console.log("PERFORMANCE: requestPlaces took " + (performance.now() - t0) + " milliseconds.")
}

function receivedPlacesCallback() {
	// Update the interface first and defer the stuff we don't care about as much
	onSliderUpdate();

	var t0 = performance.now();

	var missingPlaces = [];

	for (var person of Genealogy.Persons) {
		for (var event of person.events) {
			if (event.place != null && Genealogy.places[event.place.toLowerCase()] == null && !missingPlaces.includes(event.place) ) {
				missingPlaces.push(event.place);
			}
		}
	}

	printInfo(missingPlaces.length + " missing places.");

	var str = "";
	for (var place of missingPlaces) {
		str += "<tr id=\'" + encodeString(place) + "\'><td>" + place + "</td><td><a title=\"You will be prompted to place this location on the map\" href=\"#\" onclick=\"pickMissingPlace(\'" + encodeString(place) + "\');\">Place on map</a></td></tr>";
	}
	document.getElementById("places-table-tbody").innerHTML = str;

	console.log("PERFORMANCE: receivedPlacesCallback took " + (performance.now() - t0) + " milliseconds.")
}

function onFilterChange() {
	console.log(document.getElementById("filter-input").value);

	var missingPlaces = [];

	var regexp = new RegExp(".*" + document.getElementById("filter-input").value.toLowerCase() + ".*");

	for (var person of Genealogy.Persons) {
		for (var event of person.events) {
			if (event.place != null && Genealogy.places[event.place.toLowerCase()] == null && !missingPlaces.includes(event.place) && regexp.test(event.place.toLowerCase())) {
				missingPlaces.push(event.place);
			}
		}
	}

	var str = "";
	for (var place of missingPlaces) {
		str += "<tr id=\'" + encodeString(place) + "\'><td>" + place + "</td><td><a title=\"You will be prompted to place this location on the map\" href=\"#\" onclick=\"pickMissingPlace(\'" + encodeString(place) + "\');\">Place on map</a></td></tr>";
	}

	document.getElementById("places-table-tbody").innerHTML = str;
}

function queuePoller(queue_target) {
	var xmlHttp = new XMLHttpRequest();
	xmlHttp.onreadystatechange = function() { 
		if (xmlHttp.readyState == 4 && xmlHttp.status == 200) {
			var jsonResponse;

			// Break if response is unparseable
			try {
				jsonResponse = JSON.parse(xmlHttp.response);
			} catch (e) {
				return;
			}

			if (jsonResponse.status === "OK" && jsonResponse.queue_current != -1 && jsonResponse.queue_current < queue_target) {
				printInfo("Fetching additional places (" + (queue_target - jsonResponse.queue_current) + " remaining)");
				setTimeout(function() {
					queuePoller(queue_target)
				}, 1000);
			} else {
				if (jsonResponse.status === "OK") {
					printInfo("Place fetching status: " + jsonResponse.status)
				}
				if (!Genealogy.reloaded) {
					Genealogy.reloaded = true;
					printInfo("Reloading data")
					requestPlaces()
				}
			}
		}
	}
	xmlHttp.open("GET", Genealogy.apiUri + "/queue_status", true); // true for asynchronous
	xmlHttp.send();
}

function pickMissingPlace(address) {
	document.getElementById("places-tab").style.display = "none";
	document.getElementById("map-tab").style.display = "block";
	document.getElementById("map-tab-button").className += " active";
	document.getElementById("places-tab-button").className = "tab-btn";

	var tr = document.getElementById(address);
	if (tr != null) tr.style.backgroundColor = "var(--accolor)";

	Genealogy.pickingAddress = decodeString(address);
	printInfo("Right click on the map to set the location of " + decodeString(address));
}

function updateLayers(startYear=Genealogy.currentStartYear, endYear=Genealogy.currentEndYear) {
	var t0 = performance.now();
	
	Genealogy.currentStartYear = startYear;
	Genealogy.currentEndYear = endYear;

	Genealogy.heatmapData.data = [];

	Genealogy.clusterMarkers = L.markerClusterGroup();

	for (var person of Genealogy.Persons) {
		for (var event of person.events) {
			// Update map lists
			if (event.date == null || (event.year >= startYear && event.year <= endYear)) {
				if (event.place != null && Genealogy.places[event.place.toLowerCase()] != null) {
					var placeLower = event.place.toLowerCase();

					if (event.type === "birth") {
						if (Genealogy.map.hasLayer(Genealogy.birthLayer)) {
							Genealogy.clusterMarkers.addLayer(L.marker([
								Genealogy.places[placeLower][0],
								Genealogy.places[placeLower][1]
							]).bindPopup(event.text)
							);
						}

						Genealogy.heatmapData.data.push({lat: Genealogy.places[placeLower][0], lng: Genealogy.places[placeLower][1]})
					} else if (event.type === "death") {
						if (Genealogy.map.hasLayer(Genealogy.deathLayer)) {
							Genealogy.clusterMarkers.addLayer(L.marker([
								Genealogy.places[placeLower][0],
								Genealogy.places[placeLower][1]
							]).bindPopup(event.text)
							);
						}

						Genealogy.heatmapData.data.push({lat: Genealogy.places[placeLower][0], lng: Genealogy.places[placeLower][1]})
					} else if (event.type === "residence") {
						if (Genealogy.map.hasLayer(Genealogy.residenceLayer)) {
							Genealogy.clusterMarkers.addLayer(L.marker([
								Genealogy.places[placeLower][0],
								Genealogy.places[placeLower][1]
							]).bindPopup(event.text)
							);
						}
					}
				}
			}
		}
	}

	console.log("PERFORMANCE: updateLayers loop took " + (performance.now() - t0) + " milliseconds.")

	Genealogy.clusterLayer.clearLayers();
	if (Genealogy.map.hasLayer(Genealogy.birthLayer) || Genealogy.map.hasLayer(Genealogy.residenceLayer) || Genealogy.map.hasLayer(Genealogy.deathLayer)) {
		Genealogy.clusterLayer.addLayer(Genealogy.clusterMarkers);
	}

	if (Genealogy.map.hasLayer(Genealogy.heatmapLayer)) {
		Genealogy.heatmapLayer.setData(Genealogy.heatmapData);
	}

	console.log("PERFORMANCE: updateLayers took " + (performance.now() - t0) + " milliseconds.")

	if (Genealogy.t0 != null) {
		document.getElementById('modal-loading').style.display='none';
		console.log("PERFORMANCE: GEDCOM load took " + (performance.now() - Genealogy.t0) + " milliseconds.")
		Genealogy.t0 = null;
	}
}

//--------------------------------------------------
// UI
//--------------------------------------------------

function printInfo(text) {
	document.getElementById("info-span").innerHTML = text + "<br>" + document.getElementById("info-span").innerHTML;
}

function toggleSidebar() {
	if (document.getElementById("missing-places").style.display === "none") {
		document.getElementById("missing-places").style.display = "block";
		document.getElementById("map-canvas").style.width = "calc(80vw - 10px)"
	} else {
		document.getElementById("missing-places").style.display = "none";
		document.getElementById("map-canvas").style.width = "100%"
	}
}

function onSliderUpdate() {
	var date = Number(document.getElementById("dateStart").value);
	var range = Number(document.getElementById("dateRange").value);

	if (date + range > Genealogy.maximumYear) range = Genealogy.maximumYear - date;

	updateLayers(date, date + range);
	document.getElementById("header").innerHTML = "Genealogy map " + date + "-" + (date + range);
}

function onOverlayAdd(e) {
	updateLayers();
}

document.addEventListener("DOMContentLoaded", function(event) {
	Genealogy.map = new L.Map('map-canvas', {
		preferCanvas: true,
		center: new L.LatLng(55, 30),
		zoom: 4,
		layers: [Genealogy.baseLayer, Genealogy.heatmapLayer, Genealogy.clusterLayer]
	});

	Genealogy.heatmapLayer.setData(Genealogy.heatmapData);
	L.control.layers(null, {
		"Heatmap": Genealogy.heatmapLayer,
		"Births": Genealogy.birthLayer,
		"Residence": Genealogy.residenceLayer,
		"Deaths": Genealogy.deathLayer
	}).addTo(Genealogy.map);

	Genealogy.map.on("contextmenu", function (event) {
		if (Genealogy.pickingAddress == null) return;
		Genealogy.places[Genealogy.pickingAddress.toLowerCase()] = [event.latlng.lat, event.latlng.lng];

		var xmlHttp = new XMLHttpRequest();
		xmlHttp.open("POST", Genealogy.apiUri + "/geocode_insert", true); // true for asynchronous
		xmlHttp.setRequestHeader("Content-Type", "application/json");
		xmlHttp.send(JSON.stringify({"address": Genealogy.pickingAddress, "latitude": event.latlng.lat, "longitude": event.latlng.lng}));

		Genealogy.pickingAddress = null;
		printInfo("Location set");
		updateLayers(Genealogy.currentStartYear, Genealogy.currentEndYear);
	});

	Genealogy.map.on('overlayadd', onOverlayAdd);
	Genealogy.map.on('overlayremove', onOverlayAdd);

	document.getElementById("dateStart").onchange = function() {
		onSliderUpdate();
	}

	document.getElementById("dateStart").oninput = function() {
		onSliderUpdate();
	}

	document.getElementById("dateRange").onchange = function() {
		onSliderUpdate();
	}

	document.getElementById("dateRange").oninput = function() {
		onSliderUpdate();
	}

	document.getElementById("places-tab-button").onclick = function() {
		document.getElementById("places-tab").style.display = "block";
		//document.getElementById("map-tab").style.display = "none";
		document.getElementById("map-tab-button").className = "tab-btn";
		document.getElementById("places-tab-button").className += " active";
	}

	document.getElementById("map-tab-button").onclick = function() {
		document.getElementById("places-tab").style.display = "none";
		//document.getElementById("map-tab").style.display = "block";
		document.getElementById("map-tab-button").className += " active";
		document.getElementById("places-tab-button").className = "tab-btn";
	}
});
