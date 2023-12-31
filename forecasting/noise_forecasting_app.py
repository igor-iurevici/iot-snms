# -*- coding: utf-8 -*-
"""snms_noise_forecasting_app

Automatically generated by Colaboratory.

"""

import pytz
import os
from datetime import datetime
desired_timezone = pytz.timezone('Etc/GMT-2')
os.environ['TZ'] = 'Etc/GMT-2'
datetime.now(desired_timezone)

import pandas as pd
from prophet import Prophet
import datetime
import time

from influxdb_client import InfluxDBClient, Point, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS
from scipy.sparse import data

# InfluxDB setup
token = ""
org = ""
url = ""
client = InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)
bucket = "snms_agg"

lastChecked = None

while(True):
    # Noise data query
    query = 'from(bucket:"snms_agg")' \
            ' |> range(start:-2h)'\
            ' |> filter(fn: (r) => r._measurement == "sample")' \
            ' |> filter(fn: (r) => r._field == "noise")'

    result = client.query_api().query(org=org, query=query)

    # Extracting data from FluxTable
    raw_data = []
    for table in result:
        for record in table.records:
            raw_data.append((record.get_value(), record.get_time()+datetime.timedelta(hours=2)))

    lastSample = raw_data[-1]

    if (lastSample != lastChecked):
        lastChecked = lastSample

        df = pd.DataFrame(raw_data, columns=['y', 'ds'])

        # Removing timezone
        for col in df.select_dtypes(['datetimetz']).columns:
          df[col] = df[col].dt.tz_convert(None)

        model = Prophet()
        model.fit(df)
        future = model.make_future_dataframe(periods=1, freq='10s')
        forecast = model.predict(future)
        forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail()
        forecast['measurement'] = "forecast"
        cp = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper', 'measurement']].copy()

        #print(forecast['ds'].tail())
        lines = [str(cp["measurement"][d])
                + " "
                + "noise_yhat=" + str(cp["yhat"][d]) + ","
                + "noise_yhat_lower=" + str(cp["yhat_lower"][d]) + ","
                + "noise_yhat_upper=" + str(cp["yhat_upper"][d])
                + " " + str(int(time.mktime(cp['ds'][d].timetuple()))) + "000000000" for d in range(len(cp))]

        lines=[lines[-1]]

        try:
          # Write the data
          _write_client = client.write_api(write_options=WriteOptions(batch_size=1000,
                                                                    flush_interval=10_000,
                                                                    jitter_interval=2_000,
                                                                    retry_interval=5_000))
          _write_client.write(bucket, org, lines)
          print("Sent correctly!", lines)
        except Exception as e:
          print("Failed to send data:", str(e))
          client.close()
