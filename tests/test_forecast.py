""" Test for main app """

import uuid
from datetime import datetime, timedelta

from freezegun import freeze_time
from pvsite_datamodel.sqlmodels import SiteSQL

from pv_site_api.pydantic_models import Forecast


def test_get_forecast_fake(client, fake):
    response = client.get("/sites/ffff-ffff/pv_forecast")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0


def test_get_forecast_many_sites_fake(client, fake):
    resp = client.get("/sites/pv_forecast?site_uuids=ffff-ffff")
    assert resp.status_code == 200

    forecasts = [Forecast(**x) for x in resp.json()]
    assert len(forecasts) == 1
    assert len(forecasts[0].forecast_values) > 0


def test_get_forecast(db_session, client, forecast_values):
    site_uuid = forecast_values[0].forecast.site_uuid
    response = client.get(f"/sites/{site_uuid}/pv_forecast")
    assert response.status_code == 200

    forecast = Forecast(**response.json())
    assert len(forecast.forecast_values) > 0


def test_get_forecast_many_sites(db_session, client, forecast_values, sites):
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)

    resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}")
    assert resp.status_code == 200

    forecasts = [Forecast(**x) for x in resp.json()]

    assert len(forecasts) == len(sites)
    # We have 10 forecasts with 11 values each.
    # We should get 11 values for the latest forecast, and 9 values (all but the most recent)
    # for the first prediction for each (other) forecast.
    assert len(forecasts[0].forecast_values) == 11 + 9

    # Also check that the forecasts values are sorted by date.
    assert (
        list(sorted(forecasts[0].forecast_values, key=lambda fv: fv.target_datetime_utc))
        == forecasts[0].forecast_values
    )


def test_get_forecast_many_sites_late_forecast_one_week(db_session, client, forecast_values, sites):
    """Test the case where the forecast stop working 1 week ago"""
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)

    one_week_from_now = datetime.utcnow() + timedelta(days=7)
    with freeze_time(one_week_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}")
        assert resp.status_code == 200

        forecasts = [Forecast(**x) for x in resp.json()]

    assert len(forecasts) == 0


def test_get_forecast_many_sites_late_forecast_one_day(db_session, client, forecast_values, sites):
    """Test the case where the forecast stop working 1 day ago"""
    site_uuids = [str(s.site_uuid) for s in sites]
    site_uuids_str = ",".join(site_uuids)
    one_day_from_now = datetime.utcnow() + timedelta(days=1)

    with freeze_time(one_day_from_now):
        resp = client.get(f"/sites/pv_forecast?site_uuids={site_uuids_str}")
        assert resp.status_code == 200

        forecasts = [Forecast(**x) for x in resp.json()]

    assert len(forecasts) == len(sites)
    # We have 10 forecasts with 11 values each.
    # We should get 11 values for the latest forecast, and 9 values (all but the most recent)
    # for the first prediction for each (other) forecast.
    assert len(forecasts[0].forecast_values) == 20

    # Also check that the forecasts values are sorted by date.
    assert (
        list(sorted(forecasts[0].forecast_values, key=lambda fv: fv.target_datetime_utc))
        == forecasts[0].forecast_values
    )

    # check they are all less than one day from now
    for forecast in forecasts:
        for forecast_value in forecast.forecast_values:
            assert forecast_value.target_datetime_utc < one_day_from_now


def test_get_forecast_no_data(db_session, client, clients):
    # Make a brand new site.
    site = SiteSQL(client_uuid=clients[0].client_uuid, ml_id=123)
    db_session.add(site)
    db_session.commit()

    # Get forecasts from that site with no forecasts.
    resp = client.get(f"/sites/{site.site_uuid}/pv_forecast")
    assert resp.status_code == 204


def test_get_forecast_404(db_session, client):
    """If we get forecasts for an unknown site, we get a 404."""
    resp = client.get(f"/sites/{uuid.uuid4()}/pv_forecast")
    assert resp.status_code == 404
