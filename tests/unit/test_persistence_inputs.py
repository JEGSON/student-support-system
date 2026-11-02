from datetime import datetime,timezone
import pytest
from app.repositories.core import plain_text,identifier,london_time,InvalidInput


def test_typed_input_and_london_dst():
    assert plain_text('  synthetic text  ',100)=='synthetic text'
    for value in ['', '  ', {'$where':'injected'},['text']]:
        with pytest.raises(InvalidInput):plain_text(value,100)
    with pytest.raises(InvalidInput):plain_text('x'*10001,10000)
    with pytest.raises(InvalidInput):identifier({'$ne':None})
    assert london_time(datetime(2026,1,1,12,tzinfo=timezone.utc)).endswith('12:00 GMT')
    assert london_time(datetime(2026,7,1,12,tzinfo=timezone.utc)).endswith('13:00 BST')
    with pytest.raises(InvalidInput):london_time(datetime(2026,1,1))
