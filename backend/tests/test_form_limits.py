"""Large scene_json fields (base64 worksheet images) must reach /api/chat."""
from fastapi import FastAPI, Form
from fastapi.testclient import TestClient

from app.core.form_limits import MAX_FORM_PART_BYTES, raise_form_part_limit


def post(client, scene_json):
    # multipart/form-data, exactly like the widget (it also attaches the whiteboard PNG)
    return client.post("/echo", data={"scene_json": scene_json},
                       files={"whiteboard": ("board.png", b"png", "image/png")})


def make_client():
    app = FastAPI()

    @app.post("/echo")
    async def echo(scene_json: str = Form(...)):
        return {"size": len(scene_json)}

    return TestClient(app)


def test_scene_larger_than_one_megabyte_is_accepted():
    raise_form_part_limit()
    big = "x" * (3 * 1024 * 1024)                     # 3 MB, like a scene with a worksheet image
    response = post(make_client(), big)
    assert response.status_code == 200 and response.json() == {"size": len(big)}


def test_limit_still_exists():
    raise_form_part_limit()
    too_big = "x" * (MAX_FORM_PART_BYTES + 1)
    response = post(make_client(), too_big)
    assert response.status_code == 400


def test_calling_twice_is_harmless():
    raise_form_part_limit()
    raise_form_part_limit()
    assert post(make_client(), "ok").json() == {"size": 2}
