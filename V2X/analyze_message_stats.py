#!/usr/bin/env python3

import argparse
import csv
import statistics
from pathlib import Path
from collections import defaultdict

V2X_STATIONS = {0, 1, 2}

def is_v2x_station(station_id):
    try:
        return int(station_id) in V2X_STATIONS
    except Exception:
        return False

def classify_family(msg_type):
    if msg_type == "cam":
        return "CAM"
    if msg_type.startswith("mcm"):
        return "MCM"
    return "OTHER"

def to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fmt_ms(v):
    if v is None:
        return "-"
    return f"{v:.2f} ms"


def fmt_sec(v):
    if v is None:
        return "-"
    return f"{v:.3f} s"


def fmt_pct(v):
    if v is None:
        return "-"
    return f"{v:.2f}%"


def summarize(values):
    values = [v for v in values if v is not None]
    if not values:
        return {
            "count": 0,
            "avg": None,
            "min": None,
            "max": None,
            "median": None,
        }
    return {
        "count": len(values),
        "avg": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "median": statistics.median(values),
    }


def build_message_map(rows):
    messages = {}

    for r in rows:
        message_id = r.get("message_id", "")
        if not message_id:
            continue
        msg_type = r.get("msg_type", "")
        station_id = r.get("station_id", "")


        if message_id not in messages:
            messages[message_id] = {
                "message_id": message_id,
                "msg_type": msg_type,
                "family": classify_family(msg_type),
                "station_id": station_id,
                "tx_station_id": None,
                "receiver_id": str(r.get("receiver_id", "")),
                "manoeuvre_id": str(r.get("manoeuvre_id", "")),
                "session_id": str(r.get("session_id", "")),
                "topic": r.get("topic", ""),
                "tx_seen": False,
                "drop_seen": False,
                "rx_seen": False,
                "tx_wall_time": None,
                "rx_wall_time": None,
                "tx_sim_time": to_float(r.get("python_tx_sim_time")),
                "rx_sim_time": to_float(r.get("sim_time")),
                "delay_ms": None,
            }

        m = messages[message_id]
        direction = r.get("direction", "")
        current_station_id = str(r.get("station_id", "")).strip()
        if direction == "tx":
            m["tx_seen"] = True
            m["tx_wall_time"] = to_float(r.get("wall_time"))
            if station_id != "":
                m["tx_station_id"] = station_id
            tx_sim = to_float(r.get("python_tx_sim_time"))
            if tx_sim is not None:
                m["tx_sim_time"] = tx_sim

        elif direction == "drop":
            m["drop_seen"] = True
            tx_sim = to_float(r.get("python_tx_sim_time"))
            if tx_sim is not None:
                m["tx_sim_time"] = tx_sim

        elif direction == "rx":
            m["rx_seen"] = True
            m["rx_wall_time"] = to_float(r.get("wall_time"))
            rx_sim = to_float(r.get("sim_time"))
            if rx_sim is not None:
                m["rx_sim_time"] = rx_sim

            delay = to_float(r.get("delay_ms"))
            if delay is not None:

                m["delay_ms"] = delay

    # FILTER CAM TO V2X STATIONS ONLY
    filtered_messages = {}

    for message_id, m in messages.items():
        if m["msg_type"] == "cam":
            cam_station = m["tx_station_id"] if m["tx_station_id"] else m["station_id"]

            if is_v2x_station(cam_station):
                filtered_messages[message_id] = m
        else:
            filtered_messages[message_id] = m

    return filtered_messages

def get_type_stats(messages, target_type, sim_duration):
    selected = [m for m in messages.values() if m["msg_type"] == target_type]

    sent = sum(1 for m in selected if m["tx_seen"])
    dropped = sum(1 for m in selected if m["drop_seen"] or (m["tx_seen"] and not m["rx_seen"]))
    observed_rx = sum(1 for m in selected if m["rx_seen"])

    attempted = sent
    loss_pct = ((sent - observed_rx) / sent * 100.0) if sent > 0 else 0.0
    delays_ms = [m["delay_ms"] for m in selected if m["delay_ms"] is not None]

    v2x_sent = sum(
        1 for m in selected
        if m["tx_seen"] and is_v2x_station(m["tx_station_id"] if m["tx_station_id"] else m["station_id"])
    )

    v2x_observed_rx = sum(
        1 for m in selected
        if m["rx_seen"] and is_v2x_station(m["tx_station_id"] if m["tx_station_id"] else m["station_id"])
    )

    return {
        "type": target_type,
        "sent": sent,
        "v2x_sent": v2x_sent,
        "dropped": dropped,
        "observed_rx": observed_rx,
        "v2x_observed_rx": v2x_observed_rx,
        "attempted": attempted,
        "loss_pct": loss_pct,
        "delay_summary_ms": summarize(delays_ms),
        "messages": selected,
        "cam_rate": (sent / sim_duration) if target_type == "cam" and sim_duration > 0 else None,
    }
def get_station_stats(messages, target_type):
    per_station = defaultdict(list)

    for m in messages.values():
        if m["msg_type"] == target_type:
            if target_type == "cam":
                station_key = m["tx_station_id"] if m["tx_station_id"] else m["station_id"]
            else:
                station_key = m["station_id"]

            per_station[station_key].append(m)

    result = []
    for station_id, items in sorted(per_station.items(), key=lambda x: x[0]):
        sent = sum(1 for m in items if m["tx_seen"])
        observed_rx = sum(1 for m in items if m["rx_seen"])

        dropped = max(sent - observed_rx, 0)

        attempted = sent
        loss_pct = (dropped / sent * 100.0) if sent > 0 else 0.0
        delays_ms = [m["delay_ms"] for m in items if m["delay_ms"] is not None]

        result.append({
            "station_id": station_id,
            "sent": sent,
            "dropped": dropped,
            "observed_rx": observed_rx,
            "loss_pct": loss_pct,
            "delay_summary_ms": summarize(delays_ms),
        })
    return result


def get_request_response_wall_stats(messages):
    request_tx_by_session = {}
    response_tx_by_session = {}

    for m in messages.values():
        session_id = m.get("session_id", "")
        if not session_id:
            continue

        if m["msg_type"] == "mcm_request" and m["tx_wall_time"] is not None:
            if session_id not in request_tx_by_session:
                request_tx_by_session[session_id] = {
                    "time": m["tx_wall_time"],
                    "station_id": m["station_id"],
                    "manoeuvre_id": m["manoeuvre_id"],
                }

        elif m["msg_type"] == "mcm_response" and m["tx_wall_time"] is not None:
            if session_id not in response_tx_by_session:
                response_tx_by_session[session_id] = {
                    "time": m["tx_wall_time"],
                    "station_id": m["station_id"],
                    "manoeuvre_id": m["manoeuvre_id"],
                }

    delays_sec = []
    details = []

    for session_id, req in request_tx_by_session.items():
        resp = response_tx_by_session.get(session_id)
        if resp is not None:
            delay_sec = resp["time"] - req["time"]
            delays_sec.append(delay_sec)
            details.append({
                "session_id": session_id,
                "request_station": req["station_id"],
                "response_station": resp["station_id"],
                "manoeuvre_id": req["manoeuvre_id"],
                "delay_sec": delay_sec,
            })

    return summarize(delays_sec), details


def get_session_stats(session_rows):
    request_to_response = []
    request_to_termination = []
    session_durations = []
    completed = 0
    details = []

    for s in session_rows:
        rtr_ms = to_float(s.get("request_to_response_ms"))
        rtt_ms = to_float(s.get("request_to_termination_ms"))

        req_tx_sim = to_float(s.get("first_request_tx_sim_time"))
        term_rx_sim = to_float(s.get("termination_rx_sim_time"))

        duration_sim_sec = None
        if req_tx_sim is not None and term_rx_sim is not None:
            duration_sim_sec = term_rx_sim - req_tx_sim

        if rtr_ms is not None:
            request_to_response.append(rtr_ms / 1000.0)

        if rtt_ms is not None:
            request_to_termination.append(rtt_ms / 1000.0)

        if duration_sim_sec is not None:
            session_durations.append(duration_sim_sec)

        is_completed = str(s.get("completed", "")).lower() in ("true", "1", "yes")
        if is_completed:
            completed += 1

        details.append({
            "session_id": s.get("session_id", ""),
            "requester_station_id": s.get("requester_station_id", ""),
            "manoeuvre_id": s.get("manoeuvre_id", ""),
            "req_to_resp_sec": (rtr_ms / 1000.0) if rtr_ms is not None else None,
            "req_to_term_sec": (rtt_ms / 1000.0) if rtt_ms is not None else None,
            "duration_sim_sec": duration_sim_sec,
            "completed": is_completed,
        })

    return {
        "total_sessions": len(session_rows),
        "completed_sessions": completed,
        "incomplete_sessions": len(session_rows) - completed,
        "request_to_response": summarize(request_to_response),
        "request_to_termination": summarize(request_to_termination),
        "session_duration": summarize(session_durations),
        "details": details,
    }

def print_type_block(type_stats):
    ds = type_stats["delay_summary_ms"]
    print(f"[{type_stats['type']}]")
    print(f"Total sent packets : {type_stats['sent']}")
    print(f"Dropped packets    : {type_stats['dropped']}")
    print(f"Observed RX        : {type_stats['observed_rx']}")
    print(f"Loss               : {fmt_pct(type_stats['loss_pct'])}")

    if type_stats["type"] == "cam":
        if type_stats.get("cam_rate") is not None:
            print(f"CAM rate           : {type_stats['cam_rate']:.2f} msg/s")

    print(f"Average delay      : {fmt_ms(ds['avg'])}")
    print(f"Min delay          : {fmt_ms(ds['min'])}")
    print(f"Max delay          : {fmt_ms(ds['max'])}")
    print()

def print_station_block(title, station_stats):
    print(title)
    print("-" * len(title))
    if not station_stats:
        print("No data\n")
        return

    header = f"{'Station':<10} {'Sent':>8} {'Dropped':>10} {'Observed RX':>14} {'Loss %':>10} {'Avg Delay':>14}"
    print(header)
    print("-" * len(header))

    for s in station_stats:
        print(
            f"{s['station_id']:<10} "
            f"{s['sent']:>8} "
            f"{s['dropped']:>10} "
            f"{s['observed_rx']:>14} " 
            f"{fmt_pct(s['loss_pct']):>10} "
            f"{fmt_ms(s['delay_summary_ms']['avg']):>14}"
        )
    print()


def print_request_response_block(rr_summary, rr_details):
    print("=== MCM REQUEST -> RESPONSE ANALYSIS (wall_time, TX->TX) ===")
    print(f"Completed request->response pairs : {rr_summary['count']}")
    print(f"Average delay                     : {fmt_sec(rr_summary['avg'])}")
    print(f"Min delay                         : {fmt_sec(rr_summary['min'])}")
    print(f"Max delay                         : {fmt_sec(rr_summary['max'])}")
    print()

    if rr_details:
        print("Per-session request -> response details")
        print("--------------------------------------")
        header = f"{'Session ID':<32} {'Req Station':<12} {'Resp Station':<13} {'Manoeuvre':<10} {'Delay':>10}"
        print(header)
        print("-" * len(header))
        for d in rr_details:
            print(
                f"{d['session_id'][:32]:<32} "
                f"{d['request_station']:<12} "
                f"{d['response_station']:<13} "
                f"{d['manoeuvre_id']:<10} "
                f"{fmt_sec(d['delay_sec']):>10}"
            )
        print()


def print_session_stats_block(session_stats):
    print("=== MCM SESSION ANALYSIS ===")
    print(f"Total sessions      : {session_stats['total_sessions']}")
    print(f"Completed sessions  : {session_stats['completed_sessions']}")
    print(f"Incomplete sessions : {session_stats['incomplete_sessions']}")

    print(f"Average session duration (sim_time) : {fmt_sec(session_stats['session_duration']['avg'])}")
    print(f"Min session duration (sim_time)     : {fmt_sec(session_stats['session_duration']['min'])}")
    print(f"Max session duration (sim_time)     : {fmt_sec(session_stats['session_duration']['max'])}")
    print()

    if session_stats["details"]:
        print("Per-session details")
        print("-------------------")

        header = f"{'Session ID':<32} {'Requester':<10} {'Manoeuvre':<10} {'Req->Resp(wall)':<16} {'Req->Term(wall)':<16} {'Duration(sim)':<14} {'Completed':<10}"
        print(header)
        print("-" * len(header))

        for d in session_stats["details"]:
            print(
                f"{d['session_id']:<32} "
                f"{str(d['requester_station_id']):<10} "
                f"{str(d['manoeuvre_id']):<10} "
                f"{fmt_sec(d['req_to_resp_sec']):<16} "
                f"{fmt_sec(d['req_to_term_sec']):<16} "
                f"{fmt_sec(d['duration_sim_sec']):<14} "
                f"{str(d['completed']):<10}"
            )
        print()
def compute_sim_duration(rows):
    times = [to_float(r.get("sim_time")) for r in rows if r.get("sim_time")]
    times = [t for t in times if t is not None]

    if not times:
        return 0

    return max(times) - min(times)
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages", required=True, help="Path to *_message_events.csv")
    parser.add_argument("--sessions", required=False, help="Path to *_mcm_sessions.csv")
    args = parser.parse_args()

    message_rows = read_csv(args.messages)
    sim_duration = compute_sim_duration(message_rows)
    messages = build_message_map(message_rows)
    session_rows = []
    if args.sessions and Path(args.sessions).exists():
        session_rows = read_csv(args.sessions)

    cam_stats = get_type_stats(messages, "cam", sim_duration)
    req_stats = get_type_stats(messages, "mcm_request", sim_duration)
    resp_stats = get_type_stats(messages, "mcm_response", sim_duration)
    term_stats = get_type_stats(messages, "mcm_termination", sim_duration)

    cam_station_stats = get_station_stats(messages, "cam")
    req_station_stats = get_station_stats(messages, "mcm_request")
    resp_station_stats = get_station_stats(messages, "mcm_response")
    term_station_stats = get_station_stats(messages, "mcm_termination")

    rr_summary, rr_details = get_request_response_wall_stats(messages)
    session_stats = get_session_stats(session_rows)

    print("=== INDIVIDUAL MESSAGE ANALYSIS ===\n")

    print_type_block(cam_stats)
    print_station_block("CAM PER-STATION ANALYSIS", cam_station_stats)

    print_type_block(req_stats)
    print_station_block("MCM REQUEST PER-STATION ANALYSIS", req_station_stats)

    print_type_block(resp_stats)
    print_station_block("MCM RESPONSE PER-STATION ANALYSIS", resp_station_stats)

    print_type_block(term_stats)
    print_station_block("MCM TERMINATION PER-STATION ANALYSIS", term_station_stats)

    print_request_response_block(rr_summary, rr_details)
    print_session_stats_block(session_stats)


if __name__ == "__main__":
    main()
