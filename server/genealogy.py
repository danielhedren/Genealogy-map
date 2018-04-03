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
import logging

logging.basicConfig(filename="genealogy.log", level=logging.DEBUG)
logging.debug("Log started")

db = sqlite3.connect("database.s3db", check_same_thread=False)

app = Flask(__name__)
api = Api(app)

geocode_queue = queue.Queue()
geocode_queue_done = 0
queueProcessEvent = threading.Event()
queueProcessLock = threading.Lock()
geocode_result_queue = queue.Queue()

def process_queue():
    logging.debug("Queue processing worker thread started")
    db = sqlite3.connect("database.s3db")
    while not queueProcessEvent.is_set() and not geocode_queue.empty():
        logging.debug("Queue processing worker waiting for work")
        address = geocode_queue.get()
        logging.debug("Queue processing worker work started")
        
        try:
            response = urllib.request.urlopen("https://maps.googleapis.com/maps/api/geocode/json?address=" + urllib.parse.quote_plus(address) + "&key=" + config.gmaps_api_key)
            logging.debug("Response sent")
        except urllib.error.HTTPError:
            geocode_queue.task_done()
            geocode_result_queue.put({"json_data": {"status": "INVALID_REQUEST"}, "address": address})
            continue
        
        logging.debug("Response no error")

        content = response.read().decode(response.headers.get_content_charset())
        json_data = json.loads(content)

        geocode_result_queue.put({"json_data": json_data, "address": address})

        logging.debug("Queue processing worker task done")
        geocode_queue.task_done()

    logging.debug("Queue processing worker finished")

def process_queue_results():
    logging.debug("Queue processing worker thread started")
    db = sqlite3.connect("database.s3db")
    while not queueProcessEvent.is_set() and not (geocode_result_queue.empty() and geocode_queue.empty()):
        logging.debug("Queue result worker waiting for work")

        data = geocode_result_queue.get()
        address = data["address"]
        json_data = data["json_data"]

        if (json_data["status"] == "OK"):
            values = [address,json_data["results"][0]["geometry"]["location"]["lat"], json_data["results"][0]["geometry"]["location"]["lng"], True, "google"]
            cur = db.cursor()
            cur.execute("insert into geocodes (address, latitude, longitude, valid, source) values (?, ?, ?, ?, ?)", values)
            db.commit()
        elif (json_data["status"] == "ZERO_RESULTS"):
            values = [address, False, "google"]
            cur = db.cursor()
            cur.execute("insert into geocodes (address, valid, source) values (?, ?, ?)", values)
            db.commit()
        elif (json_data["status"] == "UNKNOWN_ERROR"):
            # Retry on unknown error
            # geocode_queue.put(address)
            pass
        elif (json_data["status"] == "OVER_QUERY_LIMIT"):
            # Kill the threads
            queueProcessEvent.set()
        elif (json_data["status"] == "INVALID_REQUEST"):
            # Skip the bad value
            pass

        global geocode_queue_done
        geocode_queue_done += 1

        logging.debug("Queue result worker task done")
        geocode_result_queue.task_done()

    logging.debug("Queue result worker finished")

process_queue_workers = []
process_result_worker = None

class GeocodePost(Resource):
    def get(self):
        return ""
    def post(self):
        json_data = request.get_json(force=True)
        cur = db.cursor()

        locations_list = []

        queue_added = 0

        for i, address in enumerate(json_data):
            result = cur.execute("select count(*) from geocodes where address=?", (address,)).fetchone()
            if (result[0] == 0 and address != ""):
                geocode_queue.put(address)
                queue_added += 1
            else:
                location = cur.execute("select latitude, longitude from geocodes where address=? and valid", (address,)).fetchone()
                if (location != None):
                    locations_list.append({"address":address, "latitude":location[0], "longitude":location[1]})
        
        logging.debug("Queue size is now approx " + str(geocode_queue.qsize()))

        if geocode_queue.qsize() > 0:
            for i in range(0, 1):
                process_queue_workers.append(threading.Thread(target=process_queue, daemon=False))
                process_queue_workers[len(process_queue_workers) - 1].start()

            process_result_worker = threading.Thread(target=process_queue_results, daemon=False)
            process_result_worker.start()

        return jsonify({"queue_done": geocode_queue_done, "queue_target": geocode_queue_done + queue_added, "data": locations_list})

class Geocode(Resource):
    def get(self, address):
        cur = db.cursor()
        query = cur.execute("select * from geocodes where address=?", (address,))
        # Query the result and get cursor.Dumping that data to a JSON is looked by extension
        result = {'data': [dict(zip(tuple(query.keys()), i)) for i in query.cursor]}
        return result
        # We can have PUT,DELETE,POST here. But in our API GET implementation is sufficient

class QueueStatus(Resource):
    def get(self):
        return jsonify({"queue_size": geocode_queue.qsize(), "queue_done": geocode_queue_done})

api.add_resource(Geocode, '/api/geocode/<string:address>')
api.add_resource(GeocodePost, '/api/geocodepost')
api.add_resource(QueueStatus, '/api/queue_status')

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

if __name__ == '__main__':
    app.run()