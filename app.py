import os
import json, requests
import csv
import pandas as pd
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

# sklearn
from sklearn import tree
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

from keras.utils import to_categorical
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

# from boto.s3.connection import S3Connection
# s3 = S3Connection(os.environ['JAWSDB_URL'])
# print(os.environ['JAWSDB_URL'])

key_pd = pd.read_csv("Keys.py")
sqlkey = key_pd[key_pd['name'] == 'sqlkey']['key'].max().strip()
# print(sqlkey)

DB_CONN_URI_DEFAULT= sqlkey

engine = create_engine(DB_CONN_URI_DEFAULT)


# reflect an existing database into a new model
Base = automap_base()
# reflect the tables
Base.prepare(engine, reflect=True)
# print(Base.metadata.tables.keys())

# Save reference to the table
Restaurant = Base.classes.restaurants
ZipRequest = Base.classes.ziprequests
Search_Information = Base.classes.search_information
Users = Base.classes.usersdb
CuisineType = Base.classes.cuisinetype

sessiondb = Session(engine)


#################################################
# Flask Setup
#################################################
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_SECRET_KEY", "NoLimitData")
app.jinja_env.undefined = StrictUndefined

from raven.contrib.flask import Sentry
sentry = Sentry(app)

#################################################
# Routes
#################################################
# Default route to render index.html
@app.route("/")
def default():
    # Default route to render landing page    
    return render_template("home.html")

# LOGIN

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

#  LOGOUT

@app.route("/logout")
def logout():
    """Log user out."""

    del session["current_user"]

    flash("Goodbye! You have successfully logged out.", "success")

    return redirect("/")

#  SIGNUP

@app.route("/signup", methods=["GET"])
def signup():
    """Show signup form."""

    return render_template("signup.html")


@app.route("/signup", methods=["POST"])
def signup_post():
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

#  REQUEST PAGE
@app.route("/requestpage", methods=['GET'])
def requestpage():
    # get list of cuisine to show on drop down
    cuisines = get_default_cuisines()

    # Default route to render request page    
    return render_template("requestpage.html",cuisines=cuisines,sizeofcuisine=len(cuisines))

@app.route("/requestpage", methods=['POST'])
def requestpage_post():
    zipcode = request.form.get("zipcode")
    if (request.form.get('cuisine')):
        cuisines=request.form.getlist('cuisine')
        results = get_restaurants(zipcode, cuisines)
    else:
        results = get_restaurants(zipcode)

    print(len(results))

    group1_results = get_shuffled_results(4, results)
    group2_results = get_shuffled_results(4, results)
    group3_results = get_shuffled_results(4, results)

    totalresults = len(group1_results) + len(group1_results) + len(group1_results)

    if totalresults == 0:
        flash("No restaurants found to evaluate for this zipcode.  Try another zipcode", "danger")
        redirect("/requestpage")

    return render_template("resultpage.html",restaurant_results1=group1_results,
        restaurant_results2=group2_results,restaurant_results3=group3_results, totalresults=totalresults,zipcode=zipcode)

# RESULT PAGE
@app.route("/resultpage", methods=['POST'])
def resultpage_post():
    user_id = session['current_user']['userid']
    zipcode = request.form.get("zipcode")

    f = request.form
    for key in f.keys():
        for value in f.getlist(key):
            if (key == 'zipcode'):
                continue
            yelpid = key.split("_")[1]
            addSelectedInformation(user_id, yelpid, int(value)) 

    print("User id profile: %s" % session['current_user']['userid'])
    r2, yelpid_the_one = ML_random_trees (zipcode, session['current_user']['userid'])
        
    print (r2)

    if len(yelpid_the_one) > 0:
        data_dict = get_restaurant_yelpid(yelpid_the_one)

    # Default route to render machine learning page    
    # return redirect("/machinelearning/%s" % session['current_user']['userid'])
    return render_template("machinelearning.html", restaurant=data_dict, r2=r2)

# MACHINE LEARNING PAGE 
@app.route("/machinelearning", methods=['GET'])
def machinelearning():    
    #  call function to do machine learning
    print("User id profile: %s" % session['current_user']['userid'])
    # clf_result, r2_result = ML_random_trees (session['current_user']['userid'])
    # Default route to render request page    
    return render_template("machinelearning.html")#, r2=r2_result)

@app.route("/machinelearning", methods=['POST'])
def machinelearning_post():      
    # Default route to render request page    
    return render_template("machinelearning.html")

@app.route("/team", methods=['GET'])
def team():    
    return render_template("team.html")

@app.route("/about", methods=['GET'])
def about():    
    return render_template("about.html")

# Request users
@app.route("/your-next-stop/users", methods=['GET'])
@app.route("/your-next-stop/users/<userid>", methods=['GET'])
def userapi(userid=None):

    data = get_users(userid)
    return jsonify(data)

# Request searchinfo by userid
@app.route("/your-next-stop/searchinfo", methods=['GET'])
@app.route("/your-next-stop/searchinfo/<userid>", methods=['GET'])
def searchinfoapi(userid=None):

    data = get_search_information(userid)
    return jsonify(data)


# request restaurant by zipcode
@app.route("/your-next-stop/restaurant/<zipcode>", methods=['GET'])
@app.route("/your-next-stop/restaurant/<zipcode>/<cuisines>", methods=['GET'])
def restaurantapi(zipcode,cuisines=None):

    data = get_restaurants(zipcode, cuisines)
    return jsonify(data)

# request restaurant by yelpid
@app.route("/your-next-stop/restaurant/id/<yelpid>", methods=['GET'])
def restaurantbyidapi(yelpid):
    data = get_restaurant_yelpid(yelpid)
    return jsonify(data)   


#################################################
# Functions
#################################################
def addSelectedInformation(user_id, yelpid,like):
    try:
        r = sessiondb.query(Restaurant).\
                    filter(Restaurant.yelpid == yelpid).\
                    first()

    except NoResultFound:
        print("Restaurant %s not found !!!!" % yelpid)
        return False

    
    # add selected restaurant to table
    si = Search_Information(userid=user_id, 
                    cuisine=r.cuisine,
                    zipcode=r.zipcode,
                    yelpid=yelpid,
                    rating=r.rating,
                    price=r.price,
                    delivery=r.delivery,
                    reservations=r.reservations,
                    like=like,
                    lastsearchdate=datetime.now())
    sessiondb.add(si)
    sessiondb.commit()

def deleteZipCodesFromRestaturant(reqid):
    rowcount = sessiondb.query(Restaurant).filter(Restaurant.requestid == int(reqid)).\
        delete(synchronize_session=False)
    sessiondb.commit()
    print('%s records deleted from Restaurants table with zipcode %s' % (rowcount, reqid))

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
        if delta > 7:
            print("False: Date over 7 days !!!!")            
            # Delete all rows in table for the zipcode requested, so if we need to run this a second time,
            # we won't be trying to add duplicate data for the request
            print("deleting zipCodes")
            deleteZipCodesFromRestaturant(zipcode)

            # # found zipcode but need to refresh. update new date and time to ziprequest
            # print(int(zipcode))
            # newdate = datetime.now()
            # print(newdate)

            # sessiondb.query(ZipRequest).filter(ZipRequest.requestid == int(zipcode)).\
            #     update({ZipRequest.lastrequestdate: newdate}, synchronize_session=False)
            # sessiondb.commit()
                
            zipCodeFound = False
        
    except NoResultFound:
        # # New request.  date gets automatically populated the first time. 
        # zp = ZipRequest(requestid=int(zipcode), zipcode=zipcode)
        # print(zp)
        # sessiondb.add(zp)
        # sessiondb.commit()
        zipCodeFound = False


    return zipCodeFound


def get_default_cuisines():
    # get list of cuisine to show on drop down    
    cuisines = sessiondb.query(CuisineType.type, CuisineType.value).order_by(CuisineType.type).all()    
    return cuisines

def get_restaurants(zipcode,cuisines=None):
    if cuisines is None:
        cuisines = get_default_cuisines()
        defaultcuisines = []
        for c in cuisines:
            defaultcuisines.append(c[0])
        cuisines = defaultcuisines

    cuisines = ",".join(cuisines)
    print(cuisines)


    newdate = datetime.now()
    print(newdate)
    if not findZipcode(zipcode):
        # always populate data with all cuisines in table
        data = yelpsearch(get_default_cuisines(), zipcode)
        if (len(data) > 0):
            # New request.  date gets automatically populated the first time. 
            zp = ZipRequest(requestid=int(zipcode), zipcode=zipcode, lastrequestdate = newdate)
            sessiondb.add(zp)
            sessiondb.commit()
            zipCodeFound = False
    else:
        print(int(zipcode))

        sessiondb.query(ZipRequest).filter(ZipRequest.requestid == int(zipcode)).\
            update({ZipRequest.lastrequestdate: newdate}, synchronize_session=False)
        sessiondb.commit()   

    # get data from DB
    # filter data using cuisines
    data = get_zipcode_data(zipcode, cuisines)

    return data

def get_restaurant_yelpid(yelpid):
    try:
        r = sessiondb.query(Restaurant).\
                        filter(Restaurant.yelpid == yelpid).\
                        first()

        # for r in result:
        transactions = []
        if r.reservations:
            transactions.append("Reservations")

        if r.delivery:
            transactions.append("Delivery")

        data_dict = {
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
                'url': r.url,
                'transactions': transactions
            }
    except:
        data_dict={}
        flash("No restaurant found for this id.  Try again.")

    return data_dict 

def get_search_information(user_id):
    if user_id is None:        
        result = sessiondb.query(Search_Information).all()
    else:
        result = sessiondb.query(Search_Information).filter(Search_Information.userid == user_id).all()
    
    data = []
    for r in result:
        searchinfo_dict = {
            'userid': r.userid,
            'lastsearchdate':r.lastsearchdate,
            'yelpid': r.yelpid,
            'price': r.price,
            'zipcode': r.zipcode,
            'rating': float(r.rating),
            'reservations': r.reservations,
            'delivery': r.delivery,
            'cuisine': r.cuisine,
            'like': r.like
        }
        data.append(searchinfo_dict)

    return data

def get_shuffled_results(numberofrecords, results):
    shuffle(results)
    # if len(results) < 8:

    print(results)

    return results[:numberofrecords]

def get_users(user_id):
    if user_id is None:        
        result = sessiondb.query(Users).all()
    else:
        result = sessiondb.query(Users).filter(Users.userid == user_id).all()
    
    data = []
    for r in result:
        user_dict = {
            'userid': r.userid,
            'firstname':r.first_name,
            'lastname': r.last_name,
            'email': r.email
        }
        data.append(user_dict)

    return data

def get_shuffled_results(numberofrecords, results):
    shuffle(results)
    # if len(results) < 8:
    return results[:numberofrecords]


def get_zipcode_data(zipcode,cuisines):
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
                    filter(Restaurant.requestid == int(zipcode), Restaurant.cuisine.in_(cuisines.split(','))).\
                    all()

        data = []
        for r in result:
            transactions = []
            if r.reservations:
                transactions.append("Reservations")

            if r.delivery:
                transactions.append("Delivery")

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
                    'url': r.url,
                    'transactions': transactions
                }
            data.append(rest_dict)

    except NoResultFound:
        print("zip code no results !!!!")
    return data

def ML_random_trees(zipcode, user_id):
    # Filter restaurants list by requested zipcode
    restaurants = sessiondb.query(Restaurant).filter(Restaurant.requestid == int(zipcode))

    data = []
    for result in restaurants:
        restaurant = {        
            'cuisine': result.cuisine,
            'delivery': result.delivery,           
            'price': result.price,
            'rating': float(result.rating),
            'reservations': result.reservations,
            'yelpid': result.yelpid
        }

        data.append(restaurant)
    restaurants_df = pd.DataFrame(data)

    # Filtered restaurants
    restaurants_df = restaurants_df[["cuisine", "delivery", "price", "rating", "reservations", "yelpid"]]

    # Getting YelpIDs of restaurants shown
    selections = sessiondb.query(Search_Information).filter(Search_Information.userid==user_id).order_by(Search_Information.searchid.desc()).limit(12).all()

    for select in selections:
        current_yelp = select.yelpid
        restaurants_df = restaurants_df[restaurants_df.yelpid != current_yelp]
    
    encoder = LabelEncoder()
    encoder.fit(restaurants_df['cuisine'])
    cuisine_transformed = encoder.transform(restaurants_df['cuisine'])
    
    # use onehot encoding for cuisine
    one_hot_cuisine = to_categorical(cuisine_transformed)

    # Adjusting one hot to fit df
    restaurant_cuisines_unique = restaurants_df['cuisine'].unique()
    cuisines = []

    restaurant_cuisines_unique = [item.lower() for item in restaurant_cuisines_unique]
    restaurant_cuisines_unique.sort()

    # Reshaping one_hot_cuisine
    cuisine_dict = {}

    for x in range(len(restaurant_cuisines_unique)):
        current_cuisine = restaurant_cuisines_unique[x]    
        encoded_cuisine = []
        for y in range(len(restaurants_df)):
            encoded_cuisine.append(int(one_hot_cuisine[y][x]))
        cuisine_dict[current_cuisine] = encoded_cuisine

    # label encode price
    encoder.fit(restaurants_df['price'])
    price_transformed = encoder.transform(restaurants_df['price'])
    # price_transformed

    # DataFrame with encoded values
    res_new = pd.DataFrame({
        'price': price_transformed,
        'rating': restaurants_df['rating'],
        'reservations': restaurants_df['reservations'],
        'delivery': restaurants_df['delivery'],
        'yelpid': restaurants_df['yelpid']
    })

    for key, value in cuisine_dict.items():
        res_new[key] = value

    # By user 
    # Storing data for specified user (user 1)
    results = sessiondb.query(Search_Information).filter(Search_Information.userid == user_id).all()

    data = []
    for result in results:
        restaurant = {            
            'price': result.price,
            'rating': float(result.rating),
            'reservations': result.reservations,
            'delivery': result.delivery,
            'cuisine': result.cuisine,
            'like': result.like,
            'yelpid': result.yelpid
        }
        data.append(restaurant)


    df = pd.DataFrame(data)
    df.head()

    # One-hot encoding cuisine
    encoder = LabelEncoder()
    encoder.fit(df['cuisine'])
    cuisine_transformed = encoder.transform(df['cuisine'])

    one_hot_cuisine = to_categorical(cuisine_transformed)

    # Reshaping one_hot_cuisine
    cuisines_unique = df['cuisine'].unique()
    cuisines = [item.lower() for item in cuisines_unique]
    cuisines.sort()

    cuisine_dict = {}

    for x in range(len(cuisines)):
        current_cuisine = cuisines[x]
        encoded_cuisine = []
        for y in range(len(df)):
            encoded_cuisine.append(int(one_hot_cuisine[y][x]))
        cuisine_dict[current_cuisine] = encoded_cuisine


    # Encoding price
    encoder.fit(df['price'])
    price_transformed = encoder.transform(df['price'])


    # DataFrame with encoded values
    df_new = pd.DataFrame({
        'price': price_transformed,
        'rating': df['rating'],
        'reservations': df['reservations'],
        'delivery': df['delivery'],
        'like': df['like'],
        'yelpid': df['yelpid']
    })

    for key, value in cuisine_dict.items():
        df_new[key] = value

    # find the difference in the list
    if len(cuisines) > len(restaurant_cuisines_unique):
        diff_unique = list(set(cuisines) - set(restaurant_cuisines_unique))
    else:    
        diff_unique = list(set(restaurant_cuisines_unique) - set(cuisines))

    # X & y values   
    X = df_new.loc[:, (df_new.columns != 'like') & (df_new.columns != 'yelpid')]        
    y = df_new['like']

    if len(restaurant_cuisines_unique) > len(cuisines):
        for c in diff_unique:
            X[c] = 0

    # train data to make r2 more meaningful
    X_train, X_test, y_train, y_test = train_test_split(X, y, random_state=40)

    rf = RandomForestClassifier(n_estimators=33)
    rf = rf.fit(X_train, y_train)
    r2 = rf.score(X_test, y_test)

    # add new column of missing cuisine and default to 0 
    if len(cuisines) > len(restaurant_cuisines_unique):
        for c in diff_unique:
            res_new[c] = 0
            
    # Predicting data
    X_res = res_new.loc[:, res_new.columns != 'yelpid']
    predictions = rf.predict(X_res)

    res_new["predictions"] = predictions

    # Selecting random restaurant with predictions = 1 
    yesses = res_new[res_new['predictions'] == 1]
    random_res = yesses.sample(n=1)
    yelp_rec = random_res['yelpid'].item()    
    # yelp_rec = str(random_res['yelpid'])    
    # yelp_rec = yelp_rec.split(" ")[4].split("\n")[0]
    print("yelp_rec: " + yelp_rec)
    

    return (float(r2), yelp_rec)



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


def updateSQL(dataframe, location): 
    dataframe.to_sql(name='restaurants', con=engine, if_exists='append', index=False)


# Query the Search API by a search term and location.
def yelpsearch(cuisines, location):
    # Args:         
    #     categories (str separated by comma) The types of cuisine passed to the API
    #     location (str separated by comma): The zipcodes passed to the API.

    # Returns:
    #     list of restaurants

    
    cuisine_type, cuisine_alias = zip(*cuisines)
    print(cuisine_alias)
    restaurants = []
    for i in range(10):
        if i == 0:
            newOffset = 0
        else:
            newOffset = i*SEARCH_LIMIT

        url_params = {
            # term (str): The search term passed to the API. In our case, restaurants
            'term': DEFAULT_TERM,
            'categories': cuisine_alias,
            'location': location,
            'limit': SEARCH_LIMIT,
            'offset': newOffset,
            'sort_by': SORT_BY
        }
        
        response = searchrequest(API_HOST, SEARCH_PATH, ykey_access_token, url_params=url_params)

        addCtr = 0
        # if (len(response['businesses'] > 0)):
        for business in response['businesses']:
            try:
                reservations = False               

                if 'restaurant_reservation' in business['transactions']:
                    reservations=True
                    
                delivery = False   
                if 'delivery'  in business['transactions']:
                    delivery = True
                
                lat = business['coordinates']['latitude']
                lng = business['coordinates']['longitude']

                for c in business['categories']:
                    if c['alias'] in cuisine_alias:
                        foundcuisine = cuisine_type[cuisine_alias.index(c['alias'])]
                        continue

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
                    'cuisine': foundcuisine
                }
                restaurants.append(rest_dict)
            except:
                print("error!!!!!")
                pass
    
    df = pd.DataFrame(restaurants)
    print("number of restaurants: " + str(len(restaurants)))
    # df.to_csv("restaurant_%s.csv" % location, index=False)
    updateSQL(df, location)

    return restaurants

# Initiate the Flask app
if __name__ == '__main__':    
    app.run(debug=True)
    session.close()