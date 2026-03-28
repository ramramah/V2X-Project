import csv
import json
from pathlib import Path


class StatsLogger:
    def __init__(self):
        self.initialized = False
        self.message_file = None
        self.message_writer = None
        self.sessions = {}
        self.prefix = "run"

    def initialize(self, prefix: str = "run", output_dir: str = "."):
        if self.initialized:
            return

        self.prefix = prefix
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        message_path = output_path / f"{prefix}_message_events.csv"

        self.message_file = open(message_path, "w", newline="", encoding="utf-8")
        self.message_writer = csv.DictWriter(
            self.message_file,
            fieldnames=[
                "wall_time",
                "sim_time",
                "direction",
                "topic",
                "msg_type",
                "station_id",
                "receiver_id",
                "manoeuvre_id",
                "session_id",
                "message_id",
                "python_tx_wall_time",
                "python_tx_sim_time",
                "delay_ms",
                "raw_json",
            ],
        )
        self.message_writer.writeheader()
        self.initialized = True

    def log_message_event(
        self,
        *,
        wall_time=None,
        sim_time=None,
        direction="",
        topic="",
        msg_type="",
        station_id="",
        receiver_id="",
        manoeuvre_id="",
        session_id="",
        message_id="",
        python_tx_wall_time="",
        python_tx_sim_time="",
        delay_ms="",
        raw_json=None,
    ):
        if not self.initialized:
            return

        if raw_json is None:
            raw_json = ""
        elif not isinstance(raw_json, str):
            raw_json = json.dumps(raw_json, ensure_ascii=False)

        self.message_writer.writerow(
            {
                "wall_time": wall_time,
                "sim_time": sim_time,
                "direction": direction,
                "topic": topic,
                "msg_type": msg_type,
                "station_id": station_id,
                "receiver_id": receiver_id,
                "manoeuvre_id": manoeuvre_id,
                "session_id": session_id,
                "message_id": message_id,
                "python_tx_wall_time": python_tx_wall_time,
                "python_tx_sim_time": python_tx_sim_time,
                "delay_ms": delay_ms,
                "raw_json": raw_json,
            }
        )
        self.message_file.flush()

    def start_session(self, session_id, manoeuvre_id, requester_station_id, request_tx_wall_time, request_tx_sim_time):
        if not session_id:
            return

        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "session_id": session_id,
                "manoeuvre_id": manoeuvre_id,
                "requester_station_id": requester_station_id,
                "first_request_tx_wall_time": request_tx_wall_time,
                "first_request_tx_sim_time": request_tx_sim_time,
                "first_response_rx_wall_time": None,
                "first_response_rx_sim_time": None,
                "termination_rx_wall_time": None,
                "termination_rx_sim_time": None,
                "completed": False,
            }

    def mark_response_rx(self, session_id, wall_time, sim_time):
        if not session_id:
            return
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "session_id": session_id,
                "manoeuvre_id": "",
                "requester_station_id": "",
                "first_request_tx_wall_time": None,
                "first_request_tx_sim_time": None,
                "first_response_rx_wall_time": wall_time,
                "first_response_rx_sim_time": sim_time,
                "termination_rx_wall_time": None,
                "termination_rx_sim_time": None,
                "completed": False,
            }
            return

        if self.sessions[session_id]["first_response_rx_wall_time"] is None:
            self.sessions[session_id]["first_response_rx_wall_time"] = wall_time
            self.sessions[session_id]["first_response_rx_sim_time"] = sim_time

    def mark_termination_rx(self, session_id, wall_time, sim_time):
        if not session_id:
            return
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "session_id": session_id,
                "manoeuvre_id": "",
                "requester_station_id": "",
                "first_request_tx_wall_time": None,
                "first_request_tx_sim_time": None,
                "first_response_rx_wall_time": None,
                "first_response_rx_sim_time": None,
                "termination_rx_wall_time": wall_time,
                "termination_rx_sim_time": sim_time,
                "completed": True,
            }
            return

        self.sessions[session_id]["termination_rx_wall_time"] = wall_time
        self.sessions[session_id]["termination_rx_sim_time"] = sim_time
        self.sessions[session_id]["completed"] = True

    def close(self, output_dir: str = "."):
        if not self.initialized:
            return

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        sessions_path = output_path / f"{self.prefix}_mcm_sessions.csv"

        with open(sessions_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "session_id",
                    "manoeuvre_id",
                    "requester_station_id",
                    "first_request_tx_wall_time",
                    "first_request_tx_sim_time",
                    "first_response_rx_wall_time",
                    "first_response_rx_sim_time",
                    "termination_rx_wall_time",
                    "termination_rx_sim_time",
                    "request_to_response_ms",
                    "request_to_termination_ms",
                    "completed",
                ],
            )
            writer.writeheader()

            for session_id, s in self.sessions.items():
                req_to_resp = ""
                if s["first_request_tx_wall_time"] is not None and s["first_response_rx_wall_time"] is not None:
                    req_to_resp = (s["first_response_rx_wall_time"] - s["first_request_tx_wall_time"]) * 1000.0

                req_to_term = ""
                if s["first_request_tx_wall_time"] is not None and s["termination_rx_wall_time"] is not None:
                    req_to_term = (s["termination_rx_wall_time"] - s["first_request_tx_wall_time"]) * 1000.0

                writer.writerow(
                    {
                        "session_id": session_id,
                        "manoeuvre_id": s["manoeuvre_id"],
                        "requester_station_id": s["requester_station_id"],
                        "first_request_tx_wall_time": s["first_request_tx_wall_time"],
                        "first_request_tx_sim_time": s["first_request_tx_sim_time"],
                        "first_response_rx_wall_time": s["first_response_rx_wall_time"],
                        "first_response_rx_sim_time": s["first_response_rx_sim_time"],
                        "termination_rx_wall_time": s["termination_rx_wall_time"],
                        "termination_rx_sim_time": s["termination_rx_sim_time"],
                        "request_to_response_ms": req_to_resp,
                        "request_to_termination_ms": req_to_term,
                        "completed": s["completed"],
                    }
                )

        if self.message_file:
            self.message_file.close()

        self.initialized = False


stats_logger = StatsLogger()
