from gevent import monkey
monkey.patch_all()

import cgi
from flask import Flask, render_template, request
from flask.ext.socketio import SocketIO, join_room, leave_room

from _pybgpstream import BGPStream, BGPRecord, BGPElem

import calendar
import time

import threading

import collections

#import logging
#logging.basicConfig(filename='app.log')

app = Flask(__name__)
socketio = SocketIO(app)

delay = 1800 # delay every message by 1hr (to simulate RT)

clients_cnt = 0
thread = None

def generate_stream():
    bs = BGPStream()
    rec = BGPRecord()

    bs.add_interval_filter(calendar.timegm(time.gmtime()) - delay, 0)
    #bs.add_interval_filter(1444780800, 1444780800)
    bs.add_filter('collector', 'route-views2')
    bs.add_filter('record-type', 'updates')

    # ask bgpstream for one rib if they asked for a table dump
    #if send_dump:
    #    bs.add_filter('record-type', 'ribs')
    #    bs.add_rib_period_filter(86400) # one per day

    bs.start()

    print('Beginning to read from stream')
    #if send_dump: print('First getting a RIB dump')
    while(bs.get_next_record(rec)):
        elem = rec.get_next_elem()
        while(elem):
            # sleep until it is time to send this second
            now = calendar.timegm(time.gmtime())
            sim_time = now - delay
            if elem.time > sim_time:
                time.sleep(elem.time - sim_time)

            #if elem.type == 'R':
		#msg = {
		#    'type': elem.type,
		#    'prefix': elem.fields['prefix'],
		#    'time': elem.time,
		#    'path': elem.fields['as-path']
		#}
                #socketio.emit('bgp_dump', msg, namespace="/bgplay")
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

#@socketio.on('connect', namespace='/bgplay')
#def ws_conn():

#@socketio.on('disconnect')
#def ws_disconn():
#    c = 9
#    socketio.emit('msg', {'count': c}, namespace='/dd')

@socketio.on('bgp_subscribe', namespace='/bgplay')
def ws_bgp_subscribe(message):
    # what prefix are they interested in?
    pfx = message['resource']
    send_dump = message['sendDump']
    # assign them to a room
    #join_room(pfx)

    # TODO: another thread to send a table dump first

    # if this is our first client, then start up the bgpstream thread
    global clients_cnt
    clients_cnt += 1
    if clients_cnt == 1:
    	thread = threading.Thread(target=generate_stream)
    	thread.start()

if __name__ == '__main__':
    socketio.run(app, host='gibi.caida.org', port=5000)
