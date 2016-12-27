#!/usr/bin/env python3
from . import api

import logging
from waggle.logging import JournalHandler
from waggle.logging import SlackHandler
import os.path
import re
import sys
import json
import time
import requests

sys.path.append("../..")
import export
sys.path.pop()

sys.path.append("..")
from waggle_protocol.utilities.mysql import *
from flask import Flask
from flask import Response
from flask import request
from flask import jsonify
from flask import stream_with_context


app = Flask(__name__)
app.logger.setLevel(logging.INFO)

logger = logging.getLogger('beehive-api')
logger.setLevel(logging.INFO)

handler = JournalHandler()
handler.setLevel(logging.INFO)
logger.addHandler(handler)
app.logger.addHandler(handler)

# Publish errors to Slack.
handler = SlackHandler('https://hooks.slack.com/services/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')
handler.setLevel(logging.ERROR)
logger.addHandler(handler)
app.logger.addHandler(handler)

port = 80
api_url_internal = 'http://localhost'
api_url = 'http://beehive1.mcs.anl.gov'

# modify /etc/hosts/: 127.0.0.1	localhost beehive1.mcs.anl.gov
STATUS_Bad_Request = 400  # A client error
STATUS_Unauthorized = 401
STATUS_Not_Found = 404
STATUS_Server_Error = 500


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code and status_code==STATUS_Server_Error:
            logger.warning(message)
        else:
            logger.debug(message)
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@api.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

def get_mysql_db():
    return Mysql(host="beehive-mysql",
                 user="waggle",
                 passwd="waggle",
                 db="waggle")

@api.route('/')
def api_root():
    return 'This is the Waggle Beehive API Server.\n'


@api.route('/1/')
def api_version():
    return 'This is the Waggle Beehive API Server.\n'


@api.route('/1/epoch')
def api_epoch():
    return jsonify({
        'epoch': int(time.time())
    })


@api.route('/1/nodes/')
def api_nodes():

    # if bAllNodes ('b' is for 'bool') is True, print all nodes, otherwise filter the active ones
    bAllNodes = request.args.get('all', 'false').lower() == 'true'

    logger.info("__ api_nodes()  bAllNodes = {}".format(str(bAllNodes)))

    db = get_mysql_db()

    all_nodes = {}

    # limit the output with a WHERE clause if bAllNodes is false
    whereClause = " " if bAllNodes else " WHERE opmode = 'active' "

    query = "SELECT node_id, hostname, project, description, reverse_ssh_port, name, location, last_updated FROM nodes {};".format(whereClause)

    logger.debug(' query = ' + query)

    mysql_nodes_result = db.query_all(query)

    for result in mysql_nodes_result:
        node_id, hostname, project, description, reverse_ssh_port, name, location, last_updated = result

        if not node_id:
            continue

        # cleanup formatting
        node_id = node_id.lower()

        all_nodes[node_id] = {
            'project': project,
            'description': description,
            'reverse_ssh_port': reverse_ssh_port,
            'name': name,
            'location': location,
            'last_updated': last_updated
        }

    if bAllNodes:
        nodes_dict = export.list_node_dates()

        for node_id in nodes_dict.keys():
            if not node_id in all_nodes:
                all_nodes[node_id]={}

    # for node_id in all_nodes.keys():
    #     logger.debug("%s %s" % (node_id, type(node_id)))

    obj = {}
    obj['data'] = all_nodes
    return jsonify(obj)
    # return  json.dumps(obj, indent=4)


@api.route('/nodes')
def nodes():
    if request.accept_mimetypes.best == 'text/csv':
        return nodes_csv()
    else:
        return nodes_json()


def nodes_json():
    return jsonify(list(filtered_nodes()))


def nodes_csv():
    fmt = '{id},{name},{description},{location},{port}\n'
    return Response((fmt.format(**node) for node in filtered_nodes()),
                    mimetype='text/csv')


def get_nodes():
    rows = get_mysql_db().query_all('SELECT node_id, name, description, location, reverse_ssh_port FROM nodes')

    for row in rows:
        yield {
            'id': row[0].lower().rjust(16, '0'),
            'name': row[1] or '',
            'description': row[2] or '',
            'location': row[3] or '',
            'port': row[4] or 0,
        }


def filtered_nodes():
    filters = [(field, re.compile(pattern, re.I))
               for field, pattern in request.args.items()]

    return filter(lambda node: all(pattern.search(node[field])
                                   for field, pattern in filters),
                  get_nodes())


@api.route('/1/nodes/<node_id>/dates')
def api_dates(node_id):
    node_id = node_id.lower()
    version = request.args.get('version', '1')

    logger.info("__ api_dates()  version = {}".format(version))

    nodes_dict = export.list_node_dates(version)

    if not node_id in nodes_dict:
        logger.debug("nodes_dict.keys(): " + ','.join([x for x in nodes_dict]))
        #logger.debug("nodes_dict: " + json.dumps(nodes_dict))
        raise InvalidUsage("node_id not found in nodes_dict: " + node_id, status_code=STATUS_Bad_Request)

    dates = nodes_dict[node_id]

    logger.debug("dates: " + str(dates))

    obj = {}
    obj['data'] = sorted(dates, reverse=True)

    return jsonify(obj)

@api.route('/1/nodes_last_update/')
def api_nodes_last_update():
    return jsonify(export.get_nodes_last_update_dict())

@api.route('/1/nodes/<node_id>/export')
def api_export(node_id):
    date = request.args.get('date')
    version = request.args.get('version', '1')
    sort_type = request.args.get('sort', 'desc').lower()[:3]
    
    logger.info("__ api_export()  date = {}, version = {}  sort_type = {} ".format(str(date), str(version), sort_type))

    if not date:
        raise InvalidUsage("date is empty", status_code=STATUS_Not_Found)

    r = re.compile('\d{4}-\d{1,2}-\d{1,2}')

    if not r.match(date):
        raise InvalidUsage("date format not correct", status_code=STATUS_Not_Found)

    logger.info("accepted date: %s" %(date))

    def generate():
        for row in export.export_generator(node_id, date, False, ';', version=version):
            yield row + '\n'

    if sort_type in ['non', 'fal']:   # 'none', 'false'
        return Response(stream_with_context(generate()), mimetype='text/csv')
    else:
        l = list(generate())
        if sort_type == 'asc':
            l.sort()
        else:
            l.sort(reverse = True)
        return Response(stream_with_context(l), mimetype='text/csv')

if __name__ == '__main__':
    app.run(host='0.0.0.0')
    