
# coding: utf-8

# In[9]:

import json, requests
import csv
import pandas as pd
import numpy as np
from datetime import datetime

# 
import sqlalchemy
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, func, literal_column

from flask import Flask, jsonify, render_template
# In[10]:

# access token for api
# ykey_access_token = "CVTqDuGbB3YF4mUT1Kx3_yLW43u9BKAxZDiirJ0Ua6VS6UMKqzAdefhsy3H-0zHOoYiczJZ0hwZ8YNhlWqsvst5c-pQ13fscyQUDfFstAOtBC7mrUs98aZCFQHRhWnYx"
ykey_access_token = "6dF_ksyC2PaHJDLhgr2_joA12Zb48JjopdvVAGD3jJ49uPuy_Cvbo-WHjusl8rYpPqYJHoHgT053pZgvr6T6EXDTxq5BDCJBFetpbAkdVneMDSTk88RqOMnZeABhWnYx"


# In[11]:

# API constants
API_HOST = 'https://api.yelp.com'
SEARCH_PATH = '/v3/businesses/search'
BUSINESS_PATH = '/v3/businesses/'

# Defaults 
DEFAULT_TERM = 'restaurant'
DEFAULT_LOCATION = '10005'
SEARCH_LIMIT = 50
SEARCH_MAX_LIMIT = 1000
SORT_BY = 'rating'

# variables
newOffset = 0

# Establish Connection to MySQL
# DB_CONFIG_DICT = {
#         'user': 'root',
#         'password': 'Bernice1!',
#         'host': 'localhost',
#         'port': 3306,
#     }

DB_CONN_URI_DEFAULT= "mysql://nchwjnkppsn6j4vj:s23q3vtsg2c0a4sv@o3iyl77734b9n3tg.cbetxkdyhwsb.us-east-1.rds.amazonaws.com:3306/zx309qzs0npjpbew"

# DB_CONN_FORMAT = "mysql://{user}:{password}@{host}:{port}/{database}"
# DB_NAME = "machinelearning"
# DB_CONN_URI_DEFAULT = (DB_CONN_FORMAT.format(
#     database=DB_NAME,
#     **DB_CONFIG_DICT)) 
    
engine = create_engine(DB_CONN_URI_DEFAULT)

# reflect an existing database into a new model
Base = automap_base()
# reflect the tables
Base.prepare(engine, reflect=True)

print(Base.metadata.tables.keys())

# Save reference to the table
# Restaurants = Base.classes.restaurants
# Zipcodes = Base.classes.zipcodes

# Create our session (link) from Python to the DB
session = Session(engine)

#################################################
# Flask Setup
#################################################
app = Flask(__name__)


#################################################
# Functions
#################################################
# Default route to render index.html
@app.route("/")
def default():
    # Default route to render index.html    
    return render_template("index.html")


def updateSQL(dataframe):    
    dataframe.to_sql(name='restaurant', con=engine, if_exists='append', index=False)

def request(host, path, api_key, url_params=None):
#     send a GET request to the API.

#     Args:
#         host (str): The domain host of the API.
#         path (str): The path of the API after the domain.
#         API_KEY (str): Your API Key.
#         url_params (dict): An optional set of query parameters in the request.

#     Returns:
#         dict: The JSON response from the request.

#     Raises:
#         HTTPError: An error occurs from the HTTP request.
    url = '%s%s' % (host, path)

    url_params = url_params or {}
    
    headers = {
        'Authorization': 'Bearer %s' % api_key,
    }

    response = requests.request('GET', url=url, headers=headers, params=url_params)
        
    return response.json()


# In[14]:

def yelpsearch(term, location):
    """Query the Search API by a search term and location.

    Args:
        term (str): The search term passed to the API.
        location (str): The search location passed to the API.

    Returns:
        dict: The JSON response from the request.
    """

    # Check if zipcode has been searched recently (1 week)
    # for test, pull everytime
    # if zipcode found


    #else
    restaurants = []

    for i in range(10):
        if i == 0:
            newOffset = 0
        else:
            newOffset = i*SEARCH_LIMIT
            print (newOffset)
            
        # data = yelpsearch(DEFAULT_TERM, zipcodes, newOffset)
        url_params = {
            'term': term.replace(' ', '+'),
            'location': location.replace(' ', '+'),
            'limit': SEARCH_LIMIT,
            'offset': newOffset,
            'sort_by': SORT_BY
        }
        
        response = request(API_HOST, SEARCH_PATH, ykey_access_token, url_params=url_params)

        for business in response['businesses']:
            try:
                reservations = False               
                if 'restaurant_reservation' in business['transactions']:
                    reservations=True
                # if i >= 0:
                #     reservations = True
                    
                delivery = True    
                i, = np.where( business['transactions']=='delivery' )
                if i >= 0:
                    delivery = True
                
                lat = business['coordinates']['latitude']
                lng = business['coordinates']['longitude']

                rest_dict = {
                    'name':business['name'].split(",")[0],
                    'image_url': business['image_url'],
                    'review_count': business['review_count'],
                    'price': business['price'],
                    'zipcode': business['location']['zip_code'],
                    'rating': business['rating'],            
                    'latitude': lat,
                    'longitude': lng,
                    'address': ','.join(business['location']['display_address']),
                    'phone': business['display_phone'],
                    'reservations': reservations,
                    'delivery': delivery,
                    'cuisine': business['categories'][0]['title']
                    
                }
                
                restaurants.append(rest_dict)
            except:
                print("error!!!!!")
            
    
    df = pd.DataFrame(restaurants)
    df.to_csv("restaurant.csv", index=False)
    updateSQL(df)
    return restaurants


@app.route("/mlyelp/search/<zipcodes>")
def searchapi(zipcodes):       
    data = yelpsearch(DEFAULT_TERM, zipcodes)

    return jsonify(data)

@app.route("/mlyelp/listzipcodes")
def get_zipcodes():
    zipcodes = pd.read_csv("zip_code_database.csv")

    return zipcodes.to_json(orient="records")


# def foundZipcode(zipcode):
#     result = session.query(Zipcodes). \
#             filter(Zipcodes.zip == zipcode). \
#             first()

#     if result['lastrequestdate'] not None:
#         date1 = datetime.strptime(result['lastrequestdate'], "%Y-%m-%d").date()
#         date2 = datetime.strptime(datetime.now(), "%Y-%m-%d").date()
#         delta =  (date2 - date1).days
#         if delta > 7:
#             return False
#         else:
#             return True
#     else:
#         return False

    

# def deleteZipCodesFromRestaturant(zipcode)
#     rowcount = session.query(Restaurants).filter(Restaurants.zipcode == zipcode).\
#         delete(synchronize_session=False)
#     print('%s records deleted from Restaurants table with zipcode %s' % (rowcount, zipcode))

# Initiate the Flask app
if __name__ == '__main__':
    app.run(debug=True)



