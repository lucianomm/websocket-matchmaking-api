from gevent import monkey
monkey.patch_all()
import requests
from requests.auth import HTTPBasicAuth
import os
import json

from flask import Flask, render_template
from flask_socketio import SocketIO, send

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey'
socketio = SocketIO(app, async_mode='gevent')

user_ids_str = os.environ.get('USER_IDS', '')
connection_ids_str = os.environ.get('CONNECTION_IDS', '')
server_ready_url = 'http://<YOUR-DOMAIN>/matchmaking/serverReady'
match_finished_url = 'http://<YOUR-DOMAIN>/matchmaking/matchFinished'

user_ids = user_ids_str.split(',')
connection_ids = connection_ids_str.split(',')

home = user_ids[int((len(user_ids))/2):]
away = user_ids[:int((len(user_ids)/2))]

def send_post_request(url, data):
    auth = HTTPBasicAuth('DEV_DEDICATED_CLIENT_ID', 'DEV_DEDICATED_CLIENT_SECRET')
    try:
        print("Sending POST request to", url, "with data:", data)
        response = requests.post(
            url, 
            data=data, 
            auth=auth
        )

        if response.status_code == 200:
            print("POST was successful.")
        else:
            print("POST request to", url, "failed with status code:", response.status_code)
            print("Response body:", response.text)
    except Exception as e:
        print("POST request to", url, "failed with exception:", e)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('message')
def handleMessage(msg):
    print('Message: ' + msg)
    if msg == 'HOME':
        body = json.dumps({
            "home": home,
            "away": away,
            "result": 'home'
        })
        send_post_request(match_finished_url, body)
        send(body, broadcast=True)
        send(msg, broadcast=True)
        os._exit(0)
        
    elif msg == 'AWAY':
        send(msg, broadcast=True)
        body = json.dumps({
            "home": home,
            "away": away,
            "result": 'away'
        })
        send_post_request(match_finished_url, body)
        send(body, broadcast=True)
        os._exit(0)
    
    elif msg == 'DRAW':
        send(msg, broadcast=True)
        body = json.dumps({
            "home": home,
            "away": away,
            "result": 'draw'
        })
        send_post_request(match_finished_url, body)
        send(body, broadcast=True)
        os._exit(0)
        
    elif msg == 'STATUS':
        send(msg, broadcast=True)
        send(f"home team: {home}", broadcast=True)
        send(f"away team: {away}", broadcast=True)
    
    else:
        send(msg, broadcast=True)

if __name__ == '__main__':
    
    body = json.dumps({
        "user_ids": user_ids,
        "connection_ids": connection_ids,
    })

    # Send a POST request with the USER_IDS in the body
    send_post_request(server_ready_url, body)
        
    socketio.run(app, host='0.0.0.0', port=80)
