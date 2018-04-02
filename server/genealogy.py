from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_restful import Resource, Api
import sqlite3
from json import dumps
import urllib
import json
import config
import queue
import threading
import time

#e = create_engine('sqlite:///database.s3db')
db = sqlite3.connect("database.s3db")

app = Flask(__name__)
api = Api(app)

geocode_queue = queue.Queue()

queueProcessEvent = threading.Event()
def process_queue():
    db = sqlite3.connect("database.s3db")
    while not queueProcessEvent.is_set():
        address = geocode_queue.get()

        #response = urllib.request.urlopen("https://maps.googleapis.com/maps/api/geocode/json?address=" + urllib.parse.quote_plus(address) + "&key=" + config.gmaps_api_key)
        #content = response.read().decode(response.headers.get_content_charset())
        #json_data = json.loads(content)
        json_data = {"status": "TOO_MANY_REQUESTS"}

        print(address, flush=True)
        time.sleep(0.1)

        if (json_data["status"] == "OK"):
            values = [address,json_data["results"][0]["geometry"]["location"]["lat"], json_data["results"][0]["geometry"]["location"]["lng"], True, "google"]
            cur = db.cursor()
            #cur.execute("insert into geocodes (address, latitude, longitude, valid, source) values (?, ?, ?, ?, ?)", values)
        elif (json_data["status"] == "ZERO_RESULTS"):
            values = [address, False, "google"]
            cur = db.cursor()
            #cur.execute("insert into geocodes (address, valid, source) values (?, ?, ?)", values)
        elif (json_data["status"] == "UNKNOWN_ERROR"):
            # Retry on unknown error
            geocode_queue.put(address)
        elif (json_data["status"] == "OVER_QUERY_LIMIT"):
            # Wait for 6 hrs
            time.sleep(60 * 60 * 6)
        elif (json_data["status"] == "INVALID_REQUEST"):
            # Skip the bad value
            pass

        geocode_queue.task_done()

class GeocodePost(Resource):
    def get(self):
        return ""
    def post(self):
        json_data = request.get_json(force=True)
        cur = db.cursor()

        locations_list = []

        queue_size = geocode_queue.qsize()

        for i, address in enumerate(json_data):
            result = cur.execute("select count(*) from geocodes where address=?", (address,)).fetchone()
            if (result[0] == 0):
                geocode_queue.put(address)
            else:
                location = cur.execute("select latitude, longitude from geocodes where address=? and valid", (address,)).fetchone()
                if (location != None):
                    locations_list.append({"address":address, "latitude":location[0], "longitude":location[1]})
        
        print("Queue size is now approx " + str(geocode_queue.qsize()))
        return jsonify(locations_list)

class Geocode(Resource):
    def get(self, address):
        print(address)
        cur = db.cursor()
        query = cur.execute("select * from geocodes where address=?", (address,))
        # Query the result and get cursor.Dumping that data to a JSON is looked by extension
        result = {'data': [dict(zip(tuple(query.keys()), i)) for i in query.cursor]}
        return result
        # We can have PUT,DELETE,POST here. But in our API GET implementation is sufficient

class QueueStatus(Resource):
    def get(self):
        return jsonify({"queue_size": geocode_queue.qsize()})

api.add_resource(Geocode, '/geocode/<string:address>')
api.add_resource(GeocodePost, '/geocodepost')
api.add_resource(QueueStatus, '/queuestatus')

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

if __name__ == '__main__':
    #app.run()
    t = threading.Thread(target=process_queue, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=8001)