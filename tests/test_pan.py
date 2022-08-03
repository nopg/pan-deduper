import os

import pytest

import pan_deduper.panorama_api as pa_api


@pytest.fixture(scope="module")
def vcr_config():
    return {"filter_query_parameters": ["user", "password"]}


@pytest.mark.asyncio
# @pytest.mark.vcr()
async def test_correct_pan_login():
    login_info = {
        "panorama": os.environ.get("PANORAMA_IP"),
        "username": os.environ.get("PAN_USERNAME"),
        "password": os.environ.get("PAN_PASSWORD"),
    }
    pa = pa_api.Panorama_api(**login_info)
    await pa.login()
    assert pa.apikey is not None


@pytest.mark.asyncio
# @pytest.mark.vcr()
async def test_incorrect_pan_login(capsys):
    login_info = {
        "panorama": "10.254.254.5",
        "username": "admin",
        "password": "admin",
    }
    with pytest.raises(SystemExit) as error:
        pa = pa_api.Panorama_api(**login_info)
        await pa.login()
    assert error.value.code == 1
    msg = capsys.readouterr()
    assert msg.out.endswith("Unable to retrieve API key...bad credentials?\n")
