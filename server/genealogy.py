from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_restful import Resource, Api
from json import dumps
import urllib
import json
import config
import queue
import threading
import time
import logging
<<<<<<< HEAD
import psycopg2
=======
>>>>>>> 4a8ccf8b01ac532629b04798353ef3904ef71371

logging.basicConfig(filename="genealogy.log", level=logging.DEBUG)
logging.debug("Log started")

<<<<<<< HEAD
db = psycopg2.connect(config.postgres_connection_string)

with db.cursor() as cur:
    cur.execute("CREATE TABLE IF NOT EXISTS geocodes (address VARCHAR(100) PRIMARY KEY, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, valid BOOLEAN, source VARCHAR(50));")
    cur.execute("CREATE TABLE IF NOT EXISTS geocodes_pending (id BIGSERIAL PRIMARY KEY, address VARCHAR(100) UNIQUE, status SMALLINT);")
    db.commit()
=======
db = sqlite3.connect("database.s3db", check_same_thread=False)
>>>>>>> 4a8ccf8b01ac532629b04798353ef3904ef71371

app = Flask(__name__)
api = Api(app)

geocode_queue = queue.Queue()
geocode_queue_done = 0
queueProcessEvent = threading.Event()
queueProcessLock = threading.Lock()

def process_queue():
<<<<<<< HEAD
    db = psycopg2.connect(config.postgres_connection_string)
    logging.debug("Queue processing worker thread started")

=======
    logging.debug("Queue processing worker thread started")
    db = sqlite3.connect("database.s3db")
>>>>>>> 4a8ccf8b01ac532629b04798353ef3904ef71371
    while not queueProcessEvent.is_set() and not geocode_queue.empty():
        logging.debug("Queue processing worker waiting for work")
        address = geocode_queue.get()
        logging.debug("Queue processing worker work started")
        
        try:
            response = urllib.request.urlopen("https://maps.googleapis.com/maps/api/geocode/json?address=" + urllib.parse.quote_plus(address) + "&key=" + config.gmaps_api_key)
            logging.debug("Response sent")
        except urllib.error.HTTPError:
            global geocode_queue_done
            geocode_queue_done += 1
            geocode_queue.task_done()
            continue
        
        logging.debug("Response no error")

        content = response.read().decode(response.headers.get_content_charset())
        json_data = json.loads(content)

<<<<<<< HEAD
=======
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

>>>>>>> 4a8ccf8b01ac532629b04798353ef3904ef71371
        if (json_data["status"] == "OK"):
            values = [address,json_data["results"][0]["geometry"]["location"]["lat"], json_data["results"][0]["geometry"]["location"]["lng"], True, "google"]
            cur = db.cursor()
            cur.execute("INSERT INTO geocodes (address, latitude, longitude, valid, source) VALUES (?, ?, ?, ?, ?);", values)
            db.commit()
        elif (json_data["status"] == "ZERO_RESULTS"):
            values = [address, False, "google"]
            cur = db.cursor()
            cur.execute("INSERT INTO geocodes (address, valid, source) VALUES (?, ?, ?);", values)
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

        logging.debug("Queue processing worker task done")

        global geocode_queue_done
        geocode_queue_done += 1
        geocode_queue.task_done()

<<<<<<< HEAD
    logging.debug("Queue processing worker finished")
    db.close()

process_queue_workers = []
=======
        logging.debug("Queue result worker task done")
        geocode_result_queue.task_done()

    logging.debug("Queue result worker finished")

process_queue_workers = []
process_result_worker = None
>>>>>>> 4a8ccf8b01ac532629b04798353ef3904ef71371

class GeocodePost(Resource):
    def get(self):
        return ""
    def post(self):
        json_data = request.get_json(force=True)
        cur = db.cursor()

        locations_list = []

        queue_added = 0

        for i, address in enumerate(json_data):
<<<<<<< HEAD
            result = cur.execute("select count(*) from geocodes where address=?;", (address,)).fetchone()
            if (result[0] == 0 and address != ""):
                cur.execute("INSERT INTO geocodes_pending (address, status) VALUES (?, ?) IF NOT EXISTS (SELECT address FROM geocodes WHERE address=?) ON CONFLICT DO NOTHING;", (address, 0, address))
                db.commit()
=======
            result = cur.execute("select count(*) from geocodes where address=?", (address,)).fetchone()
            if (result[0] == 0 and address != ""):
                geocode_queue.put(address)
                queue_added += 1
>>>>>>> 4a8ccf8b01ac532629b04798353ef3904ef71371
            else:
                location = cur.execute("SELECT latitude, longitude FROM geocodes WHERE address=? AND valid;", (address,)).fetchone()
                if (location != None):
                    locations_list.append({"address":address, "latitude":location[0], "longitude":location[1]})
        
<<<<<<< HEAD
        queue_size = cur.execute("SELECT COUNT(*) FROM geocodes_pending;").fetchone()
        logging.debug("Queue size is now approx " + str(queue_size))
=======
        logging.debug("Queue size is now approx " + str(geocode_queue.qsize()))
>>>>>>> 4a8ccf8b01ac532629b04798353ef3904ef71371

        if geocode_queue.qsize() > 0:
            for i in range(0, 1):
                process_queue_workers.append(threading.Thread(target=process_queue, daemon=False))
                process_queue_workers[len(process_queue_workers) - 1].start()

<<<<<<< HEAD
=======
            process_result_worker = threading.Thread(target=process_queue_results, daemon=False)
            process_result_worker.start()

>>>>>>> 4a8ccf8b01ac532629b04798353ef3904ef71371
        return jsonify({"queue_done": geocode_queue_done, "queue_target": geocode_queue_done + queue_added, "data": locations_list})

class Geocode(Resource):
    def get(self, address):
        cur = db.cursor()
        query = cur.execute("SELECT * FROM geocodes WHERE address=?", (address,))
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