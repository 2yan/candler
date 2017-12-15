import sql_tools
import sqlite3
import time
import pandas as pd
import requests
from datetime import datetime, timedelta
import threading

class Candler():
    
    r = None
    url = None
    tuner = None
    fire = None
    stopped = True
    product_id = None
    last_message = None
    time_difference = None
    candle_width_seconds = None
    
    def __init__(self,product_id, candle_width_seconds = 60.0000000001 , url = 'https://api.gdax.com'):
        #Initializes Values
        self.url = url
        self.stopped = True
        self.product_id = product_id
        self.last_message = datetime.now()
        self.candle_width_seconds = candle_width_seconds
        self.fire = sql_tools.IcePick(sqlite3, 'fire.db')
        self.time_difference = pd.to_datetime(self.__get('/time')['iso']) - datetime.now()
        
        #end = datetime.now() - timedelta(seconds = 60 * 60 * 12)
        #start = end - timedelta(seconds = 60 * 200)
        #self.initalize(products['id'], start, end, 60.0000000000001)
        self.tuner = threading.Thread(target = self.__tuner)
        self.tuner.start()
        
    def start(self):
        #Will start the live candle download thread
        self.stopped = False
    def stop(self):
        #Will stop the live canlde download thread
        self.stopped = True
        
    def __get(self, path, params=None):
        #Requests passthrough, tries to avoid the too many requests code by adding pauses
        self.last_message
        now = datetime.now()
        if (now - self.last_message).total_seconds() <= 1:
            time.sleep(1)
        r = requests.get(self.url + path, params=params, timeout=30, verify = False)
        if r.status_code == 429:
            time.sleep(2)
            r = requests.get(self.url + path, params=params, timeout=30, verify = False)
        self.r = r
        self.last_message = datetime.now()
        return r.json()

    def get_candles(self, start=None, end=None, granularity=None):
        #Downloads new candles, will not put them in sql,just give it a local start and end time in with a granualrity in seconds 
        params = {}
        if start is not None:
            start = start + self.time_difference
            params['start'] = start.isoformat()
        if end is not None:
            end = end + self.time_difference
            params['end'] = end.isoformat()
        if granularity is not None:
            params['granularity'] = granularity
        candles = self.__get('/products/{}/candles'.format(str(self.product_id)), params=params)
        candles = pd.DataFrame(candles, columns = [ 'time', 'low', 'high', 'open', 'close', 'volume' ])
        candles['time_string'] = candles['time'].apply(datetime.fromtimestamp)
        candles.sort_values('time', inplace= True)
        candles.set_index('time', inplace= True)
        return candles
    
    def add_candles(self, candles):
        #adds Downloaded Candles to the SQL database
        current = self.__fire.get_data(self.product_id, ['time'])
        s1 = candles.index
        s2 = current['time']
        remove_list = pd.Series(list(set(s1).intersection(set(s2))))
        remove_list = "','".join(str(x) for x in list(remove_list))
        sql = """
        delete from [{}]
        where time in ('{}')
        """.format( self.product_id, remove_list)
        with sqlite3.connect('fire.db', check_same_thread = False) as con:
            con.execute(sql)
            con.commit()
            candles.to_sql(self.product_id, con, if_exists = 'append')
        return 

    
    def __tuner(self):
        #Runs concurrently in an extra thread and keeps the candles updated. 
        def update_candles():
            print('updating')
            #Downloads the last two candles and adds them, is really only useful for live updates. 
            end = datetime.now()
            start = end - timedelta(seconds = self.candle_width_seconds * 2)
            candles = self.get_candles(self.product_id, start=start, end=end, granularity=self.candle_width_seconds)
            self.add_candles(self.product_id, candles)
        
        current_minute = datetime.now().minute
        while True:
            if not self.stopped:
                
                now = datetime.now().minute
                if now != current_minute:
                    update_candles()
                    current_minute = now
    
candler = Candler('ETH-USD')