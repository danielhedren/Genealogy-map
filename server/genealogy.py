from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_restful import Resource, Api
from sqlalchemy import create_engine
from json import dumps
import urllib
import json
import config

e = create_engine('sqlite:///database.s3db')

app = Flask(__name__)
api = Api(app)

class GeocodePost(Resource):
    def get(self):
        return ""
    def post(self):
        json_data = request.get_json(force=True)
        conn = e.connect()

        locations_list = []

        for i, address in enumerate(json_data):
            print(str(i) + "/" + str(len(json_data)))
            result = conn.execute("select count(*) from geocodes where address=?", address).first()
            if (result[0] == 0):
                response = urllib.request.urlopen("https://maps.googleapis.com/maps/api/geocode/json?address=" + urllib.parse.quote_plus(address) + "&key=" + config.gmaps_api_key)
                content = response.read().decode(response.headers.get_content_charset())
                json_data = json.loads(content)
                if (json_data["status"] == "OK"):
                    values = [address,json_data["results"][0]["geometry"]["location"]["lat"], json_data["results"][0]["geometry"]["location"]["lng"], True, "google"]
                    conn.execute("insert into geocodes (address, latitude, longitude, valid, source) values (?, ?, ?, ?, ?)", values)
                elif (json_data["status"] == "ZERO_RESULTS"):
                    values = [address, False, "google"]
                    conn.execute("insert into geocodes (address, valid, source) values (?, ?, ?)", values)
                else:
                    print("STATUS ERROR " + json_data["status"])
                    break
            else:
                location = conn.execute("select latitude, longitude from geocodes where address=? and valid", address).first()
                if (location != None):
                    locations_list.append({"address":address, "latitude":location[0], "longitude":location[1]})
        
        return jsonify(locations_list)

class Geocode(Resource):
    def get(self, address):
        print(address)
        conn = e.connect()
        query = conn.execute("select * from geocodes where address='%s'" % address)
        # Query the result and get cursor.Dumping that data to a JSON is looked by extension
        result = {'data': [dict(zip(tuple(query.keys()), i)) for i in query.cursor]}
        return result
        # We can have PUT,DELETE,POST here. But in our API GET implementation is sufficient

api.add_resource(Geocode, '/geocode/<string:address>')
api.add_resource(GeocodePost, '/geocodepost')

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

if __name__ == '__main__':
    #app.run()
    app.run()