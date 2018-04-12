from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from json import dumps
import json
import config
import logging
import psycopg2
from psycopg2.extras import execute_batch
import time

logging.basicConfig(level=logging.DEBUG)

db = psycopg2.connect(config.postgres_connection_string)

with db.cursor() as cur:
    cur.execute("CREATE TABLE IF NOT EXISTS geocodes (address TEXT, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, valid BOOLEAN, source VARCHAR(50), PRIMARY KEY (address, source));")
    cur.execute("CREATE INDEX IF NOT EXISTS geocodes_la_idx ON geocodes (address);")
    cur.execute("CREATE TABLE IF NOT EXISTS geocodes_pending (id BIGSERIAL PRIMARY KEY, address TEXT UNIQUE, status SMALLINT DEFAULT 0);")
    db.commit()

app = Flask(__name__)
api = Api(app)

class GeocodePost(Resource):
    def get(self):
        return ""
    def post(self):
        t0 = time.time()
        json_data = set(request.get_json(force=True))
        logging.debug("Json conversion took " + str(time.time() - t0) + " s")

        with db.cursor() as cur:
            locations_list = []

            t0 = time.time()
            cur.execute("SELECT address, latitude, longitude, valid FROM geocodes WHERE address in %s ORDER BY valid DESC;", (tuple(json_data),))
            logging.debug("Select took " + str(time.time() - t0) + " s")

            t0 = time.time()
            for result in cur:
                try:
                    json_data.remove(result[0])
                except KeyError:
                    pass
                else:
                    if result[3] == True:
                        locations_list.append({"address":result[0], "latitude":result[1], "longitude":result[2]})
            logging.debug("Result loop took " + str(time.time() - t0) + " s")

            t0 = time.time()
            try:
                execute_batch(cur, "INSERT INTO geocodes_pending (address) VALUES (%s) ON CONFLICT DO NOTHING;", [[a] for a in json_data])
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

            logging.debug("Rest took " + str(time.time() - t0) + " s")

            return jsonify({"queue_current": queue_current, "queue_target": queue_target, "data": locations_list})

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
        
        with db.cursor() as cur:
            logging.debug("Inserting")
            cur.execute("INSERT INTO geocodes (address, latitude, longitude, valid, source) VALUES (%(address)s, %(lat)s, %(lng)s, true, %(source)s) ON CONFLICT (address, source) DO UPDATE SET latitude=%(lat)s, longitude=%(lng)s;", {"address":data["address"].lower(), "lat":data["latitude"], "lng":data["longitude"], "source":"remote_addr|" + request.remote_addr})
            db.commit()

        return ""

api.add_resource(GeocodePost, '/api/geocodepost')
api.add_resource(QueueStatus, '/api/queue_status')
api.add_resource(GeocodeInsert, "/api/geocode_insert")

if __name__ == '__main__':
    app.run()
