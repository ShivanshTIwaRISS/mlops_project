"""Tests for S7 MCP tools: predict_duration and query_zone_stats."""

import json
from unittest.mock import MagicMock

import pytest

import labmcp.server as s


@pytest.mark.asyncio
async def test_predict_duration_success(monkeypatch):
    seen = []

    async def fake_champion(method, path, body=None):
        seen.append((method, path, body))
        return {
            "duration_minutes": 24.5,
            "model": {"name": "trip-duration", "version": "2", "alias": "champion"},
        }

    monkeypatch.setattr(s, "champion", fake_champion)
    out_list = await s.mcp.call_tool(
        "predict_duration",
        {
            "pickup_zone": "JFK Airport",
            "dropoff_zone": "Times Sq/Theatre District",
            "hour": 17,
            "day_of_week": "friday",
        },
    )
    res = json.loads(out_list[0].text)
    assert res["duration_minutes"] == 24.5
    assert res["model"]["alias"] == "champion"
    assert seen == [
        (
            "POST",
            "/predict",
            {
                "pickup_zone_id": 132,
                "dropoff_zone_id": 230,
                "pickup_hour": 17,
                "pickup_dow": 5,
            },
        )
    ]


@pytest.mark.asyncio
async def test_predict_duration_invalid_zone():
    with pytest.raises(Exception, match="unknown TLC zone"):
        await s.mcp.call_tool(
            "predict_duration",
            {
                "pickup_zone": "NonExistentZoneXYZ",
                "dropoff_zone": "JFK Airport",
                "hour": 10,
                "day_of_week": "monday",
            },
        )


@pytest.mark.asyncio
async def test_query_zone_stats_with_hour(monkeypatch):
    mock_wh = MagicMock()
    mock_wh.query.return_value = [
        {"pickup_zone_id": 132, "zone": "JFK Airport", "pickup_hour": 14, "trip_count": 1500}
    ]
    monkeypatch.setattr(s, "Warehouse", lambda: mock_wh)

    out_list = await s.mcp.call_tool(
        "query_zone_stats",
        {"zone": "JFK Airport", "metric": "trip_count", "hour": 14},
    )
    res = json.loads(out_list[0].text)
    assert res["zone"] == "JFK Airport"
    assert res["pickup_hour"] == 14
    assert res["value"] == 1500
    mock_wh.query.assert_called_once()
    sql, params = mock_wh.query.call_args[0]
    assert "trip_count" in sql
    assert params == {"pzid": 132, "hour": 14}


@pytest.mark.asyncio
async def test_query_zone_stats_without_hour(monkeypatch):
    mock_wh = MagicMock()
    mock_wh.query.return_value = [
        {"pickup_zone_id": 132, "zone": "JFK Airport", "pickup_hour": 8, "median_duration_min": 35.0},
        {"pickup_zone_id": 132, "zone": "JFK Airport", "pickup_hour": 9, "median_duration_min": 42.0},
    ]
    monkeypatch.setattr(s, "Warehouse", lambda: mock_wh)

    out_list = await s.mcp.call_tool(
        "query_zone_stats",
        {"zone": "JFK Airport", "metric": "median_duration_min"},
    )
    res = json.loads(out_list[0].text)
    assert res["zone"] == "JFK Airport"
    assert res["stats"] == {"8": 35.0, "9": 42.0} or res["stats"] == {8: 35.0, 9: 42.0}
    mock_wh.query.assert_called_once()
    sql, params = mock_wh.query.call_args[0]
    assert "median_duration_min" in sql
    assert params == {"pzid": 132}
