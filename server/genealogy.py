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
    cur.execute("CREATE TABLE IF NOT EXISTS geocodes (address TEXT PRIMARY KEY, latitude DOUBLE PRECISION, longitude DOUBLE PRECISION, valid BOOLEAN, source VARCHAR(50));")
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

            cur.execute("SELECT address, latitude, longitude, valid FROM geocodes WHERE address in %s;", (tuple(json_data),))
            for result in cur:
                queue_list.remove(result[0])
                if result[3] == True:
                    locations_list.append({"address":result[0], "latitude":result[1], "longitude":result[2]})
            
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
            query = cur.execute("SELECT * FROM geocodes WHERE address=%s;", (address,))
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
            
        return jsonify({"queue_current": queue_current})

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
