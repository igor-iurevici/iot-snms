# Smart Noise Monitoring System :sound:

### About
SMNS is an indoor noise monitoring system exploiting IoT devices (ESP32 microcontroller and MAX4466 microphone) to detect, store (on [InfluxDB](https://www.influxdata.com)) and alert (on [Grafana](https://grafana.com) dashboard) when certain noise level is reached for a specific amount of time. </br>
A Flask web page is available to set the system parameters. </br>
Moreover [Prophet](https://facebook.github.io/prophet/), a time series forecasting procedures predicts near real-time noise values in the near future.

### More
Check out the [report](https://github.com/igor-iurevici/iot-snms/blob/main/report.pdf) and [presentation](https://github.com/igor-iurevici/iot-snms/blob/main/presentation.pdf) for further details.
