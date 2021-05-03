import datetime

import pytest

from outcome.peewee_validates.peewee_validates import (  # noqa: WPS235
    StringField,
    ValidationError,
    validate_email,
    validate_equal,
    validate_function,
    validate_length,
    validate_matches,
    validate_none_of,
    validate_not_empty,
    validate_numeric_range,
    validate_one_of,
    validate_regexp,
    validate_required,
    validate_temporal_range,
)

field = StringField[None]()


def test_validate_required():
    validator = validate_required()

    for value in (None,):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in ('okay', '', '  '):
        field.value = value
        validator(field, {})


def test_validate_not_empty():
    validator = validate_not_empty()

    for value in ('', '  '):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, 'alright', '123'):
        field.value = value
        validator(field, {})


def test_validate_length():
    validator = validate_length(low=2, high=None, equal=None)

    for value in ('1', [1]):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, '22', 'longer', [1, 2]):
        field.value = value
        validator(field, {})

    validator = validate_length(low=None, high=2, equal=None)

    for value in ('123', [1, 2, 3]):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, '22', '', [1, 2]):
        field.value = value
        validator(field, {})

    validator = validate_length(low=None, high=None, equal=2)

    for value in ('242', '', [1, 2, 3]):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, '22', [1, 2]):
        field.value = value
        validator(field, {})

    validator = validate_length(low=2, high=4, equal=None)

    for value in ('1', '', [1, 2, 3, 4, 5]):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, '22', '2222', [1, 2]):
        field.value = value
        validator(field, {})


def test_validate_one_of():
    validator = validate_one_of(('a', 'b', 'c'))

    for value in ('1', '', [1, 2, 3, 4, 5]):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, 'a', 'b', 'c'):
        field.value = value
        validator(field, {})


def test_validate_none_of():
    validator = validate_none_of(('a', 'b', 'c'))

    for value in ('a', 'b', 'c'):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, '1', '', [1, 2, 3, 4, 5]):
        field.value = value
        validator(field, {})


def test_validate_numeric_range():
    validator = validate_numeric_range(low=10, high=100)

    for value in (8, 800):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, 10, 100):
        field.value = value
        validator(field, {})


def test_validate_temporal_range():
    validator = validate_temporal_range(
        low=datetime.datetime.today() - datetime.timedelta(1),
        high=datetime.datetime.today() + datetime.timedelta(2),
    )

    for value in (datetime.datetime.today() - datetime.timedelta(10), datetime.datetime.today() + datetime.timedelta(10)):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, datetime.datetime.today()):
        field.value = value
        validator(field, {})


def test_validate_equal():
    validator = validate_equal('yes')

    for value in ('no', 100):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {})

    for value in (None, 'yes'):
        field.value = value
        validator(field, {})


def test_validate_matches():
    validator = validate_matches('other')

    for value in ('no', 100):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {'other': 'yes'})

    for value in (None, 'yes'):
        field.value = value
        validator(field, {'other': 'yes'})


def test_validate_regexp():
    validator = validate_regexp('^[a-z]{3}$', flags=0)

    for value in ('123', 'abcd', [123, 123]):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {'other': 'yes'})

    for value in (None, 'yes', 'abc'):
        field.value = value
        validator(field, {'other': 'yes'})


def test_validate_function():
    def verify(value: object, check: object):
        return value == check

    validator = validate_function(verify, check='tim')

    for value in ('123', 'abcd', [123, 123]):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {'other': 'yes'})

    for value in (None, 'tim'):
        field.value = value
        validator(field, {'other': 'yes'})


def test_validate_email():
    validator = validate_email()

    for value in ('bad', '())@asdfsd.com', 'tim@().com', [123, 123]):
        field.value = value
        with pytest.raises(ValidationError):
            validator(field, {'other': 'yes'})

    for value in (None, 'tim@example.com', 'tim@localhost'):
        field.value = value
        validator(field, {'other': 'yes'})
