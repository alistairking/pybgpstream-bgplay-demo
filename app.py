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

def elem2bgplay(rec, elem):
    msg = {
        'type': elem.type,
        'timestamp': elem.time,
        'target': {
            'prefix': elem.fields['prefix'],
            },
        #'community': not-supported,

	'source': {
	    'as_number': elem.peer_asn,
	    'ip': elem.peer_address,
	    'project': rec.project,
	    'collector': rec.collector,
	    'id': rec.project + '-' + rec.collector + '-' + str(elem.peer_asn) + '-' + str(elem.peer_address)
	}
    }
    if elem.type == 'A':
        msg['path'] = [
            {'owner': str(asn), 'as_number': str(asn)}
            for asn in elem.fields['as-path'].split()
        ]
    return msg

def generate_stream():
    bs = BGPStream()
    rec = BGPRecord()

    bs.add_interval_filter(calendar.timegm(time.gmtime()) - delay, 0)
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
                msg = elem2bgplay(rec, elem)
                socketio.emit('bgp_message', msg,
                              namespace='/bgplay',
                              room=elem.fields['prefix'])
                socketio.emit('bgp_message', msg,
                              namespace='/bgplay',
                              room='all')

            elem = rec.get_next_elem()

@app.route('/')
def main():
    return render_template('main.html')

@socketio.on('bgp_subscribe', namespace='/bgplay')
def ws_bgp_subscribe(message):
    # are they interested in a prefix?
    if 'resource' in message:
        join_room(message['resource'])
    else:
        join_room('all')

    # TODO: support table dumps

if __name__ == '__main__':
    thread = threading.Thread(target=generate_stream)
    thread.start()
    socketio.run(app, host='gibi.caida.org', port=5000)
