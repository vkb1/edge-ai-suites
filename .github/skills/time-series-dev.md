# Time Series Development Skill

## Description

This skill provides knowledge for developing and extending the Industrial Edge Insights Time Series application, including creating new sample apps, writing User-Defined Functions (UDFs), configuring data ingestion pipelines, and training ML models.

## Instructions

### Architecture Overview

The Industrial Edge Insights Time Series platform uses a TICK-stack-based architecture:

```
Data Sources (CSV/Sensors)
    │
    ├── MQTT Publisher ──► MQTT Broker (Mosquitto:1883) ──► Telegraf
    └── OPC-UA Server (:4840) ──────────────────────────► Telegraf
                                                              │
                                                              ▼
                                                         InfluxDB (datain)
                                                              │
                                                              ▼
                                                    Time Series Analytics
                                                    Microservice (TSAM/Kapacitor)
                                                              │
                                                              ├── UDF Processing (Python)
                                                              ├── TICKscript Evaluation
                                                              └── Alert Output (MQTT)
                                                              │
                                                              ▼
                                                         InfluxDB (results)
                                                              │
                                                              ▼
                                                         Grafana (:3000)
                                                              │
                                                              ▼
                                                         nginx (:15443)
```

### Creating a New Sample App

1. Create a new directory under `apps/`:
   ```
   apps/<app-name>/
   ├── telegraf-config/Telegraf.conf
   ├── time-series-analytics-config/
   │   ├── config.json
   │   ├── models/            # Trained model files (.pkl, .json)
   │   ├── udfs/              # Python UDF scripts
   │   │   └── <udf_name>.py
   │   └── tick_scripts/      # Kapacitor TICKscripts
   │       └── <udf_name>.tick
   ├── simulation-data/       # CSV files for testing
   ├── grafana-dashboard.json
   └── training/              # ML training scripts (optional)
   ```

2. Add the app name to `SAMPLE_APP_LIST` in the `Makefile`.

3. Create the Telegraf configuration for your data ingestion protocol:
   - MQTT: Subscribe to topics matching your sensor data format
   - OPC-UA: Configure node IDs for the OPC-UA server
   - Set appropriate `collection_interval`, `flush_interval`, and `metric_batch_size`

4. Write a `config.json` specifying UDFs and alert destinations:
   ```json
   {
     "udfs": {
       "name": "<udf_name>",
       "models": "<model_file>",
       "device": "cpu"
     },
     "alerts": {
       "mqtt": {
         "mqtt_broker_host": "ia-mqtt-broker",
         "mqtt_broker_port": 1883,
         "name": "my_mqtt_broker"
       }
     }
   }
   ```

5. Create simulation data CSV files matching your Telegraf input schema.

6. Create a Grafana dashboard JSON to visualize your data.

### Writing User-Defined Functions (UDFs)

UDFs are Python scripts executed by the TSAM (Kapacitor) microservice:

- UDFs receive streaming time-series data points from Kapacitor
- They process data using ML models (scikit-learn with Intel Extension)
- Results are written back to InfluxDB and/or sent as alerts via MQTT

**Key patterns from existing UDFs:**

```python
# Load Intel Extension for Scikit-learn
from sklearnex import patch_sklearn
patch_sklearn()

# Load model
import joblib
model = joblib.load("path/to/model.pkl")

# Process incoming data point
def process(point):
    features = extract_features(point)
    prediction = model.predict([features])
    return build_result(prediction)
```

**UDF requirements:**
- Pin all dependencies in `udfs/requirements.txt`
- Support `device` parameter (`cpu`, `gpu`, `auto`) for Intel Extension
- Handle edge cases (missing data, out-of-range values)
- Include feature filtering logic (e.g., minimum current thresholds)
- Output structured JSON with prediction, confidence, and explanation fields

### Writing TICKscripts

TICKscripts define the Kapacitor data processing pipeline:

```tick
dbrp "datain"."autogen"

stream
    |from()
        .measurement('<measurement_name>')
    @<udf_name>()
    |influxDBOut()
        .database('datain')
        .measurement('<output_measurement>')
```

### Configuring Multi-Stream Ingestion

For high-throughput scenarios, use multi-stream Telegraf configs:

```bash
# Generate multi-stream config
make up_mqtt_ingestion app=wind-turbine-anomaly-detection num_of_streams=3

# The generate-telegraf-config.py script creates Telegraf_multi_stream.conf
# with separate input sections per stream, each connecting to a different
# simulator instance
```

### Training ML Models

1. Set up a Python virtual environment in the `training/` directory
2. Use Jupyter notebooks for interactive development
3. Export trained models as `.pkl` files using `joblib.dump()`
4. Place model files in `time-series-analytics-config/models/`
5. Document the training process, dataset, and performance metrics in `training/README.md`

### Environment Configuration

Key `.env` variables:
- `SAMPLE_APP` — Active sample application name
- `INFLUXDB_USERNAME` / `INFLUXDB_PASSWORD` — Database credentials (5+ chars / 10+ alphanumeric with digit)
- `VISUALIZER_GRAFANA_USER` / `VISUALIZER_GRAFANA_PASSWORD` — Grafana credentials
- `CONTINUOUS_SIMULATOR_INGESTION` — `true` for looping, `false` for single pass
- `GRAFANA_PORT` — Grafana/nginx port (default: 3000)
- `IMAGE_SUFFIX` — Docker image version tag
- `LOG_LEVEL` — Logging level (INFO/DEBUG)
- `INFLUXDB_RETENTION_DURATION` — Data retention period (e.g., `1h0m0s`)

### Debugging Tips

- Check TSAM startup: `docker logs ia-time-series-analytics-microservice`
- Success indicator: `"Kapacitor Tasks Enabled Successfully"`
- Verify data in InfluxDB: `docker exec -it ia-influxdb influx -execute "SELECT * FROM datain../<measurement> LIMIT 5"`
- Check MQTT messages: `docker exec -it ia-mqtt-broker mosquitto_sub -t '#'`
- Verify UDF upload: Check nginx logs for POST to `/ts-api/udfs/package`
- Config post: Check response from POST to `/ts-api/config`
