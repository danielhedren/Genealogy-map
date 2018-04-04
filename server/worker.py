import config
import psycopg2, time, logging, json, threading
from urllib import request, error, parse

logging.basicConfig(level=logging.DEBUG)

def process_queue():
    db = psycopg2.connect(config.postgres_connection_string)
    logging.debug("Queue processing worker thread started")

    while True:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM geocodes_pending WHERE status=0 ORDER BY id ASC LIMIT 1 FOR UPDATE SKIP LOCKED;")
            result = cur.fetchone()
        
        if result is not None:
            with db.cursor() as cur:
                cur.execute("UPDATE geocodes_pending SET status=1 WHERE id=%s ", (result[0],))
                db.commit()

            try:
                response = request.urlopen("https://maps.googleapis.com/maps/api/geocode/json?address=" + parse.quote_plus(result[1]) + "&key=" + config.gmaps_api_key)
            except error.HTTPError:
                with db.cursor() as cur:
                    cur.execute("DELETE FROM geocodes_pending WHERE id=%s ", (result[0],))
                    db.commit()
                continue

            content = response.read().decode(response.headers.get_content_charset())
            json_data = json.loads(content)

            logging.debug(json_data["status"] + ": " + result[1])

            if (json_data["status"] == "OK"):
                values = [result[1],json_data["results"][0]["geometry"]["location"]["lat"], json_data["results"][0]["geometry"]["location"]["lng"], True, "google"]
                cur = db.cursor()
                cur.execute("INSERT INTO geocodes (address, latitude, longitude, valid, source) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING;", values)
                db.commit()
            elif (json_data["status"] == "ZERO_RESULTS"):
                values = [result[1], False, "google"]
                cur = db.cursor()
                cur.execute("INSERT INTO geocodes (address, valid, source) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;", values)
                db.commit()
            elif (json_data["status"] == "UNKNOWN_ERROR"):
                # Retry on unknown error
                pass
            elif (json_data["status"] == "OVER_QUERY_LIMIT"):
                # Wait 6 hours
                time.sleep(60 * 60 * 6)
            elif (json_data["status"] == "INVALID_REQUEST"):
                # Skip the bad value
                pass

            with db.cursor() as cur:
                cur.execute("DELETE FROM geocodes_pending WHERE id=%s ", (result[0],))
                db.commit()

        else:
            time.sleep(1)

if __name__ == "__main__":
    for i in range(0, 9):
        threading.Thread(target=process_queue, daemon=True).start()
    process_queue()