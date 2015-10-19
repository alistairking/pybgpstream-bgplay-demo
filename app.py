from gevent import monkey
monkey.patch_all()
from flask import Flask, render_template, request
from flask.ext.socketio import SocketIO, join_room, leave_room
from _pybgpstream import BGPStream, BGPRecord, BGPElem
import calendar
import time
import threading
import collections

app = Flask(__name__)
socketio = SocketIO(app)
delay = 1800 # delay every message by 30min (to simulate RT)
clients_cnt = 0
thread = None

def generate_stream():
    bs = BGPStream()
    rec = BGPRecord()

    bs.add_interval_filter(calendar.timegm(time.gmtime()) - delay, 0)
    #bs.add_interval_filter(1444780800, 1444780800)
    bs.add_filter('collector', 'route-views.sg')
    bs.add_filter('record-type', 'updates')
    bs.start()

    print('Beginning to read from stream')
    while(bs.get_next_record(rec)):
        elem = rec.get_next_elem()
        while(elem):
            # sleep until it is time to send this record
            now = calendar.timegm(time.gmtime())
            sim_time = now - delay
            if elem.time > sim_time:
                time.sleep(elem.time - sim_time)

            if elem.type == 'A' or elem.type == 'W':
		msg = {
		    'type': elem.type,
		    'prefix': elem.fields['prefix'],
		    'time': elem.time
		}
		if elem.type == 'A':
		    msg['as-path'] = elem.fields['as-path']
                socketio.emit('bgp_message', msg,
                              namespace='/bgplay')#, room=msg['prefix'])
            elem = rec.get_next_elem()

@app.route('/')
def main():
    return render_template('main.html')

@socketio.on('bgp_subscribe', namespace='/bgplay')
def ws_bgp_subscribe(message):
    # what prefix are they interested in?
    pfx = message['resource']
    send_dump = message['sendDump']
    # assign them to a room
    #join_room(pfx)

    # if this is our first client, then start up the bgpstream thread
    global clients_cnt
    clients_cnt += 1
    if clients_cnt == 1:
    	thread = threading.Thread(target=generate_stream)
    	thread.start()

if __name__ == '__main__':
    socketio.run(app, host='gibi.caida.org', port=5000)
