import json
from flask import Flask, request, redirect, url_for, Response, render_template
from urllib import parse
import requests
from subprocess import run
import subprocess
import base64
import config_reader as cfg
import os


from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
# from data import ACTORS
# from modules import get_names, get_actor, get_id

app = Flask(__name__)


# Flask-WTF requires an encryption key - the string can be anything
app.config['SECRET_KEY'] = 'C2HWGVoMGfNTBsrYQg8EcMrdTimkZfAb'

# Flask-Bootstrap requires this line
Bootstrap(app)


# with Flask-WTF, each web form is represented by a class
# "NameForm" can change; "(FlaskForm)" cannot
# see the route for "/" and "index.html" to see how this is used
class NameForm(FlaskForm):
    text  = StringField('Say what?')
    say   = SubmitField('Say')
    title = StringField('Play what?')
    play  = SubmitField('Play')
    pause = SubmitField('Pause')
    auth  = SubmitField('Authorize')



# URLs
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com"
API_VERSION = "v1"
SPOTIFY_API_URL = "{}/{}".format(SPOTIFY_API_BASE_URL, API_VERSION)
SPOTIFY_PLAYER_URL = SPOTIFY_API_URL+"/me/player"
SPOTIFY_PLAYABLE_URI = cfg.get_spotify_playable_uri()

HOSTNAME = "0.0.0.0"
PORT = 3141
THIS_SERVER_ADDRESS = "http://" + HOSTNAME + ":" + str(PORT)
SPOTIFY_REDIRECT_URI = THIS_SERVER_ADDRESS + "/authorize_spotify"

# App's global constants
SPOTIFY_DEVICE_ID =  cfg.get_spotify_device_id()
currently_playing = False

def link2uri(link):
    if link.split(':')[0] == 'spotify':
        return link
    list = link.split('?')[0].split('/')

    if len(list) == 5 and list[0] == 'https:' and list[2] == 'open.spotify.com':
        return 'spotify:' + list[-2] + ':' + list[-1]
    else:
        return ''

@app.route('/', methods=['GET', 'POST'])
def index():
    # you must tell the variable 'form' what you named the class, above
    # 'form' is the variable name used in this template: index.html
    form = NameForm()
    message = ""
    response = None
    if form.validate_on_submit():    
        if form.say.data:
            say(form.text.data)
        if form.play.data:
            response = play(link2uri(form.title.data))
        if form.pause.data:
            response = pause()
        if response is not None:
            message = str(response)
            #message += '<br><br>' + 'Request:  ' + response.url
            #message += '<br>'     + 'Response: ' + str(response.status_code) + ' ' + response.text
        if form.auth.data:
            message = request_spotify_authorization()
    return render_template('form.html', form=form, message=message)



@app.route("/test")
def test_menu():
    message = "<h2>Server test menu</h2>"
    message += '<br><a href="/talk?text=whoa whoa whoa! What was that?">whoa</a>'
    message += '<br><a href="/devices">devices</a>'
    message += '<br><a href="/request_spotify_authorization">authorize</a>'
    message += '<br><a href="/spotiplay">play</a>'
    message += '<br><a href="/spotipause">pause</a>'
    message += '<br><a href="/spotinext">next</a>'
    message += '<br><a href="/spotiprev">previous</a>'
    message += '<br><a href="/transfer">transfer</a><br><br><br>'
    return message

@app.route("/talk")
def server_talk():
    message = request.args.get('text')
#    message += "Server address: " + host_uri()
#    message += "<br>redirect: " + spotify_redirect_uri()
    say(message)
    return test_menu() + "I just said: " + message


def host_ip():    
    return request.host.split(':')[0]

def host_uri():    
    return "http://" + request.host

def spotify_redirect_uri():    
    return host_uri() + "/authorize_spotify"


# TODO: In context of /login, maybe rename to refresh auth
@app.route("/request_spotify_authorization")
def request_spotify_authorization(code=None):
    if code != None:
        # Ask for a refresh token and access token using code received from Spotify in /login
        # (Step 2 of 'Authorization Code Flow')
        # https://developer.spotify.com/documentation/general/guides/authorization-guide/
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": spotify_redirect_uri(),
        }
    else:
        # Ask for an access token using a refresh token
        # (Step 4 of 'Authorization Code Flow')
        # https://developer.spotify.com/documentation/general/guides/authorization-guide/
        data = {
            "grant_type": "refresh_token",
            "refresh_token": cfg.get_spotify_refresh_token()
        }

    client_id = cfg.get_spotify_client_id()
    client_secret = cfg.get_spotify_client_secret()
    auth_str = '{}:{}'.format(client_id, client_secret)
    b64_auth_str = base64.urlsafe_b64encode(auth_str.encode()).decode()
    headers = {"Authorization": "Basic {}".format(b64_auth_str)}
    response = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    error = handle_and_return_possible_error_message_in_api_response(response)
    response_data = response.json()
    if error:
        return error
    elif "access_token" in response_data:
        access_token = response_data["access_token"]
        file = open("access_token.txt", "w")
        file.write(access_token)
        file.close()
        refresh_token_received = "refresh_token" in response_data
        if refresh_token_received:
            refresh_token = response_data["refresh_token"]
            cfg.set_spotify_refresh_token(refresh_token)
        message = "Retrieved and saved access token" + (" and refresh token" if refresh_token_received else "")
        app.logger.info(message)
        return message
    else:
        return "Unknown problem with response to request_spotify_authorization"

@app.route("/authorize_spotify")
def authorize_spotify():
    # XXX: Handle erroneous response 
    # (https://developer.spotify.com/documentation/general/guides/authorization-guide/)
    code = request.args.get('code')
    status_message = request_spotify_authorization(code=code)
    return status_message 
        
@app.route("/login")
def login():
    scopes = "user-read-playback-state user-modify-playback-state"
    login_url = SPOTIFY_AUTH_URL + '?response_type=code' + '&client_id=' + cfg.get_spotify_client_id() + '&scope=' + parse.quote(scopes) + '&redirect_uri=' + parse.quote(spotify_redirect_uri())
    return redirect(login_url, code=302)


@app.route("/spotipause")
def spotipause():
    response = pause()
    return answer( response )


@app.route("/spotiplay")
def spotiplay():
    response = play(spotify_uri="spotify:playlist:5crU6AclXGahkiVpvIcbZQ")
    return answer( response )



def play(spotify_uri=None, song_number=0, retries_attempted=0): 
    # XXX: naming problem between this and spotiplay
    global currently_playing
    data = ''
    if spotify_uri != None:
        #data = '{"context_uri":"' + spotify_uri + '","offset":{"position":' + str(song_number) + '},"position_ms":0}'
        data = '{"uris":["' + spotify_uri + '"]}'
    response = spotify_request("play", force_device=True, data=data)
    if response.ok:
        currently_playing = True
    if response.status_code == 404:
        # Hardcoded device not found
        try: 
            radioplay()
            app.logger.info('Spotify device not found, playing radio')
        except:
            app.logger.info("Spotify device not found and failed to play radio")
            
    return response


def pause():
    global currently_playing
    response = spotify_request("pause")
    if response.ok:
        currently_playing = False
    return response


def playpause():
    global currently_playing
    if currently_playing:
        pause()
    else:
        play()

def set_volume(new_volume):
    url_params = {"volume_percent":str((new_volume+1)*10)}
    response = spotify_request("volume", url_params=url_params)
    return response

def spotify_request(endpoint, http_method="PUT",  data=None, force_device=False, token=None, url_params={}):
    app.logger.info("Request to endpoint '/" + endpoint + "' attempted")
    if token is None:
        token = access_token_from_file()
    if force_device:
        url_params["device_id"] = "98bb0735e28656bac098d927d410c3138a4b5bca"
    if endpoint:
        url = SPOTIFY_PLAYER_URL + "/" + endpoint
    else:
        url = SPOTIFY_PLAYER_URL
    headers = {'Authorization': 'Bearer {}'.format(token)} 
    if http_method == "PUT":
        response = requests.put(url, data=data, headers=headers, params=url_params)
    elif http_method == "GET":
        response = requests.get(url, data=data, headers=headers, params=url_params)
    elif http_method == "POST":
        response = requests.post(url, data=data, headers=headers, params=url_params)

    handle_and_return_possible_error_message_in_api_response(response)
    if response.status_code == 401:
        # If the access token is expired, get a new one and retry
        token = request_spotify_authorization()
        headers = {'Authorization': 'Bearer {}'.format(token)}
        response = requests.put(url, data=data, headers=headers, params=url_params)
    return response

def handle_and_return_possible_error_message_in_api_response(response):
    if response.ok:
        return
    response_data = response.json()
    
    if "error" in response_data:
        if "error_description" in response_data:
            error_message =  response_data["error_description"]
        elif "message" in response_data["error"]:
            error_message = response_data["error"]["message"] 
        app.logger.info(error_message)
        say("Error: " + error_message)
        return error_message

def access_token_from_file():
    file = open("access_token.txt","r")
    access_token = file.read()
    file.close()
    return access_token

def say(something):
    run(["espeak", something], stdout=subprocess.DEVNULL)




@app.route('/devices', methods=['GET'])
def devices():
    response = spotify_request("devices", http_method="GET")
    return answer( response )


@app.route('/areyourunning', methods=['GET'])
def areyourunning():
    message = "Alarm-clock server is running."
    say(message)
    return message


@app.route("/transfer")
def trans():
    response = spotify_request("", data='{"device_ids": ["98bb0735e28656bac098d927d410c3138a4b5bca"]}')
    return answer( response )




@app.route("/spotinext")
def next():
    response = spotify_request("next", http_method="POST")
    return answer( response )

@app.route("/spotiprev")
def prev():
    response = spotify_request("previous", http_method="POST" )
    return answer( response )

def answer (response):
    message = test_menu()
    message += '<br><br>' + 'Request:  ' + response.url
    message += '<br>'     + 'Response: ' + str(response.status_code) + ' ' + response.text
    return message



if __name__ == '__main__':
    app.run(debug=True, port=PORT, host='0.0.0.0')
