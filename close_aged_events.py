#!/usr/bin/env python

import logging
import requests
import time
import multiprocessing
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger("LOGGER")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(name)s:%(levelname)s:%(message)s")
file_handler = logging.FileHandler("closed_events.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


# Set minutes to Zero to remove all events in Event Class
# To keep all events within the last 10 minutes. Set minutes to 10.

minutes = 10
event_class = '/Unknown'
url = 'https://zenoss5.zenoss.zenoss.sup'
username = 'zenoss'
password = 'zenoss'


# Number of events to process (pull from server) at a time. Max limit is 1000.
limit = 100
start = 0
open_events_count = 0
closed_events_count = 0


secs = minutes * 60
now_secs = time.time()
lookback_secs = now_secs - secs
date_output_format = "%Y-%m-%d %H:%M:%S"
date_now = time.strftime(date_output_format, time.localtime(time.time()))
lookback_time = time.strftime(date_output_format, time.localtime((lookback_secs)))


class GetEvents(object):
    event_counter_total = 0

    def __init__(self, first_seen=None, last_seen=None, event_class=event_class, event_id=None):
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.event_class = event_class
        self.event_id = event_id

        GetEvents.event_counter_total += 1

    def event_info(self):
        print("EVID: %s \nDeviceClass: %s\nCurrent time: %s\nFirst seen %s\nLast seen %s \n"
              % (self.event_id, self.event_class, date_now, time.strftime(date_output_format, time.localtime(self.first_seen)),
                 time.strftime(date_output_format, time.localtime(self.last_seen))))


def get_events(start, limit):
    try:
        query_payload = {"action": "EventsRouter", "method": "query", "data": [
            {"start": start, "limit": limit, "params": {"eventClass": event_class, "eventState": [0]}}], "tid": 1}
        r = requests.post(url+'/zport/dmd/evconsole_router',
                          auth=(username, password), json=query_payload, verify=False)
        if r.status_code is not 200:
            print("Problem with server status_code: {}".format(r.status_code))
            exit(1)

        data = r.json()

        # create dictionary from event
        event_info_dict = data["result"]["events"]
        # logger.debug("Number of dictonaries from json file is {}".format(len(event_info_dict)))

    except Exception as e:
        print("\n*** No data recieved. Check connection information ***\n" + str(e))
        exit(1)

    return event_info_dict, len(event_info_dict)


def close_events(evid_close_list):
    ''' submit api post to close the list of events '''
    evid_close_list = [x.encode("ascii", "ignore") for x in evid_close_list]

    close_payload = {"action": "EventsRouter", "method": "close", "data": [
        {"evids": evid_close_list, "params": {"eventClass": event_class}}], "tid": 1}
    try:
        c = requests.post(url+'/zport/dmd/evconsole_router',
                          auth=(username, password), json=close_payload, verify=False)
        if c.status_code is not 200:
            print("Problem with server status_code: {}".format(c.status_code))
            exit(1)

    except Exception as e:
        print("\n*** Check connection ***\n" + str(e))
        exit(1)


def open_events(open_obj_list):
    ''' Display events that will stay open'''
    for i in open_obj_list:
        print("Open:")
        i.event_info()


def process_events(event_dict_value):
    ''' process dictionary returned from api query '''
    closeList = []
    openList = []
    evid_close_list = []
    num_events_processed = 0
    num_closed_events = 0
    num_open_events = 0

    # for loop processing generator items
    for e in (events for events in event_dict_value):
        num_events_processed += 1
        event_dict = dict(e.items())
        first_seen = event_dict["firstTime"]
        last_seen = event_dict["lastTime"]
        event_class = event_dict["eventClass"]["text"].encode("ascii", "ignore")
        event_id = event_dict["evid"].encode("ascii", "ignore")

        event_obj = GetEvents(first_seen, last_seen, event_class,
                              event_id.encode("ascii", "ignore"))

        if event_obj.last_seen < lookback_secs:
            closeList.append(event_obj)
            evid_close_list.append(event_obj.event_id)
            num_closed_events += 1
            print("Closed:")
            event_obj.event_info()
            if len(evid_close_list) < limit:
                continue
            # logger.debug("evid_close_list inside process_events() :{}".format(evid_close_list))
            close_events(evid_close_list)
        else:
            openList.append(event_obj)
            num_open_events += 1
            if len(openList) < limit:
                continue
            open_events(openList)

    # logger.debug("num_events_processed: {}\nnum_open_events: {}\
    #     \nnum_closed_events :{}".format(num_events_processed, num_open_events, num_closed_events))

    return num_events_processed, num_open_events, num_closed_events


event_dict_value, event_count = get_events(start, limit)

while True:
    events_processed, num_open_events, num_closed_events = process_events(event_dict_value)
    # check for empty value returned after processing all events
    if events_processed == 0:
        break
    else:
        event_dict_value, event_count = get_events(start + events_processed, limit)
        event_count -= events_processed
        closed_events_count += num_closed_events
        open_events_count += num_open_events


if __name__ == "__main__":
    p = multiprocessing.Process(target=get_events, args=(start, limit))
    p.start()
    p.join()

    print("Total events: {}".format(GetEvents.event_counter_total))
    print("Open {}".format(open_events_count))
    print("Closed {}".format(closed_events_count))
