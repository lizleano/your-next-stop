import os
import json, requests
import csv
import pandas as pd
import numpy as np
from random import shuffle
from datetime import datetime

# 
from jinja2 import StrictUndefined
import sqlalchemy
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import create_engine, func, literal_column

from flask import Flask, jsonify, render_template, redirect, request, flash, session

#################################################
# Constants and Variables
#################################################

# access token for api
# ykey_access_token = "CVTqDuGbB3YF4mUT1Kx3_yLW43u9BKAxZDiirJ0Ua6VS6UMKqzAdefhsy3H-0zHOoYiczJZ0hwZ8YNhlWqsvst5c-pQ13fscyQUDfFstAOtBC7mrUs98aZCFQHRhWnYx"
ykey_access_token = "6dF_ksyC2PaHJDLhgr2_joA12Zb48JjopdvVAGD3jJ49uPuy_Cvbo-WHjusl8rYpPqYJHoHgT053pZgvr6T6EXDTxq5BDCJBFetpbAkdVneMDSTk88RqOMnZeABhWnYx"

# API constants
API_HOST = 'https://api.yelp.com'
SEARCH_PATH = '/v3/businesses/search'
BUSINESS_PATH = '/v3/businesses/'

# Defaults 
DEFAULT_TERM = 'restaurants'
DEFAULT_CUISINE = 'italian,asian,mexican,mediterrean,indian'
DEFAULT_LOCATION = '10005'
SEARCH_LIMIT = 50
SEARCH_MAX_LIMIT = 1000
SORT_BY = 'rating'

# variables
newOffset = 0

#################################################
# MySQL Setup
#################################################

DB_CONN_URI_DEFAULT= "mysql://nchwjnkppsn6j4vj:s23q3vtsg2c0a4sv@o3iyl77734b9n3tg.cbetxkdyhwsb.us-east-1.rds.amazonaws.com:3306/zx309qzs0npjpbew"

engine = create_engine(DB_CONN_URI_DEFAULT)

# reflect an existing database into a new model
Base = automap_base()
# reflect the tables
Base.prepare(engine, reflect=True)
print(Base.metadata.tables.keys())

# Save reference to the table
Restaurant = Base.classes.restaurants
ZipRequest = Base.classes.ziprequests
Search_Information = Base.classes.searchinformation
Users = Base.classes.usersdb
CuisineType = Base.classes.cuisinetype

sessiondb = Session(engine)

#################################################
# Flask Setup
#################################################
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY", "NoLimitData")
app.jinja_env.undefined = StrictUndefined

#################################################
# Routes
#################################################
# Default route to render index.html
@app.route("/")
def default():
    # Default route to render landing page    
    return render_template("home.html")

@app.route("/login", methods=['GET'])
def login():
    # render login page    
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    """Log user in if credentials provided are correct."""

    login_email = request.form.get("login_email")
    login_password = request.form.get("login_password")

    try:
        current_user = sessiondb.query(Users).filter(Users.email == login_email,
                                                     Users.password == login_password).one()
    except NoResultFound:
        flash("The email or password you have entered did not match our records. Please try again.", "danger")
        return redirect("/login")

    # Get information of last search
    # searchinfo = get_search_information(current_user.userid)

    # Use a nested dictionary for session["current_user"] to store more than just user_id
    session["current_user"] = {
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "userid": current_user.userid
        # "lastsearchdate": searchinfo['lastsearchdate'],
        # "cuisines": searchinfo['cuisine'],
        # "zipcodes": searchinfo['zipcode']
    }

    flash("Welcome {}. You have successfully logged in.".format(current_user.first_name), "success")

    return redirect("/requestpage")
    # return redirect("/users/{}".format(current_user.user_id))

@app.route("/logout")
def logout():
    """Log user out."""

    del session["current_user"]

    flash("Goodbye! You have successfully logged out.", "success")

    return redirect("/")


@app.route("/signup", methods=["GET"])
def show_signup():
    """Show signup form."""

    return render_template("signup.html")


@app.route("/signup", methods=["POST"])
def signup():
    """Check if user exists in database, otherwise add user to database."""

    signup_email = request.form.get("signup_email")
    signup_password = request.form.get("signup_password")
    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    
    try:
        sessiondb.query(Users).filter(Users.email == signup_email).one()

    except NoResultFound:
        new_user = Users(email=signup_email,
                        password=signup_password,
                        first_name=first_name,
                        last_name=last_name)
        sessiondb.add(new_user)
        sessiondb.commit()

        # Add same info to session for new user as per /login route
        session["current_user"] = {
            "first_name": new_user.first_name,
            "last_name": new_user.last_name,
            "userid": new_user.userid
        }

        flash("You have succesfully signed up for an account, and you are now logged in.", "success")

        return redirect("/requestpage")
        # return redirect("/requestpage/%s" % new_user.userid)

    flash("An account already exists with this email address. Please login.", "danger")

    return redirect("/login")

# @app.route("/requestpage/<userid>", methods=['GET'])
# def requestpage(user_id):
@app.route("/requestpage", methods=['GET'])
def requestpage():
    # get list of cuisine to show on drop down
    cuisines = sessiondb.query(CuisineType.type, CuisineType.value).all()
    # Default route to render request page    
    return render_template("requestpage.html",cuisines=cuisines)

@app.route("/requestpage", methods=['POST'])
def requestpage_post():
    print(request.form)

    zipcode = request.form.get("zipcode")
    results = get_restaurants(zipcode)

    shuffle(results)
    group1_results = results[:8]

    shuffle(results)
    group2_results = results[:8]

    shuffle(results)
    group3_results = results[:8]

    # Default route to render request page    
    return render_template("resultpage.html",restaurant_results1=group1_results,
        restaurant_results2=group2_results,restaurant_results3=group3_results)


@app.route("/machinelearning", methods=['GET'])
def machinelearning():
    # get searchinfo
    searchinfo = sessiondb.query(Search_Information).all()
    # Default route to render request page    
    return render_template("machinelearning.html")

# Request restaurants by zipcode
@app.route("/mlyelp/search/<zipcode>", methods=['GET'])
@app.route("/mlyelp/search/<zipcode>/<cuisine>", methods=['GET'])
def searchapi(zipcode,cuisine=None):
    # print (zipcode)
    # print(cuisine)
    if cuisine is None:
        cuisine = DEFAULT_CUISINE
    # print (cuisine)

    if findZipcode(zipcode):
        # get data from DB
        data = get_zipcode_data(zipcode)
    else: 
        # get new data from yelp
        data = yelpsearch(cuisine, zipcode)

    return jsonify(data)   

#################################################
# Functions
#################################################
def get_restaurants(zipcode,cuisine=None):
    # print (zipcode)
    # print(cuisine)
    if cuisine is None:
        cuisine = DEFAULT_CUISINE
    # print (cuisine)

    if findZipcode(zipcode):
        # get data from DB
        data = get_zipcode_data(zipcode)
    else: 
        # get new data from yelp
        data = yelpsearch(cuisine, zipcode)

    return data  

def get_search_information(user_id):
    try:
        searchinfo = sessiondb.query(Search_Information).filter(Search_Information.userid == user_id).one()
    except:
        searchinfo = {
            "lastsearchdate": datetime.strftime(datetime.now(), "%m/%d/%Y %H:%M:%S"),
            "userid": user_id,
            "cuisine": "",
            "zipcode": ""
        }
    print(searchinfo)

    return searchinfo

def updateSQL(dataframe, location): 
    dataframe.to_sql(name='restaurants', con=engine, if_exists='append', index=False)


def searchrequest(host, path, api_key, url_params=None):
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


# Query the Search API by a search term and location.
def yelpsearch(cuisine, location):
    # Args:         
    #     categories (str separated by comma) The types of cuisine passed to the API
    #     location (str separated by comma): The zipcodes passed to the API.

    # Returns:
    #     list of restaurants
    
    restaurants = []
    for i in range(10):
        if i == 0:
            newOffset = 0
        else:
            newOffset = i*SEARCH_LIMIT
            print ("offset: %s   limit: %s" % (newOffset, SEARCH_LIMIT))
            
        # data = yelpsearch(DEFAULT_TERM, zipcodes, newOffset)
        url_params = {
            # term (str): The search term passed to the API. In our case, restaurants
            'term': DEFAULT_TERM,
            # 'categories': cuisine,
            'location': location,
            'limit': SEARCH_LIMIT,
            'offset': newOffset,
            'sort_by': SORT_BY
        }
        
        response = searchrequest(API_HOST, SEARCH_PATH, ykey_access_token, url_params=url_params)

        print("records returned: %s" % (len(response['businesses'])))
        addCtr = 0
        # if (len(response['businesses'] > 0)):
        for business in response['businesses']:
            # print(business['name'])
            try:
                reservations = False               

                if 'restaurant_reservation' in business['transactions']:
                    reservations=True
                    
                delivery = True    
                i, = np.where( business['transactions']=='delivery' )
                if i >= 0:
                    delivery = True
                
                lat = business['coordinates']['latitude']
                lng = business['coordinates']['longitude']

                rest_dict = {
                    'requestid': location,
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
                    'url': business['url'],
                    'yelpid': business['id'],
                    'cuisine': business['categories'][0]['title']
                }
                
                restaurants.append(rest_dict)
            except:
                # print("error!!!!!")
                pass
    
    df = pd.DataFrame(restaurants)
    # df.to_csv("restaurant_%s.csv" % location, index=False)
    updateSQL(df, location)

    print("restaurants collected through yelp API!!!!")

    return restaurants



def findZipcode(zipcode):
    # print(ZipRequest.__table__.columns)
    zipCodeFound = True
    try:
        result = sessiondb.query(ZipRequest.requestid, ZipRequest.lastrequestdate).\
                filter(ZipRequest.zipcode == zipcode).\
                one()

        date1 = result[1]
        date2 = datetime.now()
        delta =  (date2 - date1).days
        print(delta)
        if delta > 7:
            print("False: Date over 7 days !!!!")            
            # Delete all rows in table for the zipcode requested, so if we need to run this a second time,
            # we won't be trying to add duplicate data for the request
            print("deleting zipCodes")
            deleteZipCodesFromRestaturant(zipcode)

            # found zipcode but need to refresh. update new date and time to ziprequest
            print(int(zipcode))
            newdate = datetime.now()
            print(newdate)

            sessiondb.query(ZipRequest).filter(ZipRequest.requestid == int(zipcode)).\
                update({ZipRequest.lastrequestdate: newdate}, synchronize_session=False)
            sessiondb.commit()
                
            zipCodeFound = False
        
    except NoResultFound:
        # New request.  date gets automatically populated the first time. 
        zp = ZipRequest(requestid=int(zipcode), zipcode=zipcode)
        print(zp)
        sessiondb.add(zp)
        sessiondb.commit()
        zipCodeFound = False


    return zipCodeFound
    

def get_zipcode_data(zipcode):
    result = []
    try:
        result = sessiondb.query(Restaurant.address,\
                            Restaurant.cuisine,\
                            Restaurant.delivery,\
                            Restaurant.image_url,\
                            Restaurant.latitude,\
                            Restaurant.longitude,\
                            Restaurant.name,\
                            Restaurant.phone,\
                            Restaurant.price,\
                            Restaurant.rating,\
                            Restaurant.requestid,\
                            Restaurant.reservations,\
                            Restaurant.review_count,\
                            Restaurant.url,\
                            Restaurant.yelpid,\
                            Restaurant.zipcode).\
                    filter(Restaurant.requestid == int(zipcode)).\
                    all()

        data = []
        for r in result:
            rest_dict = {
                    'requestid': r.requestid,
                    'name':r.name,
                    'image_url': r.image_url,
                    'review_count': r.review_count,
                    'price': r.price,
                    'zipcode': r.zipcode,
                    'rating': float(r.rating),            
                    'latitude': float(r.latitude),
                    'longitude': float(r.longitude),
                    'address': r.address,
                    'phone': r.phone,
                    'reservations': r.reservations,
                    'delivery': r.delivery,
                    'cuisine': r.cuisine,
                    'yelpid': r.yelpid,
                    'url': r.url
                }
            data.append(rest_dict)

        print("zip code collected from DB!!!!")

    except NoResultFound:
        print("zip code no results !!!!")
    return data

def deleteZipCodesFromRestaturant(reqid):
    rowcount = sessiondb.query(Restaurant).filter(Restaurant.requestid == int(reqid)).\
        delete(synchronize_session=False)
    sessiondb.commit()
    print('%s records deleted from Restaurants table with zipcode %s' % (rowcount, reqid))

# Initiate the Flask app
if __name__ == '__main__':
    app.run(debug=True)