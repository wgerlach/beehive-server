#!/usr/bin/env python

import logging, time, argparse, sys
from cassandra.cluster import Cluster

#start container:
#docker run -it  -v ${DATA}/export:/export --link beehive-cassandra:cassandra --rm waggle/beehive-server /bin/bash


LOG_FORMAT='%(asctime)s - %(name)s - %(levelname)s - line=%(lineno)d - %(message)s'
formatter = logging.Formatter(LOG_FORMAT)

handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)

logger.addHandler(handler)

CASSANDRA_HOST="cassandra"

def export(node_id, date, ttl):
    cluster = Cluster(contact_points=[CASSANDRA_HOST])
    session = None

    while not session:
        print "try to connect"
        try: # Might not immediately connect. That's fine. It'll try again if/when it needs to.
            session = cluster.connect('waggle')
        except:
            logger.warning("WARNING: Cassandra connection to " + CASSANDRA_HOST + " failed.")
            logger.warning("The process will attempt to re-connect at a later time.")
        if not session:
            time.sleep(3)

    if not ttl:
        statement = "SELECT node_id, date, plugin_id, plugin_version, plugin_instance, timestamp, sensor, sensor_meta, data "+ \
                    "FROM waggle.sensor_data "+ \
                    "WHERE node_id='%s' AND date='%s'" %(node_id, date)
    else:
        statement = "SELECT node_id, date, plugin_id, plugin_version, plugin_instance, timestamp, sensor, sensor_meta, data "+ \
                    "FROM waggle.sensor_data_ttl "+ \
                    "WHERE node_id='%s'" %(node_id)

    rows = session.execute(statement)


    for (node_id, date, plugin_id, plugin_version, plugin_instance, timestamp, sensor, sensor_meta, data) in rows:
        print "%s,%s,%s,%s,%s,%s,%s,%s,%s" % (node_id, date, plugin_id, plugin_version, plugin_instance, timestamp, sensor, sensor_meta, data)


if __name__ == "__main__":
    node_id=None
    date=None
    
    parser = argparse.ArgumentParser()
    #parser.add_argument('--logging', dest='enable_logging', help='write to log files instead of stdout', action='store_true')
    parser.add_argument('--ttl', dest='ttl', help='export only ttl data (latest sensor data)', action='store_true')
    parser.add_argument('--node_id', dest='node_id', help='node_id')
    parser.add_argument('--date', dest='date', help='date (not needed with ttl), format: YYYY-MM-DD, e.g. 2016-01-21')
    
    
    args = parser.parse_args()
    
    if not args.node_id:
        logger.error("node_id not defined")
        parser.print_help()
        sys.exit(1)
    
    if (not args.ttl) and (not args.date):
        logger.error("neither ttl nor date provided")
        parser.print_help()
        sys.exit(1)
        
        
    export(args.node_id, args.date, args.ttl)
        
   
