

from datetime import datetime, timedelta, timezone
from astral import LocationInfo
from watcher.model import sunlight_from_time_for_location

def test_sunlight():
	austin = LocationInfo('austin', 'texas', 'US/Central', 30.443, -97.817)

	wee_hours = datetime.fromisoformat('2022-03-30 03:00-05:00')
	assert sunlight_from_time_for_location(wee_hours, austin) == 'night'

	pre_dawn = datetime.fromisoformat('2022-03-30 07:10-05:00')
	assert sunlight_from_time_for_location(pre_dawn, austin) == 'twighlight'

	dawn = datetime.fromisoformat('2022-03-30 07:30-05:00')
	assert sunlight_from_time_for_location(dawn, austin) == 'daylight'

	afternoon = datetime.fromisoformat('2022-03-30 15:30-05:00')
	assert sunlight_from_time_for_location(afternoon, austin) == 'daylight'

	dusk = datetime.fromisoformat('2022-03-30 20:00-05:00')
	assert sunlight_from_time_for_location(dusk, austin) == 'twighlight'

	evening = datetime.fromisoformat('2022-03-30 20:30-05:00')
	assert sunlight_from_time_for_location(evening, austin) == 'night'

	midnight = datetime.fromisoformat('2022-03-30 00:00-05:00')
	assert sunlight_from_time_for_location(midnight, austin) == 'night'

def test_timezones():
	austin = LocationInfo('austin', 'texas', 'US/Central', 30.443, -97.817)

	end_of_march = datetime.fromisoformat('2022-03-30 10:00')
	assert end_of_march.astimezone(austin.tzinfo).utcoffset() == timedelta(hours= -5)

	mid_january = datetime.fromisoformat('2022-01-15 13:42')
	assert mid_january.astimezone(austin.tzinfo).utcoffset() == timedelta(hours= -6)

	assert end_of_march.astimezone(austin.tzinfo).astimezone(timezone.utc).isoformat() == '2022-03-30T15:00:00+00:00'