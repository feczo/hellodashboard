import os
import bqclient
import webapp2
import logging
from django.utils import simplejson as json
from google.appengine.ext.webapp.template import render
from oauth2client.appengine import oauth2decorator_from_clientsecrets
from googleapiclient.discovery import build
from googleapiclient import errors
from google.appengine.api import memcache

CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'client_secrets.json')
SCOPES = [
    'https://www.googleapis.com/auth/bigquery'
]
decorator = oauth2decorator_from_clientsecrets(
    filename=CLIENT_SECRETS,
    scope=SCOPES,
    cache=memcache)

# Project ID for a project where you and your users
#   are viewing members.  This is where the bill will be sent.
#   During the limited availability preview, there is no bill.
# Replace this value with the Client ID value from your project,
#   the same numeric value you used in client_secrets.json
BILLING_PROJECT_ID = "475473128136"
DATA_PROJECT_ID = "publicdata"
DATASET = "samples"
TABLE = "natality"
QUERY = ("select state,"
         "SUM(gestation_weeks) / COUNT(gestation_weeks) as weeks "
         "from %s:%s.%s "
         "where year > 1990 and year < 2005 "
         "and IS_EXPLICITLY_DEFINED(gestation_weeks) "
         "group by state order by weeks") % (DATA_PROJECT_ID, DATASET, TABLE)
mem = memcache.Client()


class MainPage(webapp2.RequestHandler):
    def _bq2geo(self, bqdata):
        """geodata output for region maps must be in the format region, value.
           Assume the query output is in this format, get names from schema.
        """
        logging.info(bqdata)
        columnNameGeo = bqdata["schema"]["fields"][0]["name"]
        columnNameVal = bqdata["schema"]["fields"][1]["name"]
        logging.info("Column Names=%s, %s" % (columnNameGeo, columnNameVal))
        geodata = {}
        geodata["rows"] = []
        geodata["cols"] = (
            {"id": columnNameGeo, "label": columnNameGeo, "type": "string"},
            {"id": columnNameVal, "label": columnNameVal, "type": "number"})
        for row in bqdata["rows"]:
            newrow = ({"c": []})
            newrow["c"].append({"v": "US-"+row["f"][0]["v"]})
            newrow["c"].append({"v": row["f"][1]["v"]})
            geodata["rows"].append(newrow)
        logging.info("FINAL GEODATA---")
        logging.info(geodata)
        return json.dumps(geodata, ensure_ascii=True)

    @decorator.oauth_required
    def get(self):
        data = mem.get('natality')
        if not(data):
            bq = bqclient.BigQueryClient(decorator)
            values = self._bq2geo(bq.Query(QUERY, BILLING_PROJECT_ID))
            data = {'data': values,
                    'query': QUERY}
            mem.set('natality', data)
        template = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(render(template, data))

application = webapp2.WSGIApplication([
    ('/', MainPage),
    (decorator.callback_path, decorator.callback_handler())
], debug=True)
