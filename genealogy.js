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
	map: null,
	Persons: []
}
Genealogy.heatmapLayer = new HeatmapOverlay(Genealogy.heatmapCfg)

//--------------------------------------------------
// Class definitions
//--------------------------------------------------

class Person {
	constructor(name) {
		this.name = name;
		this.birth = None;
		this.death = None;
		this.events = [];
	}

	addEvent(v_type, v_location, v_year) {
		this.events.push({type: v_type, location: v_location, year:v_year});

		if (v_type == "birth") this.birth = v_year;
		else if (v_type == "death") this.death = v_year;
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
	var lines = string.split('\r\n');
	var dates = [];
	var places = [];

	console.log(lines.length);
	for (var i = 0; i < lines.length; i++) {
		if (lines[i].substr(0, 6).localeCompare("1 BIRT") == 0) {
			var place, date;

			do {
				i++;
				if (lines[i].substr(0, 6).localeCompare("2 PLAC") == 0) {
					place = lines[i].substr(7);
				} else if (lines[i].substr(0, 6).localeCompare("2 DATE") == 0) {
					date = lines[i].substr(7);
				}
			} while (lines[i].substr(0, 1).localeCompare("2") == 0);

			if (place != null && date != null) {
				places.push(place);
				dates.push(date);
			}
		}
	}

	var placesUnique = places.filter(function (item, pos, self) {
		return self.indexOf(item) == pos;
	});

	console.log(placesUnique.length);

	var xmlHttp = new XMLHttpRequest();
	xmlHttp.onreadystatechange = function() { 
		if (xmlHttp.readyState == 4 && xmlHttp.status == 200)
			var jsonResponse = JSON.parse(xmlHttp.response);
			
			Genealogy.heatmapData.data = [];
			
			for (var location in jsonResponse) {
				Genealogy.heatmapData.data.push({lat: Number(jsonResponse[location].latitude), lng: Number(jsonResponse[location].longitude), count: 1})
			}

			Genealogy.heatmapLayer.setData(Genealogy.heatmapData);
	}
	xmlHttp.open("POST", "http://localhost:5000/geocodepost", true); // true for asynchronous
	xmlHttp.setRequestHeader("Content-Type", "application/json");
	xmlHttp.send(JSON.stringify(placesUnique));
}

//--------------------------------------------------
// Heatmap
//--------------------------------------------------

$(document).ready(function () {
	Genealogy.map = new L.Map('map-canvas', {
		center: new L.LatLng(25.6586, -80.3568),
		zoom: 4,
		layers: [Genealogy.baseLayer, Genealogy.heatmapLayer]
	});

	Genealogy.heatmapLayer.setData(Genealogy.heatmapData);
});