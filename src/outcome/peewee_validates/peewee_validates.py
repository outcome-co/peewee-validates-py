"""peewee-validates is a validator module designed to work with the Peewee ORM."""

import datetime
import re
import types
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from inspect import isgenerator, isgeneratorfunction

import peewee
from dateutil.parser import parse as dateutil_parse

try:
    from playhouse.fields import ManyToManyField  # noqa: WPS433
except ImportError:
    from peewee import ManyToManyField  # noqa: WPS433, WPS440

__version__ = '1.0.10'

__all__ = [
    'Field',
    'Validator',
    'ModelValidator',
    'ValidationError',
    'StringField',
    'FloatField',
    'IntegerField',
    'DecimalField',
    'DateField',
    'TimeField',
    'DateTimeField',
    'BooleanField',
    'ModelChoiceField',
    'ManyModelChoiceField',
]

if peewee.__version__ < '3.0.0':  # noqa: WPS609
    assert AssertionError('Requires Peewee3')  # pragma: no cover # noqa: S101

required_const = 'required'
email_const = 'email'
value_const = 'value'
default_const = 'default'
validators_const = 'validators'

DEFAULT_MESSAGES = types.MappingProxyType(
    {
        required_const: 'This field is required.',
        'empty': 'This field must not be blank.',
        'one_of': 'Must be one of the choices: {choices}.',
        'none_of': 'Must not be one of the choices: {choices}.',
        'equal': 'Must be equal to {other}.',
        'regexp': 'Must match the pattern {pattern}.',
        'matches': 'Must match the field {other}.',
        email_const: 'Must be a valid email address.',
        'function': 'Failed validation for {function}.',
        'length_high': 'Must be at most {high} characters.',
        'length_low': 'Must be at least {low} characters.',
        'length_between': 'Must be between {low} and {high} characters.',
        'length_equal': 'Must be exactly {equal} characters.',
        'range_high': 'Must be at most {high}.',
        'range_low': 'Must be at least {low}.',
        'range_between': 'Must be between {low} and {high}.',
        'coerce_decimal': 'Must be a valid decimal.',
        'coerce_date': 'Must be a valid date.',
        'coerce_time': 'Must be a valid time.',
        'coerce_datetime': 'Must be a valid datetime.',
        'coerce_float': 'Must be a valid float.',
        'coerce_int': 'Must be a valid integer.',
        'related': 'Unable to find object with {field} = {values}.',
        'list': 'Must be a list of values',
        'unique': 'Must be a unique value.',
        'index': 'Fields must be unique together.',
    },
)


class ValidationError(Exception):
    """An exception class that should be raised when a validation error occurs on data."""

    def __init__(self, key, *args, **kwargs):
        self.key = key
        self.kwargs = kwargs
        super().__init__(*args)


def validate_required():
    def required_validator(field, data, ctx=None):
        if field.value is None:  # noqa: WPS204
            raise ValidationError(required_const)

    return required_validator


def validate_not_empty():
    def empty_validator(field, data, ctx=None):
        if isinstance(field.value, str) and not field.value.strip():
            raise ValidationError('empty')

    return empty_validator


def validate_length(low=None, high=None, equal=None):  # noqa: WPS231
    def length_validator(field, data, ctx=None):  # noqa: WPS231
        if field.value is None:
            return
        if equal is not None and len(field.value) != equal:
            raise ValidationError('length_equal', equal=equal)
        if low is not None and len(field.value) < low:
            key = 'length_low' if high is None else 'length_between'
            raise ValidationError(key, low=low, high=high)
        if high is not None and len(field.value) > high:
            key = 'length_high' if low is None else 'length_between'
            raise ValidationError(key, low=low, high=high)

    return length_validator


def validate_one_of(values):
    def one_of_validator(field, data, ctx=None):
        if field.value is None:
            return
        options = values
        if callable(options):
            options = options()
        if field.value not in options:
            raise ValidationError('one_of', choices=', '.join(map(str, options)))

    return one_of_validator


def validate_none_of(values):
    def none_of_validator(field, data, ctx=None):
        options = values
        if callable(options):
            options = options()
        if field.value in options:
            raise ValidationError('none_of', choices=str.join(', ', options))

    return none_of_validator


def validate_range(low=None, high=None):  # noqa: WPS231
    def range_validator(field, data, ctx=None):
        if field.value is None:
            return
        if low is not None and field.value < low:
            key = 'range_low' if high is None else 'range_between'
            raise ValidationError(key, low=low, high=high)
        if high is not None and field.value > high:
            key = 'range_high' if high is None else 'range_between'
            raise ValidationError(key, low=low, high=high)

    return range_validator


def validate_equal(value):
    def equal_validator(field, data, ctx=None):
        if field.value is None:
            return
        if field.value != value:
            raise ValidationError('equal', other=value)

    return equal_validator


def validate_matches(other):
    def matches_validator(field, data, ctx=None):
        if field.value is None:
            return
        if field.value != data.get(other):
            raise ValidationError('matches', other=other)

    return matches_validator


def validate_regexp(pattern, flags=0):
    regex = re.compile(pattern, flags) if isinstance(pattern, str) else pattern

    def regexp_validator(field, data, ctx=None):
        if field.value is None:
            return
        if regex.match(str(field.value)) is None:
            raise ValidationError('regexp', pattern=pattern)

    return regexp_validator


def validate_function(method, **kwargs):
    def function_validator(field, data, ctx=None):
        if field.value is None:
            return
        if not method(field.value, **kwargs):
            raise ValidationError('function', function=method.__name__)

    return function_validator


def validate_email():  # noqa: WPS231
    user_regex = re.compile(
        r"(^[-!#$%&'*+/=?^`{}|~\w]+(\.[-!#$%&'*+/=?^`{}|~\w]+)*$"  # noqa: P103
        r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]'
        r'|\\[\001-\011\013\014\016-\177])*"$)',  # noqa: WPS326
        re.IGNORECASE | re.UNICODE,
    )

    domain_regex = re.compile(
        r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'
        r'(?:[A-Z]{2,6}|[A-Z0-9-]{2,})$'  # noqa: WPS326
        r'|^\[(25[0-5]|2[0-4]\d|[0-1]?\d?\d)'  # noqa: WPS326
        r'(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\]$',  # noqa: WPS326
        re.IGNORECASE | re.UNICODE,
    )

    domain_whitelist = ('localhost',)

    def email_validator(field, data, ctx=None):
        if field.value is None:
            return

        value = str(field.value)

        if '@' not in value:
            raise ValidationError(email_const)

        user_part, domain_part = value.rsplit('@', 1)

        if not user_regex.match(user_part):
            raise ValidationError(email_const)

        if domain_part in domain_whitelist:
            return

        if not domain_regex.match(domain_part):
            raise ValidationError(email_const)

    return email_validator


def validate_model_unique(lookup_field, queryset, pk_field=None, pk_value=None):
    def unique_validator(field, data, ctx=None):
        # If we have a PK, ignore it because it represents the current record.
        query = queryset.where(lookup_field == field.value)
        if pk_field and pk_value:
            query = query.where(~(pk_field == pk_value))
        if query.count():
            raise ValidationError('unique')

    return unique_validator


def coerce_single_instance(lookup_field, value):
    if isinstance(value, dict):
        return value.get(lookup_field.name)
    if isinstance(value, peewee.Model):
        return getattr(value, lookup_field.name)
    return value


def isiterable_notstring(value):
    if isinstance(value, str):
        return False
    return isinstance(value, Iterable) or isgeneratorfunction(value) or isgenerator(value)


class Field:
    __slots__ = (value_const, 'name', required_const, default_const, validators_const)

    def __init__(self, required=False, default=None, validators=None):
        self.default = default
        self.value = None
        self.name = None
        self.validators = validators or []  # noqa: WPS204
        if required:
            self.validators.append(validate_required())

    def coerce(self, value):
        return value

    def get_value(self, name, data):
        if name in data:
            return data.get(name)
        if self.default:
            if callable(self.default):
                return self.default()
            return self.default
        return None

    def validate(self, name, data, ctx):
        self.value = self.get_value(name, data)
        self.name = name
        if self.value is not None:
            self.value = self.coerce(self.value)
        for method in self.validators:
            method(self, data, ctx)


class StringField(Field):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(self, required=False, max_length=None, min_length=None, default=None, validators=None):
        validators = validators or []
        if max_length or min_length:
            validators.append(validate_length(high=max_length, low=min_length))
        super().__init__(required=required, default=default, validators=validators)

    def coerce(self, value):
        return str(value)


class FloatField(Field):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(self, required=False, low=None, high=None, default=None, validators=None):
        validators = validators or []
        if low or high:
            validators.append(validate_range(low=low, high=high))
        super().__init__(required=required, default=default, validators=validators)

    def coerce(self, value):
        try:
            return float(value) if value else None
        except (TypeError, ValueError):
            raise ValidationError('coerce_float')


class IntegerField(Field):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(self, required=False, low=None, high=None, default=None, validators=None):
        validators = validators or []
        if low or high:
            validators.append(validate_range(low=low, high=high))
        super().__init__(required=required, default=default, validators=validators)

    def coerce(self, value):
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            raise ValidationError('coerce_int')


class DecimalField(Field):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(self, required=False, low=None, high=None, default=None, validators=None):
        validators = validators or []
        if low or high:
            validators.append(validate_range(low=low, high=high))
        super().__init__(required=required, default=default, validators=validators)

    def coerce(self, value):
        try:
            return Decimal(value) if value else None
        except (TypeError, ValueError, InvalidOperation):
            raise ValidationError('coerce_decimal')


class DateField(Field):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(self, required=False, low=None, high=None, default=None, validators=None):
        validators = validators or []
        if low or high:
            validators.append(validate_range(low=low, high=high))
        super().__init__(required=required, default=default, validators=validators)

    def coerce(self, value):
        if not value or isinstance(value, datetime.date):
            return value
        try:
            return dateutil_parse(value).date()
        except (TypeError, ValueError):
            raise ValidationError('coerce_date')


class TimeField(Field):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(self, required=False, low=None, high=None, default=None, validators=None):
        validators = validators or []
        if low or high:
            validators.append(validate_range(low=low, high=high))
        super().__init__(required=required, default=default, validators=validators)

    def coerce(self, value):
        if not value or isinstance(value, datetime.time):
            return value
        try:
            return dateutil_parse(value).time()
        except (TypeError, ValueError):
            raise ValidationError('coerce_time')


class DateTimeField(Field):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(self, required=False, low=None, high=None, default=None, validators=None):
        validators = validators or []
        if low or high:
            validators.append(validate_range(low=low, high=high))
        super().__init__(required=required, default=default, validators=validators)

    def coerce(self, value):
        if not value or isinstance(value, datetime.datetime):
            return value
        try:
            return dateutil_parse(value)
        except (TypeError, ValueError):
            raise ValidationError('coerce_datetime')


class BooleanField(Field):
    __slots__ = (value_const, required_const, default_const, validators_const)

    false_values = ('0', '{}', '[]', 'none', 'false')  # noqa: P103

    def coerce(self, value):
        return str(value).lower() not in self.false_values


class ModelChoiceField(Field):
    __slots__ = ('query', 'lookup_field', value_const, required_const, default_const, validators_const)

    def __init__(self, query, lookup_field, required=False, **kwargs):
        self.query = query
        self.lookup_field = lookup_field
        super().__init__(required=required, **kwargs)

    def coerce(self, value):
        return coerce_single_instance(self.lookup_field, value)

    def validate(self, name, data, ctx):
        super().validate(name, data, ctx)
        if self.value is not None:
            try:
                self.value = self.query.get(self.lookup_field == self.value)
            except (AttributeError, ValueError, peewee.DoesNotExist):
                raise ValidationError('related', field=self.lookup_field.name, values=self.value)


class ManyModelChoiceField(Field):
    __slots__ = ('query', 'lookup_field', value_const, required_const, default_const, validators_const)

    def __init__(self, query, lookup_field, required=False, **kwargs):
        self.query = query
        self.lookup_field = lookup_field
        super().__init__(required=required, **kwargs)

    def coerce(self, value):
        if isinstance(value, dict):
            value = [value]
        if not isiterable_notstring(value):
            value = [value]
        return [coerce_single_instance(self.lookup_field, v) for v in value]

    def validate(self, name, data, ctx):
        super().validate(name, data, ctx)
        if self.value is not None:
            try:
                # self.query could be a query like "User.select()" or a model like "User"
                # so ".select().where()" handles both cases.
                self.value = [self.query.select().where(self.lookup_field == v).get() for v in self.value if v]
            except (AttributeError, ValueError, peewee.DoesNotExist):
                raise ValidationError('related', field=self.lookup_field.name, values=self.value)


class ValidatorOptions:
    def __init__(self, obj):
        self.fields = {}
        self.messages = {}
        self.only = []
        self.exclude = []


class Validator:
    """A validator class. Can have many fields attached to it to perform validation on data."""

    class Meta:
        pass

    __slots__ = ('data', 'errors', '_meta')

    def __init__(self):
        self.errors = {}
        self.data = {}

        self._meta = ValidatorOptions(self)
        self._meta.__dict__.update(self.Meta.__dict__)  # noqa: WPS609

        self.initialize_fields()

    def add_error(self, name, error):
        message = self._meta.messages.get(f'{name}.{error.key}')
        if not message:
            message = self._meta.messages.get(error.key)
        if not message:
            message = DEFAULT_MESSAGES.get(error.key, 'Validation failed.')
        self.errors[name] = message.format(**error.kwargs)

    def initialize_fields(self):
        for field in dir(self):  # noqa: WPS421
            obj = getattr(self, field)
            if isinstance(obj, Field):
                self._meta.fields[field] = obj

    def validate(self, data=None, only=None, exclude=None, ctx=None):  # noqa: WPS231
        only = only or []
        exclude = exclude or []
        data = data or {}
        self.errors = {}
        self.data = {}

        # Validate individual fields.
        for name, field in self._meta.fields.items():
            if name in exclude or (only and name not in only):
                continue
            try:
                field.validate(name, data, ctx)
            except ValidationError as err:
                self.add_error(name, err)
                continue
            self.data[name] = field.value

        # Clean individual fields.
        if not self.errors:
            self.clean_fields(self.data)

        # Then finally clean the whole data dict.
        if not self.errors:
            try:
                self.data = self.clean(self.data)
            except ValidationError as err:  # noqa: WPS440
                self.add_error('__base__', err)

        return not self.errors

    def clean_fields(self, data):
        for name, value in data.items():  # noqa: WPS327
            try:
                method = getattr(self, f'clean_{name}', None)
                if method:
                    self.data[name] = method(value)
            except ValidationError as err:
                self.add_error(name, err)
                continue

    def clean(self, data):
        return data


class ModelValidator(Validator):
    __slots__ = ('data', 'errors', '_meta', 'instance', 'pk_field', 'pk_value')

    FIELD_MAP = {  # noqa: WPS115
        'smallint': IntegerField,
        'bigint': IntegerField,
        'bool': BooleanField,
        'date': DateField,
        'datetime': DateTimeField,
        'decimal': DecimalField,
        'double': FloatField,
        'float': FloatField,
        'int': IntegerField,
        'time': TimeField,
    }

    def __init__(self, instance):
        if not isinstance(instance, peewee.Model):
            message = 'First argument to {} must be an instance of peewee.Model.'  # noqa: P103
            raise AttributeError(message.format(type(self).__name__))

        self.instance = instance
        self.pk_field = self.instance._meta.primary_key
        self.pk_value = self.instance.get_id()

        super().__init__()

    def initialize_fields(self):
        # # Pull all the "normal" fields off the model instance meta.
        for name, field in self.instance._meta.fields.items():
            if getattr(field, 'primary_key', False):
                continue
            self._meta.fields[name] = self.convert_field(name, field)

        # Many-to-many fields are not stored in the meta fields dict.
        # Pull them directly off the class.
        for mtm_name in dir(type(self.instance)):  # noqa: WPS421
            mtm_field = getattr(type(self.instance), mtm_name, None)
            if isinstance(mtm_field, ManyToManyField):
                self._meta.fields[mtm_name] = self.convert_field(mtm_name, mtm_field)

        super().initialize_fields()

    def convert_field(self, name, field):
        field_type = field.field_type.lower()

        pwv_field = ModelValidator.FIELD_MAP.get(field_type, StringField)

        validators = []
        required = not bool(getattr(field, 'null', True))
        choices = getattr(field, 'choices', ())
        default = getattr(field, default_const, None)
        max_length = getattr(field, 'max_length', None)
        unique = getattr(field, 'unique', False)

        if required:
            validators.append(validate_required())

        if choices:
            validators.append(validate_one_of([c[0] for c in choices]))

        if max_length:
            validators.append(validate_length(high=max_length))

        if unique:
            validators.append(validate_model_unique(field, self.instance.select(), self.pk_field, self.pk_value))

        if isinstance(field, peewee.ForeignKeyField):
            rel_field = field.rel_field
            return ModelChoiceField(field.rel_model, rel_field, default=default, validators=validators)

        if isinstance(field, ManyToManyField):
            return ManyModelChoiceField(
                field.rel_model, field.rel_model._meta.primary_key, default=default, validators=validators,
            )

        return pwv_field(default=default, validators=validators)

    def validate(self, data=None, only=None, exclude=None):  # noqa: WPS231
        data = data or {}
        only = only or self._meta.only
        exclude = exclude or self._meta.exclude

        for name, _ in self.instance._meta.fields.items():
            if name in exclude or (only and name not in only):
                continue
            try:
                data.setdefault(name, getattr(self.instance, name, None))
            except (peewee.DoesNotExist):
                instance_data = self.instance.__data__  # noqa: WPS609
                data.setdefault(name, instance_data.get(name, None))

        # This will set self.data which we should use from now on.
        super().validate(data=data, only=only, exclude=exclude, ctx=self.instance)

        if not self.errors:
            self.perform_index_validation(self.data)

        return not self.errors

    def perform_index_validation(self, data):  # noqa: WPS231
        # Build a list of dict containing query values for each unique index.
        index_data = []
        for columns, unique in self.instance._meta.indexes:
            if not unique:
                continue
            index_data.append({col: data.get(col, None) for col in columns})

        # Then query for each unique index to see if the value is unique.
        for index in index_data:
            query = self.instance.filter(**index)
            # If we have a primary key, need to exclude the current record from the check.
            if self.pk_field and self.pk_value:
                query = query.where(~(self.pk_field == self.pk_value))
            if query.count():
                err = ValidationError('index', fields=str.join(', ', index.keys()))
                for col in index.keys():
                    self.add_error(col, err)

    def save(self, force_insert=False):
        delayed = {}
        for field, value in self.data.items():
            model_field = getattr(type(self.instance), field, None)

            # If this is a many-to-many field, we cannot save it to the instance until the instance
            # is saved to the database. Collect these fields and delay the setting until after
            # the model instance is saved.
            if isinstance(model_field, ManyToManyField):
                if value is not None:  # pragma: no cover
                    delayed[field] = value
                continue

            setattr(self.instance, field, value)

        rv = self.instance.save(force_insert=force_insert)

        for delayed_field, delayed_value in delayed.items():
            setattr(self.instance, delayed_field, delayed_value)

        return rv  # noqa: R504
