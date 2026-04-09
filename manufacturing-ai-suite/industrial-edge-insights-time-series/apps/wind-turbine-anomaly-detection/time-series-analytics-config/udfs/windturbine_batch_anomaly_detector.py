#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

""" Custom user defined function for batch anomaly detection on
the windturbine speed and generated power data. Processes multiple
points at once for improved throughput using Intel Extension for
Scikit-learn vectorized operations. """

import os
import logging
import pickle
import time
import math
import warnings
from collections import deque
from kapacitor.udf.agent import Agent, Handler
from kapacitor.udf import udf_pb2
import numpy as np
import requests
from sklearnex import patch_sklearn, config_context
patch_sklearn()
from sklearn.linear_model import LinearRegression

warnings.filterwarnings(
    "ignore",
    message=".*Threading.*parallel backend is not supported by Extension for Scikit-learn.*"
)


log_level = os.getenv('KAPACITOR_LOGGING_LEVEL', 'INFO').upper()
enable_benchmarking = os.getenv('ENABLE_BENCHMARKING', 'false').upper() == 'TRUE'
total_no_pts = int(os.getenv('BENCHMARK_TOTAL_PTS', "0"))
logging_level = getattr(logging, log_level, logging.INFO)

# Configure logging
logging.basicConfig(
    level=logging_level,  # Set the log level to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
)

logger = logging.getLogger()

# Batch anomaly detection on the windturbine speed and generated power data
class BatchAnomalyDetectorHandler(Handler):
    """ Handler for the batch anomaly detection UDF. It collects incoming points
    in batches and processes them using vectorized operations for improved
    throughput and latency, leveraging Intel Extension for Scikit-learn.
    """
    def __init__(self, agent):
        self._agent = agent
        # read the saved model and load it
        def load_model(filename):
            with open(filename, 'rb') as f:
                model = pickle.load(f)
            return model
        model_path = os.getenv('MODEL_PATH')
        model_path = os.path.abspath(model_path)
        self.rf = load_model(model_path)

        self.device = os.getenv('DEVICE', 'auto').lower()

        # wind speed and active power field name in the influxdb measurements
        self.x_name = "wind_speed"
        self.y_name = "grid_active_power"

        # hyper-params for anomaly classification
        self.n_steps = 3
        self.last_states = deque(self.n_steps*[0], self.n_steps)
        self.last_anomalies = deque(self.n_steps*[0], self.n_steps)
        self.error_threshold = 0.15
        self.anomalies = []
        self.cut_in_speed = 3
        self.cut_out_speed = 14
        self.min_power_th = 50

        # batch processing state
        self._batch_points = []
        self._begin_response = None

        self.points_received = {}
        global total_no_pts
        self.max_points = int(total_no_pts)

    def info(self):
        """ Return the InfoResponse. Describing the properties of this Handler
        """
        response = udf_pb2.Response()
        response.info.wants = udf_pb2.BATCH
        response.info.provides = udf_pb2.BATCH
        return response

    def init(self, init_req):
        """ Initialize the Handler with the provided options.
        """
        response = udf_pb2.Response()
        response.init.success = True
        return response

    def snapshot(self):
        """ Create a snapshot of the running state of the process.
        """
        response = udf_pb2.Response()
        response.snapshot.snapshot = b''
        return response

    def restore(self, restore_req):
        """ Restore a previous snapshot.
        """
        response = udf_pb2.Response()
        response.restore.success = False
        response.restore.error = 'not implemented'
        return response

    def begin_batch(self, begin_req):
        """ A batch has begun. Initialize collection for batch processing.
        """
        self._batch_points = []
        self._begin_response = udf_pb2.Response()
        self._begin_response.beginBatch.CopyFrom(begin_req)
        logger.info("Batch started - collecting points for batch processing")

    def point(self, point):
        """ A point has arrived. Accumulate it for batch processing.
        """
        self._batch_points.append(point)

    def end_batch(self, end_req):
        """ The batch is complete. Process all accumulated points using
        vectorized operations for improved throughput.
        """
        batch_start_time = time.time_ns()
        batch_size = len(self._batch_points)
        logger.info("Processing batch of %d points", batch_size)

        # Write begin batch response
        self._agent.write_response(self._begin_response)

        if batch_size == 0:
            # Empty batch - just send end
            response = udf_pb2.Response()
            response.endBatch.CopyFrom(end_req)
            self._agent.write_response(response)
            return

        # Extract all x and y values from the batch for vectorized prediction
        x_values = []
        y_values = []
        valid_indices = []  # indices of points that have both x and y
        sources = []

        for i, point in enumerate(self._batch_points):
            stream_src = None
            if "source" in point.tags:
                stream_src = point.tags["source"]
            elif "source" in point.fieldsString:
                stream_src = point.fieldsString["source"]
            sources.append(stream_src)

            global enable_benchmarking
            if enable_benchmarking:
                if stream_src not in self.points_received:
                    self.points_received[stream_src] = 0
                if self.points_received[stream_src] >= self.max_points:
                    continue
                self.points_received[stream_src] += 1

            x = None
            y = None
            if self.x_name in point.fieldsDouble:
                x = point.fieldsDouble[self.x_name]
            if self.y_name in point.fieldsDouble:
                y = point.fieldsDouble[self.y_name]

            if x is not None and y is not None:
                x_values.append(x)
                y_values.append(y)
                valid_indices.append(i)
            else:
                logger.error("No input received for %s %s, %s %s at batch index %d. "
                             "Skipping anomaly detection.",
                             self.x_name, x, self.y_name, y, i)

        # Vectorized prediction: predict all valid points at once
        # This is the key performance optimization - sklearnex accelerates
        # batch predictions significantly compared to point-by-point inference
        predictions = np.array([])
        if valid_indices:
            x_array = np.array(x_values).reshape(-1, 1)
            predictions = self.rf.predict(x_array)

        # Map predictions back to points and apply anomaly classification
        pred_idx = 0
        for i, point in enumerate(self._batch_points):
            point_start_time = time.time_ns()

            if i in valid_indices:
                x = x_values[pred_idx]
                y = y_values[pred_idx]
                y_pred = predictions[pred_idx]
                pred_idx += 1

                point.fieldsDouble["analytic"] = True
                check_for_anomalies = self._should_check_anomaly(x, y)

                if check_for_anomalies:
                    error = (y_pred - y) / (y)
                    if error > self.error_threshold:
                        self.last_states.append(1)
                        self.last_anomalies.append((x, y))
                    else:
                        self.last_states.append(0)

                    # check if there are consecutive 3 anomalies, and then filter
                    # out any false positives
                    if sum(self.last_states) == self.n_steps:
                        x_feat = list(zip(*self.last_anomalies))[0]
                        x_feat = np.reshape(x_feat, (-1, 1))
                        y_feat = list(zip(*self.last_anomalies))[1]

                        with config_context(target_offload=self.device,
                                            allow_fallback_to_host=True):
                            lm = LinearRegression()
                            lm.fit(x_feat, y_feat)

                        if abs(lm.coef_) < 200:
                            self.anomalies.append((x, y))
                            if error < 0.3:
                                point.fieldsDouble["anomaly_status"] = 0.3
                            elif error < 0.6:
                                point.fieldsDouble["anomaly_status"] = 0.6
                            else:
                                point.fieldsDouble["anomaly_status"] = 1.0
                        else:
                            self.last_states.append(0)
            else:
                point.fieldsDouble["analytic"] = False

            # Ensure anomaly_status field exists with default value
            if "anomaly_status" not in point.fieldsDouble:
                point.fieldsDouble["anomaly_status"] = 0.0

            time_now = time.time_ns()
            processing_time = time_now - point_start_time
            end_end_time = time_now - point.time
            point.fieldsDouble["processing_time"] = processing_time
            point.fieldsDouble["end_end_time"] = end_end_time

            # Write point response
            response = udf_pb2.Response()
            response.point.CopyFrom(point)
            self._agent.write_response(response)

        # Write end batch response
        response = udf_pb2.Response()
        response.endBatch.CopyFrom(end_req)
        self._agent.write_response(response)

        batch_end_time = time.time_ns()
        batch_processing_time = (batch_end_time - batch_start_time) / 1e6
        logger.info("Batch of %d points processed in %.2f ms (%.2f ms/point)",
                     batch_size, batch_processing_time,
                     batch_processing_time / batch_size if batch_size > 0 else 0)

    def _should_check_anomaly(self, x, y):
        """ Determine if a point should be checked for anomalies based on
        wind speed and power thresholds.
        """
        if math.isnan(x) or math.isnan(y):
            self.last_states.append(0)
            return False

        if ((x <= self.cut_in_speed) or (x > self.cut_in_speed and y < self.min_power_th)
                or (x > self.cut_out_speed)):
            self.last_states.append(0)
            return False

        return True


if __name__ == '__main__':
    # Create an agent
    agent = Agent()

    # Create a handler and pass it an agent so it can write points
    h = BatchAnomalyDetectorHandler(agent)

    # Set the handler on the agent
    agent.handler = h

    # Anything printed to STDERR from a UDF process gets captured
    # into the Kapacitor logs.
    agent.start()
    agent.wait()
