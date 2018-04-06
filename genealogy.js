//gmaps geocoding api key AIzaSyBeD23MFIgJeouDljUSiMq1cBHqR9IfncY

//https://maps.googleapis.com/maps/api/geocode/json?address=Fjärdebäck,+Böja,+Mariestad&key=AIzaSyBeD23MFIgJeouDljUSiMq1cBHqR9IfncY

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
		'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
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
		this.events.push(event);

		if (event.type.localeCompare("birth") == 0) this.birth = event.date;
		else if (event.type.localeCompare("death") == 0) this.death = event.date;
	}

	getEventText(event) {
		var eventStr = this.givenName + " " + this.surname;
		if (event.date != null) eventStr += "<br>" + event.date;
		eventStr += "<br>" + event.place;

		return eventStr;
	}

	getEventDate(event) {
		var date = 0;
		if (event.date != null) {
			for (var part of event.date.split(" ")) {
				if (part.length == 4) {
					date = Number(part);
					break;
				}
			}
		}
		return Number(date);
	}
}

//--------------------------------------------------
// Drag and drop handling
//--------------------------------------------------

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

	// TODO: check for correctly formatted GEDCON file instead of .ged extension
	if (file == null || file.name.split(".").pop().toLowerCase() != "ged") return;

	var fileReader = new FileReader();
	fileReader.onload = (function (file) {
		return function (e) {
			parseGED(e.target.result);
		};
	})(file);
	fileReader.readAsText(file);

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

//--------------------------------------------------
// GEDCOM parsing
//--------------------------------------------------

function parseGED(string) {
	Genealogy.Persons = []
	var lines = string.split('\r\n');
	var dates = [];
	var places = [];

	for (var i = 0; i < lines.length; i++) {
		if (lines[i].substr(lines[i].length - 4).localeCompare("INDI") == 0) {
			var p = new Person();
			Genealogy.Persons.push(p);
			var currentTag = null;
			var currentEvent = null;

			while (lines[++i].substr(0, 1).localeCompare("0") != 0) {
				var gedconTag = lines[i].split(" ")[1];

				if (gedconTag.localeCompare("BIRT") == 0) {
					currentTag = "BIRT";
					currentEvent = {type: "birth"}
				} else if (gedconTag.localeCompare("DEAT") == 0) {
					currentTag = "DEAT";
					currentEvent = {type: "death"}
				} else if (gedconTag.localeCompare("RESI") == 0) {
					currentTag = "RESI";
					currentEvent = {type: "residence"}
				} else if (gedconTag.localeCompare("GIVN") == 0) {
					p.givenName = lines[i].substr(7);
				} else if (gedconTag.localeCompare("SURN") == 0) {
					p.surname = lines[i].substr(7);
				} else if (gedconTag.localeCompare("SEX") == 0) {
					p.sex = lines[i].substr(lines[i].length - 1);
				} else if (gedconTag.localeCompare("DATE") == 0) {
					if (currentTag == null || currentEvent == null) {
						// Skip for unimplemented tags
					} else {
						currentEvent.date = lines[i].substr(7);
					}
				} else if (gedconTag.localeCompare("PLAC") == 0) {
					if (currentTag == null || currentEvent == null) {
						// Skip for unimplemented tags
					} else {
						currentEvent.place = lines[i].substr(7);
					}
				} else if (gedconTag.localeCompare("ADDR") == 0) {
					if (currentTag == null || currentEvent == null) {
						// Skip for unimplemented tags
					} else if (currentTag.localeCompare("RESI") == 0) {
						currentEvent.place = lines[i].substr(7);
					}
				}

				// Push an event when the next line is a new tag
				if (lines[i + 1].substr(0, 1).localeCompare("1") == 0 && currentEvent != null) {
					p.addEvent(Object.assign({}, currentEvent));
					currentEvent = null;
				}
			}

			// Don't consume the ending row -- it might be an INDI
			--i;
		}
	}

	Genealogy.reloaded = false;
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
	var places = [];

	for (var p in Genealogy.Persons) {
		for (var e in Genealogy.Persons[p].events) {
			var event = Genealogy.Persons[p].events[e];
			if (event.place != null && !places.includes(event.place)) {
				places.push(event.place);
			}
		}
	}

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

			if (jsonResponse.queue_current != -1 && jsonResponse.queue_current < queue_target) {
				printInfo("Fetching additional places (" + (queue_target - jsonResponse.queue_current) + " remaining)");
				setTimeout(function() {
					queuePoller(queue_target)
				}, 1000);
			} else {
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

function receivedPlacesCallback() {
	Genealogy.minimumYear = 10000;
	Genealogy.maximumYear = -1;

	var missingPlaces = [];

	for (var person of Genealogy.Persons) {
		for (var event of person.events) {
			var eventDate = person.getEventDate(event);
			if (eventDate != 0) {
				if (eventDate > Genealogy.maximumYear) Genealogy.maximumYear = eventDate;
				if (eventDate < Genealogy.minimumYear) Genealogy.minimumYear = eventDate;
			}

			if (event.place != null && !missingPlaces.includes(event.place) && Genealogy.places[event.place] == null) {
				missingPlaces.push(event.place);
			}
		}
	}

	document.getElementById("dateStart").min = Genealogy.minimumYear;
	document.getElementById("dateStart").max = Genealogy.maximumYear;
	document.getElementById("dateRange").max = Genealogy.maximumYear - Genealogy.minimumYear;
	document.getElementById("dateRange").value = document.getElementById("dateRange").max;

	printInfo(missingPlaces.length + " missing places.");

	var str = "";
	for (var place of missingPlaces) {
		str += "<tr id=\'" + encodeString(place) + "\'><td>" + place + "</td><td><a href=\"#\" onclick=\"pickMissingPlace(\'" + encodeString(place) + "\');\">Pick on map</a></td></tr>";
	}
	document.getElementById("places-table-tbody").innerHTML = str;

	onSliderUpdate();
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

function updateLayers(startYear, endYear) {
	Genealogy.currentStartYear = startYear;
	Genealogy.currentEndYear = endYear;

	Genealogy.heatmapData.data = [];
	Genealogy.birthMarkers = [];
	Genealogy.residenceMarkers = [];
	Genealogy.deathMarkers = [];

	for (var person of Genealogy.Persons) {
		for (var event of person.events) {
			// Update map lists
			if (event.date == null || (person.getEventDate(event) >= startYear && person.getEventDate(event) <= endYear)) {
				if (event.place != null && Genealogy.places[event.place] != null) {
					if (event.type.localeCompare("birth") == 0) {
						Genealogy.birthMarkers.push(L.marker([
							Genealogy.places[event.place][0],
							Genealogy.places[event.place][1]
						]).bindPopup(person.getEventText(event)
						+ "<br><a href=\"#\" onclick=\"pickMissingPlace(\'" + encodeString(event.place) + "\');\">Change location</a></td></tr>"
					));

						Genealogy.heatmapData.data.push({lat: Genealogy.places[event.place][0], lng: Genealogy.places[event.place][1], count: 1})
					} else if (event.type.localeCompare("death") == 0) {
						Genealogy.deathMarkers.push(L.marker([
							Genealogy.places[event.place][0],
							Genealogy.places[event.place][1]
						]).bindPopup(person.getEventText(event)
						+ "<br><a href=\"#\" onclick=\"pickMissingPlace(\'" + encodeString(event.place) + "\');\">Change location</a></td></tr>"
					));

						Genealogy.heatmapData.data.push({lat: Genealogy.places[event.place][0], lng: Genealogy.places[event.place][1], count: 1})
					} else if (event.type.localeCompare("residence") == 0) {
						Genealogy.residenceMarkers.push(L.marker([
							Genealogy.places[event.place][0],
							Genealogy.places[event.place][1]
						]).bindPopup(person.getEventText(event)
						+ "<br><a href=\"#\" onclick=\"pickMissingPlace(\'" + encodeString(event.place) + "\');\">Change location</a></td></tr>"
					));

					}
				}
			}
		}
	}

	Genealogy.birthLayer.clearLayers();
	Genealogy.birthLayer.addLayer(L.layerGroup(Genealogy.birthMarkers));

	Genealogy.residenceLayer.clearLayers();
	Genealogy.residenceLayer.addLayer(L.layerGroup(Genealogy.residenceMarkers));

	Genealogy.deathLayer.clearLayers();
	Genealogy.deathLayer.addLayer(L.layerGroup(Genealogy.deathMarkers));

	Genealogy.heatmapLayer.setData(Genealogy.heatmapData);
}

//--------------------------------------------------
// UI
//--------------------------------------------------

function printInfo(text) {
	document.getElementById("info-span").innerHTML = text + "<br>" + document.getElementById("info-span").innerHTML;
}

function toggleSidebar() {
	if (document.getElementById("missing-places").style.display.localeCompare("none") == 0) {
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
	document.getElementById("date-text").innerHTML = "Anno " + date + " to " + (date + range) + " (" + range + " years)";
}

$(document).ready(function () {
	Genealogy.map = new L.Map('map-canvas', {
		center: new L.LatLng(55, 30),
		zoom: 4,
		layers: [Genealogy.baseLayer, Genealogy.heatmapLayer]
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
		Genealogy.places[Genealogy.pickingAddress] = [event.latlng.lat, event.latlng.lng];

		var xmlHttp = new XMLHttpRequest();
		xmlHttp.open("POST", Genealogy.apiUri + "/geocode_insert", true); // true for asynchronous
		xmlHttp.setRequestHeader("Content-Type", "application/json");
		xmlHttp.send(JSON.stringify({"address": Genealogy.pickingAddress, "latitude": event.latlng.lat, "longitude": event.latlng.lng}));

		Genealogy.pickingAddress = null;
		printInfo("Location set");
		updateLayers(Genealogy.currentStartYear, Genealogy.currentEndYear);
	});

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
		document.getElementById("map-tab").style.display = "none";
		document.getElementById("map-tab-button").className = "tab-btn";
		document.getElementById("places-tab-button").className += " active";
	}

	document.getElementById("map-tab-button").onclick = function() {
		document.getElementById("places-tab").style.display = "none";
		document.getElementById("map-tab").style.display = "block";
		document.getElementById("map-tab-button").className += " active";
		document.getElementById("places-tab-button").className = "tab-btn";
	}
});