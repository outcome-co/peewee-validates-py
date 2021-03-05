from datetime import date, datetime, time, timedelta
from typing import Dict

from outcome.peewee_validates.peewee_validates import (  # noqa: WPS235
    DEFAULT_MESSAGES,
    BooleanField,
    DateField,
    DateTimeField,
    DecimalField,
    Field,
    FloatField,
    IntegerField,
    StringField,
    TimeField,
    ValidationError,
    Validator,
    validate_email,
    validate_equal,
    validate_function,
    validate_length,
    validate_none_of,
    validate_not_empty,
    validate_one_of,
    validate_regexp,
)

required_msg = DEFAULT_MESSAGES['required']


def test_raw_field():
    class TestValidator(Validator):
        field1 = Field[None]()

    validator = TestValidator()
    assert validator.validate({'field1': 'thing'})
    assert validator.data['field1'] == 'thing'


def test_required():  # noqa: WPS218
    class TestValidator(Validator):
        bool_field = BooleanField[None](required=True)
        decimal_field = DecimalField[None](required=True)
        float_field = FloatField[None](required=True, low=10.0, high=50.0)
        int_field = IntegerField[None](required=True)
        str_field = StringField[None](required=True)
        date_field = DateField[None](required=True, low=date.today() - timedelta(1), high=date.today() + timedelta(1))
        time_field = TimeField[None](required=True, low=time(), high=time())
        datetime_field = DateTimeField[None](required=True, low=datetime.now() - timedelta(1), high=datetime.now() + timedelta(1))

    validator = TestValidator()
    assert not validator.validate()
    assert validator.errors['bool_field'] == required_msg
    assert validator.errors['decimal_field'] == required_msg
    assert validator.errors['float_field'] == required_msg
    assert validator.errors['int_field'] == required_msg
    assert validator.errors['str_field'] == required_msg
    assert validator.errors['date_field'] == required_msg
    assert validator.errors['time_field'] == required_msg
    assert validator.errors['datetime_field'] == required_msg


def test_integerfield():
    class TestValidator(Validator):
        int_field = IntegerField[None](required=True)

    data = {'int_field': 0}
    validator = TestValidator()
    assert validator.validate(data)


def test_coerce_fails():
    class TestValidator(Validator):
        float_field = FloatField[None]()
        int_field = IntegerField[None](required=True)
        decimal_field = DecimalField[None](required=True)
        boolean_field = BooleanField[None]()

    validator = TestValidator()
    data = {'int_field': 'a', 'float_field': 'a', 'decimal_field': 'a', 'boolean_field': 'false'}
    assert not validator.validate(data)
    assert validator.errors['decimal_field'] == DEFAULT_MESSAGES['coerce_decimal']
    assert validator.errors['float_field'] == DEFAULT_MESSAGES['coerce_float']
    assert validator.errors['int_field'] == DEFAULT_MESSAGES['coerce_int']


def test_decimal():
    class TestValidator(Validator):
        low_field = DecimalField[None](low=-42.0)
        high_field = DecimalField[None](high=42.0)
        low_high_field = DecimalField[None](low=-42.0, high=42.0)

    validator = TestValidator()
    data = {'low_field': '-99.99', 'high_field': '99.99', 'low_high_field': '99.99'}
    assert not validator.validate(data)
    assert validator.errors['low_field'] == 'Must be at least -42.0.'
    assert validator.errors['high_field'] == 'Must be between None and 42.0.'
    assert validator.errors['low_high_field'] == 'Must be between -42.0 and 42.0.'


def test_required_empty():
    class TestValidator(Validator):
        field1 = StringField[None](required=False, validators=[validate_not_empty()])

    validator = TestValidator()

    assert validator.validate()

    assert not validator.validate({'field1': ''})
    assert validator.errors['field1'] == DEFAULT_MESSAGES['empty']


def test_dates_empty():
    class TestValidator(Validator):
        date_field = DateField[None]()
        time_field = TimeField[None]()
        datetime_field = DateTimeField[None]()

    data = {
        'date_field': '',
        'time_field': '',
        'datetime_field': '',
    }

    validator = TestValidator()
    assert validator.validate(data)

    assert not validator.data['datetime_field']
    assert not validator.data['date_field']
    assert not validator.data['time_field']


def test_dates_coersions():
    class TestValidator(Validator):
        date_field = DateField[None](required=True)
        time_field = TimeField[None](required=True)
        datetime_field = DateTimeField[None](required=True)

    data = {
        'date_field': 'jan 1, 2015',
        'time_field': 'jan 1, 2015 3:20 pm',
        'datetime_field': 'jan 1, 2015 3:20 pm',
    }

    validator = TestValidator()
    assert validator.validate(data)

    assert validator.data['datetime_field'] == datetime(2015, 1, 1, 15, 20)
    assert validator.data['date_field'] == date(2015, 1, 1)
    assert validator.data['time_field'] == time(15, 20)


def test_dates_native():
    class TestValidator(Validator):
        date_field = DateField[None](required=True)
        time_field = TimeField[None](required=True)
        datetime_field = DateTimeField[None](required=True)

    data = {
        'date_field': date(2015, 1, 1),
        'time_field': time(15, 20),
        'datetime_field': datetime(2015, 1, 1, 15, 20),
    }

    validator = TestValidator()
    assert validator.validate(data)

    assert validator.data['datetime_field'] == datetime(2015, 1, 1, 15, 20)
    assert validator.data['date_field'] == date(2015, 1, 1)
    assert validator.data['time_field'] == time(15, 20)


def test_date_coerce_fail():
    class TestValidator(Validator):
        date_field = DateField[None](required=True)
        time_field = TimeField[None](required=True)
        datetime_field = DateTimeField[None](required=True)

    data = {
        'date_field': 'failure',
        'time_field': 'failure',
        'datetime_field': 'failure',
    }

    validator = TestValidator()
    assert not validator.validate(data)

    assert validator.errors['datetime_field'] == DEFAULT_MESSAGES['coerce_datetime']
    assert validator.errors['date_field'] == DEFAULT_MESSAGES['coerce_date']
    assert validator.errors['time_field'] == DEFAULT_MESSAGES['coerce_time']


def test_default():
    class TestValidator(Validator):
        str_field = StringField[None](required=True, default='timster')

    validator = TestValidator()
    assert validator.validate()
    assert validator.data['str_field'] == 'timster'


def test_callable_default():
    def getname():
        return 'timster'

    class TestValidator(Validator):
        str_field = StringField[None](required=True, default=getname)

    validator = TestValidator()
    assert validator.validate()
    assert validator.data['str_field'] == 'timster'


def test_lengths():
    class TestValidator(Validator):
        max_field = StringField[None](max_length=5)
        min_field = StringField[None](min_length=5)
        len_field = StringField[None](validators=[validate_length(equal=10)])

    validator = TestValidator()
    assert not validator.validate({'min_field': 'shrt', 'max_field': 'toolong', 'len_field': '3'})
    assert validator.errors['min_field'] == DEFAULT_MESSAGES['length_low'].format(low=5)
    assert validator.errors['max_field'] == DEFAULT_MESSAGES['length_high'].format(high=5)
    assert validator.errors['len_field'] == DEFAULT_MESSAGES['length_equal'].format(equal=10)


def test_range():
    class TestValidator(Validator):
        range1 = IntegerField[None](low=1, high=5)
        range2 = IntegerField[None](low=1, high=5)

    validator = TestValidator()
    assert not validator.validate({'range1': '44', 'range2': '3'})
    assert validator.errors['range1'] == DEFAULT_MESSAGES['range_between'].format(low=1, high=5)
    assert 'range2' not in validator.errors


def test_coerce_error():
    class TestValidator(Validator):
        date_field = DateField[None]()

    validator = TestValidator()
    assert not validator.validate({'date_field': 'not a real date'})
    assert validator.errors['date_field'] == DEFAULT_MESSAGES['coerce_date']


def test_choices():
    class TestValidator(Validator):
        first_name = StringField[None](validators=[validate_one_of(('tim', 'bob'))])

    validator = TestValidator()
    assert validator.validate()

    validator = TestValidator()
    assert validator.validate({'first_name': 'tim'})

    validator = TestValidator()
    assert not validator.validate({'first_name': 'asdf'})
    assert validator.errors['first_name'] == DEFAULT_MESSAGES['one_of'].format(choices='tim, bob')


def test_choices_integers():
    class TestValidator(Validator):
        int_field = IntegerField[None](validators=[validate_one_of((1, 2, 3))])

    validator = TestValidator()
    assert not validator.validate({'int_field': 4})


def test_exclude():
    class TestValidator(Validator):
        first_name = StringField[None](validators=[validate_none_of(('tim', 'bob'))])

    validator = TestValidator()
    assert not validator.validate({'first_name': 'tim'})
    assert validator.errors['first_name'] == DEFAULT_MESSAGES['none_of'].format(choices='tim, bob')

    validator = TestValidator()
    assert validator.validate({'first_name': 'asdf'})


def test_callable_choices():
    def getchoices():
        return ('tim', 'bob')

    class TestValidator(Validator):
        first_name = StringField[None](validators=[validate_one_of(getchoices)])

    validator = TestValidator()
    assert not validator.validate({'first_name': 'asdf'})
    assert validator.errors['first_name'] == DEFAULT_MESSAGES['one_of'].format(choices='tim, bob')

    validator = TestValidator()
    assert validator.validate({'first_name': 'tim'})


def test_callable_exclude():
    def getchoices():
        return ('tim', 'bob')

    class TestValidator(Validator):
        first_name = StringField[None](validators=[validate_none_of(getchoices)])

    validator = TestValidator()
    assert not validator.validate({'first_name': 'tim'})
    assert validator.errors['first_name'] == DEFAULT_MESSAGES['none_of'].format(choices='tim, bob')

    validator = TestValidator()
    assert validator.validate({'first_name': 'asdf'})


def test_equal():
    class TestValidator(Validator):
        first_name = StringField[None](validators=[validate_equal('tim')])

    validator = TestValidator()
    assert validator.validate({'first_name': 'tim'})

    validator = TestValidator()
    assert not validator.validate({'first_name': 'asdf'})
    assert validator.errors['first_name'] == DEFAULT_MESSAGES['equal'].format(other='tim')


def test_regexp():
    class TestValidator(Validator):
        first_name = StringField[None](validators=[validate_regexp('^[i-t]+$')])

    validator = TestValidator()
    assert validator.validate({'first_name': 'tim'})

    validator = TestValidator()
    assert not validator.validate({'first_name': 'asdf'})
    assert validator.errors['first_name'] == DEFAULT_MESSAGES['regexp'].format(pattern='^[i-t]+$')


def test_email():
    class TestValidator(Validator):
        email = StringField[None](validators=[validate_email()])

    validator = TestValidator()
    assert not validator.validate({'email': 'bad-domain@asdfasdf'})
    assert validator.errors['email'] == DEFAULT_MESSAGES['email']


def test_function():
    def alwaystim(value: object):
        return value == 'tim'

    class TestValidator(Validator):
        first_name = StringField[None](validators=[validate_function(alwaystim)])

        class Meta(Validator.Meta):
            messages = {'function': 'your name must be tim'}

    validator = TestValidator()
    assert validator.validate({'first_name': 'tim'})

    validator = TestValidator()
    assert not validator.validate({'first_name': 'asdf'})
    assert validator.errors['first_name'] == validator._meta.messages['function']  # type: ignore


def test_only_exclude():
    class TestValidator(Validator):
        field1 = StringField[None](required=True)
        field2 = StringField[None](required=True)

    validator = TestValidator()
    assert validator.validate({'field1': 'shrt'}, only=['field1'])

    assert validator.validate({'field1': 'shrt'}, exclude=['field2'])


def test_clean_field():
    class TestValidator(Validator):
        field1 = StringField[None](required=True)

        def clean_field1(self, value: object):
            return f'{value}-awesome'

    validator = TestValidator()
    assert validator.validate({'field1': 'tim'})
    assert validator.data['field1'] == 'tim-awesome'


def test_clean_field_error():
    class TestValidator(Validator):
        field1 = StringField[None](required=True)

        def clean_field1(self, value: object):
            raise ValidationError('required')

    validator = TestValidator()
    assert not validator.validate({'field1': 'tim'})
    assert validator.data['field1'] == 'tim'
    assert validator.errors['field1'] == DEFAULT_MESSAGES['required']


def test_clean():
    class TestValidator(Validator):
        field1 = StringField[None](required=True)

        def clean(self, data: Dict[str, object]):
            v = data['field1']
            assert isinstance(v, str)
            data['field1'] = v + 'awesome'  # noqa: WPS336
            return data

    validator = TestValidator()
    assert validator.validate({'field1': 'tim'})
    assert validator.data['field1'] == 'timawesome'


def test_clean_error():
    class TestValidator(Validator):
        field1 = StringField[None](required=True)

        def clean(self, data: Dict[str, object]) -> Dict[str, object]:
            raise ValidationError('required')

    validator = TestValidator()
    assert not validator.validate({'field1': 'tim'})
    assert validator.data['field1'] == 'tim'
    assert validator.errors['__base__'] == DEFAULT_MESSAGES['required']


def test_custom_messages():
    class TestValidator(Validator):
        field1 = StringField[None](required=True)
        field2 = StringField[None](required=True)
        field3 = IntegerField[None](required=True)

        class Meta(Validator.Meta):
            messages = {
                'required': 'enter value',
                'field2.required': 'field2 required',
                'field3.coerce_int': 'pick a number',
            }

    validator = TestValidator()
    assert not validator.validate({'field3': 'asdfasdf'})
    assert validator.errors['field1'] == 'enter value'
    assert validator.errors['field2'] == 'field2 required'
    assert validator.errors['field3'] == 'pick a number'


def test_subclass():
    class ParentValidator(Validator):
        field1 = StringField[None](required=True)
        field2 = StringField[None](required=False)

    class TestValidator(ParentValidator):
        field2 = StringField[None](required=True)
        field3 = StringField[None](required=True)

    validator = TestValidator()
    assert not validator.validate({})
    assert validator.errors['field1'] == DEFAULT_MESSAGES['required']
    assert validator.errors['field2'] == DEFAULT_MESSAGES['required']
    assert validator.errors['field3'] == DEFAULT_MESSAGES['required']
