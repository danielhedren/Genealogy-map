from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_restful import Resource, Api
from json import dumps
import json
import config
import logging
import psycopg2
from psycopg2.extras import execute_batch

#logging.basicConfig(filename="genealogy.log", level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)
logging.debug("Log started")

db = psycopg2.connect(config.postgres_connection_string)

with db.cursor() as cur:
    cur.execute("CREATE TABLE IF NOT EXISTS geocodes (address TEXT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, valid BOOLEAN, source VARCHAR(50), PRIMARY KEY (address, source));")
    cur.execute("CREATE INDEX IF NOT EXISTS geocodes_la_idx ON geocodes (lower(address));")
    cur.execute("CREATE TABLE IF NOT EXISTS geocodes_pending (id BIGSERIAL PRIMARY KEY, address TEXT UNIQUE, status SMALLINT);")
    db.commit()

app = Flask(__name__)
api = Api(app)

class GeocodePost(Resource):
    def get(self):
        return ""
    def post(self):
        logging.debug("Post entered")
        json_data = request.get_json(force=True)
        with db.cursor() as cur:
            locations_list = []
            queue_list = json_data
            lower_list = [element.lower() for element in json_data]
            logging.debug(tuple(queue_list))

            cur.execute("SELECT address, latitude, longitude, valid FROM geocodes WHERE lower(address) in %s ORDER BY valid DESC;", (tuple(lower_list),))
            for result in cur:
                logging.debug(result[0])
                try:
                    queue_list.remove(result[0])
                except ValueError:
                    pass
                else:
                    if result[3] == True:
                        locations_list.append({"address":result[0], "latitude":result[1], "longitude":result[2]})
            
            logging.debug(queue_list)
            logging.debug("Inserting into pending")

            try:
                execute_batch(cur, "INSERT INTO geocodes_pending (address, status) VALUES (%s, 0) ON CONFLICT DO NOTHING;", [[a] for a in queue_list])
            except psycopg2.DataError as e:
                logging.debug(e)
            else:
                db.commit()
            
            cur.execute("SELECT id FROM geocodes_pending ORDER BY id DESC LIMIT 1;")
            if cur.rowcount > 0:
                queue_target = cur.fetchone()[0]
            else:
                queue_target = 0
            cur.execute("SELECT id FROM geocodes_pending ORDER BY id ASC LIMIT 1;")
            if cur.rowcount > 0:
                queue_current = cur.fetchone()[0]
            else:
                queue_current = 0

            logging.debug("Queue current " + str(queue_current) + " queue target " + str(queue_target))

            return jsonify({"queue_current": queue_current, "queue_target": queue_target, "data": locations_list})

class Geocode(Resource):
    def get(self, address):
        with db.cursor() as cur:
            query = cur.execute("SELECT * FROM geocodes WHERE lower(address)=%s;", (address.lower(),))
            # Query the result and get cursor.Dumping that data to a JSON is looked by extension
            if query is not None:
                result = {"data": [dict(zip(tuple(query.keys()), i)) for i in query.cursor]}
            else:
                result = {"data": None}
        return result
        # We can have PUT,DELETE,POST here. But in our API GET implementation is sufficient

class QueueStatus(Resource):
    def get(self):
        with db.cursor() as cur:
            cur.execute("SELECT id FROM geocodes_pending ORDER BY id ASC LIMIT 1;")
            queue_current = cur.fetchone()
            if queue_current is not None:
                queue_current = queue_current[0]
            else:
                queue_current = -1
            
            status = "OK"
            cur.execute("SELECT id FROM geocodes_pending WHERE address='OVER_QUERY_LIMIT' AND status=-1 LIMIT 1;")
            if cur.rowcount == 1:
                status = "OVER_QUERY_LIMIT"
            
        return jsonify({"queue_current": queue_current, "status": status})

class GeocodeInsert(Resource):
    def post(self):
        data = request.get_json(force=True)
        logging.debug(data)
        
        with db.cursor() as cur:
            logging.debug("Inserting")
            cur.execute("INSERT INTO geocodes (address, latitude, longitude, valid, source) VALUES (%(address)s, %(lat)s, %(lng)s, true, %(source)s) ON CONFLICT (address, source) DO UPDATE SET latitude=%(lat)s, longitude=%(lng)s;", {"address":data["address"], "lat":data["latitude"], "lng":data["longitude"], "source":"remote_addr|" + request.remote_addr})
            db.commit()

        return ""

api.add_resource(Geocode, '/api/geocode/<string:address>')
api.add_resource(GeocodePost, '/api/geocodepost')
api.add_resource(QueueStatus, '/api/queue_status')
api.add_resource(GeocodeInsert, "/api/geocode_insert")

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

if __name__ == '__main__':
    app.run()
