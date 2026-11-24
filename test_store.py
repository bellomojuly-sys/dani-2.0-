"""Settings on disk: defaults, round trip, refusal of a broken file, hiding."""

from datetime import date, datetime

import pytest

from cycle import CycleSettings
from models import AMSTERDAM, Event
from store import UserSettings, hide_event, read_settings, unhide_event, write_settings

NOW = datetime(2026, 11, 10, 14, 0, tzinfo=AMSTERDAM)
GYM = Event(calendar="personale", title="Palestra", uid="gym-1",
            start=datetime(2026, 11, 10, 18, 0, tzinfo=AMSTERDAM), end=datetime(2026, 11, 10, 19, 0, tzinfo=AMSTERDAM))


def test_missing_file_gives_the_defaults(tmp_path):
    settings = read_settings(str(tmp_path / "nothing.json"))
    assert settings.context == "" and settings.cycle is None
    assert settings.tickable_calendars == ["personale", "studio"]


def test_what_is_written_is_read_back(tmp_path):
    path = str(tmp_path / "data" / "settings.json")  # the folder does not exist yet
    saved = UserSettings(context="No study on Sunday", cycle=CycleSettings(start=date(2026, 11, 8)))
    write_settings(hide_event(saved, GYM, NOW), path)
    loaded = read_settings(path)
    assert loaded.context == "No study on Sunday"
    assert loaded.cycle.start == date(2026, 11, 8)
    assert [entry.key for entry in loaded.hidden_events] == [GYM.key]


@pytest.mark.parametrize("content", ["{not json", '{"cycle": {"start": "2026-11-08", "cycle_length": 3}}', '{"context": 5}'])
def test_a_broken_file_is_refused_with_its_name(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content)
    with pytest.raises(ValueError, match="settings.json is not a valid settings file"):
        read_settings(str(path))


def test_hiding_twice_keeps_one_entry_and_unhide_removes_it():
    once = hide_event(UserSettings(), GYM, NOW)
    twice = hide_event(once, GYM, NOW)
    assert len(twice.hidden_events) == 1
    assert twice.hidden_events[0].title == "Palestra"
    assert unhide_event(twice, GYM.key).hidden_events == []
    assert len(unhide_event(twice, "another-key").hidden_events) == 1


def test_two_occurrences_of_one_repeating_event_have_different_keys():
    next_week = GYM.model_copy(update={"start": datetime(2026, 11, 17, 18, 0, tzinfo=AMSTERDAM),
                                       "end": datetime(2026, 11, 17, 19, 0, tzinfo=AMSTERDAM)})
    assert GYM.key != next_week.key and GYM.uid == next_week.uid


def test_rejecting_a_block_is_remembered_once_and_can_be_restored(tmp_path):
    from store import reject_block, restore_block

    path = str(tmp_path / "settings.json")
    settings = reject_block(UserSettings(), "t1")
    settings = reject_block(settings, "t1")  # rejecting twice adds nothing
    assert settings.rejected_blocks == ["t1"]
    write_settings(settings, path)
    assert read_settings(path).rejected_blocks == ["t1"]  # survives a restart
    assert restore_block(settings, "t1").rejected_blocks == []
    assert restore_block(settings, "other").rejected_blocks == ["t1"]  # unknown id changes nothing
