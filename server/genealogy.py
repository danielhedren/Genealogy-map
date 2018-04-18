from flask import Flask, request, jsonify, session
from flask_restful import Resource, Api
from json import dumps
import json
import config
import logging
import psycopg2
from psycopg2.extras import execute_batch
import time
import ipaddress
import datetime

logging.basicConfig(level=logging.DEBUG)

db = psycopg2.connect(config.postgres_connection_string)

with db.cursor() as cur:
    cur.execute("CREATE TABLE IF NOT EXISTS geocodes (address VARCHAR(500), latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, valid BOOLEAN, source VARCHAR(75), PRIMARY KEY (address, source));")
    cur.execute("CREATE INDEX IF NOT EXISTS geocodes_la_idx ON geocodes (address);")
    cur.execute("CREATE TABLE IF NOT EXISTS geocodes_pending (id BIGSERIAL PRIMARY KEY, address TEXT UNIQUE, status SMALLINT DEFAULT 0);")
    db.commit()

app = Flask(__name__)
api = Api(app)

app.secret_key = config.secret_key

class GeocodePost(Resource):
    def post(self):
        t0 = time.time()
        json_data = set(request.get_json(force=True, silent=True))

        if json_data is None:
            return "{status: \"BAD_REQUEST\"}", 400

        logging.debug("Json conversion took " + str(time.time() - t0) + " s")

        with db.cursor() as cur:
            locations_list = []

            t0 = time.time()
            try:
                data_tuple = tuple(json_data)
            except Exception:
                return "{status: \"BAD_REQUEST\"}", 400

            cur.execute("SELECT address, latitude, longitude, valid FROM geocodes WHERE address in %s ORDER BY valid DESC;", (data_tuple,))
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
                db.rollback()
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

            session["timestamp"] = datetime.datetime.now()

            return jsonify({"status": "OK", "queue_current": queue_current, "queue_target": queue_target, "data": locations_list})

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
            
        return jsonify({"queue_current": queue_current, "status": status}), 200

class GeocodeInsert(Resource):
    def post(self):
        data = request.get_json(force=True, silent=True)

        if data is None:
            return "{status: \"BAD_REQUEST\"}", 400
        
        if data["latitude"] < -90 or data["latitude"] > 90 or data["longitude"] < -180 or data["longitude"] > 180:
            return "{status: \"BAD_REQUEST\"}", 400

        if "timestamp" not in session:
            return "{status: \"FORBIDDEN\"}", 403
        
        with db.cursor() as cur:
            logging.debug("Inserting")
            try:
                cur.execute("INSERT INTO geocodes (address, latitude, longitude, valid, source) VALUES (%(address)s, %(lat)s, %(lng)s, true, %(source)s) ON CONFLICT (address, source) DO UPDATE SET latitude=%(lat)s, longitude=%(lng)s;", {"address":data["address"].lower(), "lat":data["latitude"], "lng":data["longitude"], "source":"remote_addr|" + request.remote_addr})
            except Exception:
                db.rollback()
                return "{status: \"BAD_REQUEST\"}", 400 
            else:
                db.commit()

        return "{status: \"OK\"}", 201

@app.before_request
def session_timeout():
    if "timestamp" in session and (datetime.datetime.now() - session["timestamp"]).seconds > config.session_timeout:
        session.clear()

api.add_resource(GeocodePost, '/api/geocodepost')
api.add_resource(QueueStatus, '/api/queue_status')
api.add_resource(GeocodeInsert, "/api/geocode_insert")

if __name__ == '__main__':
    app.run()
