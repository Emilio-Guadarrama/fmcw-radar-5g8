"""Engine, snapshot and local web server, end to end on simulated frames."""

import http.client
import json
import threading

import pytest
from radar_display.engine import Engine
from radar_display.server import apply_control, make_server
from radar_display.simulated import SCENES, SimulatedSource


def fast_source():
    return SimulatedSource(frame_rate_hz=200.0, seed=5)


@pytest.mark.parametrize("sweep", ["115", "150"])
@pytest.mark.parametrize("scene", SCENES)
@pytest.mark.parametrize("window", ["hann", "rect"])
def test_every_scene_produces_a_valid_snapshot(sweep, scene, window):
    engine = Engine(fast_source())
    apply_control(
        engine, {"window": window, "simulation": {"sweep": sweep, "scene": scene}}
    )
    assert engine.step() and engine.step()
    _, snapshot, error = engine.wait_for_update(0, 1.0)
    assert error is None
    json.dumps(snapshot, allow_nan=False)  # what the browser must be able to read
    assert snapshot["source"]["is_simulated"] is True
    assert snapshot["settings"]["window"] == window
    assert snapshot["settings"]["bandwidth_mhz"] == pytest.approx(float(sweep))
    spectrum = snapshot["spectrum"]
    assert len(spectrum["cell_db"]) == len(spectrum["threshold_db"])
    assert len(spectrum["db"]) * spectrum["range_step_m"] == pytest.approx(45, abs=0.2)


def test_settings_shown_are_the_calculated_ones():
    engine = Engine(fast_source())
    for _ in range(3):
        engine.step()
    settings = engine.wait_for_update(0, 1.0)[1]["settings"]
    assert settings["range_cell_m"] == pytest.approx(1.303, abs=0.001)
    assert settings["samples_per_chirp"] == 100
    assert settings["chirps_per_frame"] == 16
    assert settings["frame_capture_ms"] == pytest.approx(16.0)
    assert settings["integration_gain_db"] == pytest.approx(12.04, abs=0.01)
    assert settings["max_unaliased_range_m"] == pytest.approx(65.17, abs=0.01)


def test_processing_errors_are_published_not_swallowed():
    class Broken(SimulatedSource):
        def read_frame(self, timeout_s):
            raise RuntimeError("link broke")

    engine = Engine(Broken())
    engine.start()
    try:
        _, _, error = engine.wait_for_update(0, 2.0)
    finally:
        engine.stop()
    assert "link broke" in error


def test_non_simulated_source_refuses_simulation_controls():
    source = fast_source()
    source.is_simulated = False
    with pytest.raises(ValueError):
        apply_control(Engine(source), {"drop_frames": 1})


@pytest.fixture
def server():
    engine = Engine(fast_source())
    httpd = make_server(engine, 0)
    thread = threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    engine.start()
    yield engine, httpd.server_address[1]
    engine.stop()
    httpd.shutdown()
    httpd.server_close()


def request(port, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path, body, headers or {})
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


def post(port, command, content_type="application/json", **headers):
    return request(
        port,
        "POST",
        "/api/control",
        json.dumps(command),
        {"Content-Type": content_type, **headers},
    )


def test_server_listens_on_this_pc_only(server):
    engine, _ = server
    httpd = make_server(engine, 0)
    assert httpd.server_address[0] == "127.0.0.1"
    httpd.server_close()


def test_page_files_and_banner_are_served(server):
    _, port = server
    status, page = request(port, "GET", "/")
    assert status == 200
    assert b"SIMULATED DATA" in page
    assert b"Neither sweep is cleared to transmit" in page
    assert request(port, "GET", "/app.js")[0] == 200
    assert request(port, "GET", "/style.css")[0] == 200
    assert request(port, "GET", "/../run_display.py")[0] == 404


def test_state_and_stream_deliver_frames(server):
    _, port = server
    status, data = request(port, "GET", "/api/state")
    assert status == 200 and json.loads(data)["frame"]["source"]["is_simulated"]
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request("GET", "/api/stream")
    response = connection.getresponse()
    line = response.fp.readline()
    while not line.startswith(b"data: "):
        line = response.fp.readline()
    connection.close()
    assert json.loads(line[6:])["frame"]["spectrum"]["db"]


def test_control_changes_settings_and_rejects_bad_requests(server):
    engine, port = server
    assert post(port, {"simulation": {"scene": "three"}})[0] == 200
    assert engine.source.settings.scene == "three"
    for bad in (
        {"transmit": True},
        {"window": "blackman"},
        {"drop_frames": 1000},
        {"simulation": {"distance_m": 500}},
        [1],
    ):
        assert post(port, bad)[0] == 400, bad
    assert post(port, {"window": "rect"}, "text/plain")[0] == 415
    assert post(port, {"window": "rect"}, Host="evil.example")[0] == 403
    assert (
        request(port, "GET", "/api/state", headers={"Host": "evil.example"})[0] == 403
    )
    assert engine.window == "hann"
