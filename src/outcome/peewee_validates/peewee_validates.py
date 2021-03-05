"""peewee-validates is a validator module designed to work with the Peewee ORM."""
from __future__ import annotations

import datetime
import re
import types
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from inspect import isgenerator, isgeneratorfunction
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Generic,
    List,
    Mapping,
    Optional,
    Pattern,
    Protocol,
    Sequence,
    Sized,
    Tuple,
    TypeVar,
    Union,
    cast,
    runtime_checkable,
)

import peewee
from dateutil.parser import parse as dateutil_parse

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


T = TypeVar('T')
M = TypeVar('M', bound=peewee.Model)


class ValidatorFn(Protocol[T]):  # pragma: no cover
    def __call__(self, field: Field[T], data: Data, ctx: Optional[T] = ...) -> None:
        ...


Data = Mapping[str, object]
Numeric = Union[int, float]
Temporal = Union[datetime.time, datetime.date, datetime.datetime]


@runtime_checkable
class NumericComparable(Protocol):  # pragma: no cover
    def __eq__(self, x: object) -> bool:
        ...

    def __lt__(self: T, x: T) -> bool:
        ...

    def __gt__(self: T, x: T) -> bool:
        ...


@runtime_checkable
class TemporalComparable(Protocol):  # pragma: no cover
    def __eq__(self, o: object) -> bool:
        ...

    def __lt__(self: T, other: T) -> bool:
        ...

    def __gt__(self: T, other: T) -> bool:
        ...


Comparable = Union[TemporalComparable, NumericComparable]


class ValidationError(Exception):
    """An exception class that should be raised when a validation error occurs on data."""

    def __init__(self, key: str, *args: object, **kwargs: object):
        self.key = key
        self.kwargs = kwargs
        super().__init__(*args)


def validate_required() -> ValidatorFn[Any]:
    def required_validator(field: Field[Any], data: Data, ctx: Any = None):
        if field.value is None:  # noqa: WPS204
            raise ValidationError(required_const)

    return required_validator


def validate_not_empty() -> ValidatorFn[Any]:
    def empty_validator(field: Field[Any], data: Data, ctx: Any = None):
        if isinstance(field.value, str) and not field.value.strip():
            raise ValidationError('empty')

    return empty_validator


def validate_length(  # noqa: WPS231,WPS238
    low: Optional[Numeric] = None, high: Optional[Numeric] = None, equal: Optional[Numeric] = None,
) -> ValidatorFn[Any]:
    def length_validator(field: Field[Any], data: Data, ctx: Any = None):  # noqa: WPS231,WPS238
        if field.value is None:
            return

        value = field.value

        if not isinstance(value, Sized):  # pragma: no cover
            raise ValidationError('invalid')

        if equal is not None and len(value) != equal:
            raise ValidationError('length_equal', equal=equal)
        if low is not None and len(value) < low:
            key = 'length_low' if high is None else 'length_between'
            raise ValidationError(key, low=low, high=high)
        if high is not None and len(value) > high:
            key = 'length_high' if low is None else 'length_between'
            raise ValidationError(key, low=low, high=high)

    return length_validator


Values = Collection[object]
ValuesFn = Callable[[], Values]


def validate_one_of(values: Union[Values, ValuesFn]) -> ValidatorFn[Any]:
    def one_of_validator(field: Field[Any], data: Data, ctx: Any = None):
        if field.value is None:
            return
        options = values
        if callable(options):
            options = options()
        if field.value not in options:
            raise ValidationError('one_of', choices=', '.join(map(str, options)))

    return one_of_validator


def validate_none_of(values: Union[Values, ValuesFn]) -> ValidatorFn[Any]:
    def none_of_validator(field: Field[Any], data: Data, ctx: Any = None):
        options = values
        if callable(options):
            options = options()
        if field.value in options:
            raise ValidationError('none_of', choices=', '.join(map(str, options)))

    return none_of_validator


def validate_numeric_range(  # noqa: WPS231
    low: Optional[NumericComparable] = None, high: Optional[NumericComparable] = None,
) -> ValidatorFn[Any]:
    def numeric_range_validator(field: Field[Any], data: Data, ctx: Any = None):  # noqa: WPS231
        if field.value is None:
            return

        value = field.value

        if not isinstance(value, NumericComparable):  # pragma: no cover
            raise ValidationError('invalid comparable')

        if low is not None and value < low:
            key = 'range_low' if high is None else 'range_between'
            raise ValidationError(key, low=low, high=high)
        if high is not None and value > high:
            key = 'range_high' if high is None else 'range_between'
            raise ValidationError(key, low=low, high=high)

    return numeric_range_validator


def validate_temporal_range(  # noqa: WPS231
    low: Optional[TemporalComparable] = None, high: Optional[TemporalComparable] = None,
) -> ValidatorFn[Any]:
    def temporal_range_validator(field: Field[Any], data: Data, ctx: Any = None):  # noqa: WPS231
        if field.value is None:
            return

        value = field.value

        if not isinstance(value, TemporalComparable):  # pragma: no cover
            raise ValidationError('invalid comparable')

        if low is not None and value < low:
            key = 'range_low' if high is None else 'range_between'
            raise ValidationError(key, low=low, high=high)
        if high is not None and value > high:
            key = 'range_high' if high is None else 'range_between'
            raise ValidationError(key, low=low, high=high)

    return temporal_range_validator


def validate_equal(value: object) -> ValidatorFn[Any]:
    def equal_validator(field: Field[Any], data: Data, ctx: Any = None):
        if field.value is None:
            return
        if field.value != value:
            raise ValidationError('equal', other=value)

    return equal_validator


def validate_matches(other: str) -> ValidatorFn[Any]:
    def matches_validator(field: Field[Any], data: Data, ctx: Any = None):
        if field.value is None:
            return
        if field.value != data.get(other):
            raise ValidationError('matches', other=other)

    return matches_validator


def validate_regexp(pattern: Union[str, Pattern[str]], flags: int = 0) -> ValidatorFn[Any]:
    regex = re.compile(pattern, flags) if isinstance(pattern, str) else pattern

    def regexp_validator(field: Field[Any], data: Data, ctx: Any = None):
        if field.value is None:
            return
        if regex.match(str(field.value)) is None:
            raise ValidationError('regexp', pattern=pattern)

    return regexp_validator


class CustomValidatorValueFn(Protocol):  # pragma: no cover
    __name__: str

    def __call__(self, value: object) -> bool:
        ...


class CustomValidatorValueArgsFn(Protocol):  # pragma: no cover
    __name__: str

    def __call__(self, value: object, *args: object) -> bool:
        ...


class CustomValidatorValueKwargsFn(Protocol):  # pragma: no cover
    __name__: str

    def __call__(self, value: object, **kwargs: object) -> bool:
        ...


class CustomValidatorValueArgsKwargsFn(Protocol):  # pragma: no cover
    __name__: str

    def __call__(self, value: object, *args: object, **kwargs: object) -> bool:
        ...


CustomValidatorFn = Union[
    CustomValidatorValueFn,
    CustomValidatorValueArgsFn,
    CustomValidatorValueKwargsFn,
    CustomValidatorValueArgsKwargsFn,
    Callable[..., bool],
]


def validate_function(method: CustomValidatorFn, **kwargs: object) -> ValidatorFn[Any]:
    def function_validator(field: Field[Any], data: Data, ctx: Any = None):
        if field.value is None:
            return
        if not method(field.value, **kwargs):
            raise ValidationError('function', function=method.__name__)

    return function_validator


def validate_email() -> ValidatorFn[Any]:  # noqa: WPS231
    user_regex = re.compile(
        r"(^[-!#$%&'*+/=?^`{}|~\w]+(\.[-!#$%&'*+/=?^`{}|~\w]+)*$"  # noqa: P103
        + r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]'  # noqa: P103
        + r'|\\[\001-\011\013\014\016-\177])*"$)',  # noqa: WPS326
        re.IGNORECASE | re.UNICODE,
    )

    domain_regex = re.compile(
        r'(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'
        '(?:[A-Z]{2,6}|[A-Z0-9-]{2,})$'  # noqa: WPS326
        r'|^\[(25[0-5]|2[0-4]\d|[0-1]?\d?\d)'  # noqa: WPS326
        r'(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\]$',  # noqa: WPS326
        re.IGNORECASE | re.UNICODE,
    )

    domain_whitelist = ('localhost',)

    def email_validator(field: Field[Any], data: Data, ctx: Any = None):
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


class LookupField(Protocol):
    name: str


class QueryLike(Protocol):  # pragma: no cover
    def where(self, *args: object) -> QueryLike:
        ...

    def count(self) -> int:
        ...

    def get(self, *args: object) -> Optional[object]:
        ...

    def select(self) -> QueryLike:
        ...


def validate_model_unique(
    lookup_field: LookupField, queryset: QueryLike, pk_field: Optional[peewee.Field] = None, pk_value: Optional[object] = None,
) -> ValidatorFn[Any]:
    def unique_validator(field: Field[Any], data: Data, ctx: Any = None):
        # If we have a PK, ignore it because it represents the current record.
        query = queryset.where(lookup_field == field.value)
        if pk_field and pk_value:
            query = query.where(~(pk_field == pk_value))
        if query.count():
            raise ValidationError('unique')

    return unique_validator


def coerce_single_instance(lookup_field: LookupField, value: object) -> Any:
    if isinstance(value, dict):
        return cast(Dict[str, object], value).get(lookup_field.name)
    if isinstance(value, peewee.Model):
        return getattr(value, lookup_field.name)
    return value


def isiterable_notstring(value: object):
    if isinstance(value, str):
        return False
    return isinstance(value, Iterable) or isgeneratorfunction(value) or isgenerator(value)


V = TypeVar('V')

DefaultFactory = Callable[[], object]
Default = Union[object, DefaultFactory]


Validators = Sequence[ValidatorFn[T]]


def combine_validators(default_validators: Validators[T], additional_validators: Optional[Validators[T]]) -> Validators[T]:
    return [*default_validators, *(additional_validators or [])]


class Field(Generic[T]):
    __slots__ = (value_const, 'name', required_const, default_const, validators_const)

    name: Optional[str]
    default: Optional[Default]
    value: Optional[object]

    def __init__(
        self, required: bool = False, default: Optional[Default] = None, validators: Optional[Validators[T]] = None,
    ):

        default_validators: Validators[T]
        if required:
            default_validators = [validate_required()]
        else:
            default_validators = []

        self.default = default
        self.value = None
        self.name = None
        self.validators = combine_validators(default_validators, validators)

    def coerce(self, value: V) -> V:
        return value

    def get_value(self, name: str, data: Data) -> Optional[object]:  # noqa: WPS615
        if name in data:
            return data.get(name)

        default = self.default

        if default:
            if callable(default):
                return cast(DefaultFactory, default)()
            return default
        return None

    def validate(self, name: str, data: Data, ctx: Optional[T]):
        self.value = self.get_value(name, data)
        self.name = name
        if self.value is not None:
            self.value = self.coerce(self.value)
        for method in self.validators:
            method(self, data, ctx)


class StringField(Field[T]):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(
        self,
        required: bool = False,
        max_length: Optional[Numeric] = None,
        min_length: Optional[Numeric] = None,
        default: Optional[Default] = None,
        validators: Optional[Validators[T]] = None,
    ):
        default_validators: Validators[T]

        if max_length or min_length:
            default_validators = [validate_length(high=max_length, low=min_length)]
        else:
            default_validators = []

        super().__init__(required=required, default=default, validators=combine_validators(default_validators, validators))

    def coerce(self, value: Optional[object]) -> str:  # type: ignore
        return str(value)


class FloatField(Field[T]):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(
        self,
        required: bool = False,
        low: Optional[Numeric] = None,
        high: Optional[Numeric] = None,
        default: Optional[Default] = None,
        validators: Optional[Validators[T]] = None,
    ):
        default_validators: Validators[T]

        if low or high:
            default_validators = [validate_numeric_range(low=low, high=high)]
        else:
            default_validators = []

        super().__init__(required=required, default=default, validators=combine_validators(default_validators, validators))

    def coerce(self, value: Optional[object]) -> Optional[float]:  # type: ignore
        try:
            return float(value) if value else None  # type: ignore
        except (TypeError, ValueError):
            raise ValidationError('coerce_float')


class IntegerField(Field[T]):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(
        self,
        required: bool = False,
        low: Optional[Numeric] = None,
        high: Optional[Numeric] = None,
        default: Optional[Default] = None,
        validators: Optional[Validators[T]] = None,
    ):
        default_validators: Validators[T]

        if low or high:
            default_validators = [validate_numeric_range(low=low, high=high)]
        else:
            default_validators = []

        super().__init__(required=required, default=default, validators=combine_validators(default_validators, validators))

    def coerce(self, value: Optional[object]) -> Optional[int]:  # type: ignore
        try:
            return int(value) if value is not None else None  # type: ignore
        except (TypeError, ValueError):
            raise ValidationError('coerce_int')


class DecimalField(Field[T]):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(
        self,
        required: bool = False,
        low: Optional[Numeric] = None,
        high: Optional[Numeric] = None,
        default: Optional[Default] = None,
        validators: Optional[Validators[T]] = None,
    ):
        default_validators: Validators[T]

        if low or high:
            default_validators = [validate_numeric_range(low=low, high=high)]
        else:
            default_validators = []

        super().__init__(required=required, default=default, validators=combine_validators(default_validators, validators))

    def coerce(self, value: Optional[object]) -> Optional[Decimal]:  # type: ignore
        try:
            return Decimal(value) if value else None  # type: ignore
        except (TypeError, ValueError, InvalidOperation):
            raise ValidationError('coerce_decimal')


class DateField(Field[T]):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(
        self,
        required: bool = False,
        low: Optional[datetime.date] = None,
        high: Optional[datetime.date] = None,
        default: Optional[Default] = None,
        validators: Optional[Validators[T]] = None,
    ):
        default_validators: Validators[T]

        if low or high:
            default_validators = [validate_temporal_range(low=low, high=high)]
        else:
            default_validators = []

        super().__init__(required=required, default=default, validators=combine_validators(default_validators, validators))

    def coerce(self, value: Optional[object]) -> Optional[datetime.date]:  # type: ignore
        if not value or isinstance(value, datetime.date):
            return value
        try:
            return dateutil_parse(value).date()  # type: ignore
        except (TypeError, ValueError):
            raise ValidationError('coerce_date')


class TimeField(Field[T]):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(
        self,
        required: bool = False,
        low: Optional[datetime.time] = None,
        high: Optional[datetime.time] = None,
        default: Optional[Default] = None,
        validators: Optional[Validators[T]] = None,
    ):
        default_validators: Validators[T]

        if low or high:
            default_validators = [validate_temporal_range(low=low, high=high)]
        else:
            default_validators = []

        super().__init__(required=required, default=default, validators=combine_validators(default_validators, validators))

    def coerce(self, value: Optional[object]) -> Optional[datetime.time]:  # type: ignore
        if not value or isinstance(value, datetime.time):
            return value
        try:
            return dateutil_parse(value).time()  # type: ignore
        except (TypeError, ValueError):
            raise ValidationError('coerce_time')


class DateTimeField(Field[T]):
    __slots__ = (value_const, required_const, default_const, validators_const)

    def __init__(
        self,
        required: bool = False,
        low: Optional[datetime.datetime] = None,
        high: Optional[datetime.datetime] = None,
        default: Optional[Default] = None,
        validators: Optional[Validators[T]] = None,
    ):
        default_validators: Validators[T]

        if low or high:
            default_validators = [validate_temporal_range(low=low, high=high)]
        else:
            default_validators = []

        super().__init__(required=required, default=default, validators=combine_validators(default_validators, validators))

    def coerce(self, value: Optional[object]) -> Optional[datetime.datetime]:  # type: ignore
        if not value or isinstance(value, datetime.datetime):
            return value
        try:
            return dateutil_parse(value)  # type: ignore
        except (TypeError, ValueError):
            raise ValidationError('coerce_datetime')


class BooleanField(Field[T]):
    __slots__ = (value_const, required_const, default_const, validators_const)

    false_values = ('0', '{}', '[]', 'none', 'false')  # noqa: P103

    def coerce(self, value: Optional[object]) -> bool:  # type: ignore
        return str(value).lower() not in self.false_values


class ModelChoiceField(Field[M]):
    __slots__ = ('query', 'lookup_field', value_const, required_const, default_const, validators_const)

    def __init__(self, query: QueryLike, lookup_field: LookupField, required: bool = False, **kwargs: object):
        self.query = query
        self.lookup_field = lookup_field
        super().__init__(required=required, **kwargs)

    def coerce(self, value: object) -> Any:  # type: ignore
        return coerce_single_instance(self.lookup_field, value)

    def validate(self, name: str, data: Data, ctx: Optional[M] = None):
        super().validate(name, data, ctx)
        if self.value is not None:
            try:
                self.value = self.query.get(self.lookup_field == self.value)
            except (AttributeError, ValueError, peewee.DoesNotExist):
                raise ValidationError('related', field=self.lookup_field.name, values=self.value)


class ManyModelChoiceField(Field[M]):
    __slots__ = ('query', 'lookup_field', value_const, required_const, default_const, validators_const)

    def __init__(self, query: QueryLike, lookup_field: LookupField, required: bool = False, **kwargs: object):
        self.query = query
        self.lookup_field = lookup_field
        super().__init__(required=required, **kwargs)

    def coerce(self, value: object) -> Iterable[object]:  # type: ignore
        if isinstance(value, dict):
            value = cast(Sequence[object], [value])
        if not isiterable_notstring(value):  # noqa: WPS504
            value = cast(Sequence[object], [value])
        else:
            value = cast(Sequence[object], value)
        return [coerce_single_instance(self.lookup_field, v) for v in value]

    def validate(self, name: str, data: Data, ctx: Optional[M] = None):
        super().validate(name, data, ctx)
        if self.value is not None and isinstance(self.value, Sequence):
            value = cast(Sequence[object], self.value)
            try:
                # self.query could be a query like "User.select()" or a model like "User"
                # so ".select().where()" handles both cases.
                self.value = [self.query.select().where(self.lookup_field == v).get() for v in value if v]
            except (AttributeError, ValueError, peewee.DoesNotExist):
                raise ValidationError('related', field=self.lookup_field.name, values=value)


class ValidatorOptions(Generic[T]):
    messages: Dict[str, str]
    fields: Dict[str, Field[T]]
    only: Iterable[str]
    exclude: Iterable[str]

    def __init__(self, obj: object):
        self.fields = {}
        self.messages = {}
        self.only = []
        self.exclude = []


class BaseValidator(Generic[T]):
    """A validator class. Can have many fields attached to it to perform validation on data."""

    class Meta:
        pass

    __slots__ = ('data', 'errors', '_meta', 'ctx')

    data: Dict[str, object]
    errors: Dict[str, str]
    ctx: Optional[T]

    def __init__(self):
        self.errors = {}
        self.data = {}

        # Sometimes a subclass has already set context
        if not hasattr(self, 'ctx'):  # noqa: WPS421
            self.ctx = None

        self._meta = ValidatorOptions[T](self)
        self._meta.__dict__.update(self.Meta.__dict__)  # noqa: WPS609

        self.initialize_fields()

    def add_error(self, name: str, error: ValidationError):
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

    def validate(  # noqa: WPS231
        self,
        data: Optional[Data] = None,
        ctx: Optional[T] = None,
        only: Optional[Iterable[str]] = None,
        exclude: Optional[Iterable[str]] = None,
    ):
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

    def clean_fields(self, data: Dict[str, object]):
        for name, value in data.items():
            try:
                method = getattr(self, f'clean_{name}', None)
                if method:
                    self.data[name] = method(value)
            except ValidationError as err:
                self.add_error(name, err)

    def clean(self, data: Dict[str, object]) -> Dict[str, object]:
        return data


class Validator(BaseValidator[None]):
    ...


class ModelMetaLike(Protocol):
    primary_key: peewee.Field
    fields: Dict[str, peewee.Field]
    indexes: Sequence[Tuple[Tuple[str, ...], bool]]  # noqa: WPS234


class ModelLike(QueryLike):  # pragma: no cover
    _meta: ModelMetaLike
    __data__: Data

    def get_id(self) -> object:
        ...

    def select(self) -> QueryLike:
        ...

    def filter(self, *args: object) -> QueryLike:  # noqa: A003
        ...

    def save(self, force_insert: bool) -> int:
        ...


class ModelValidator(BaseValidator[M]):
    __slots__ = ('data', 'errors', '_meta', 'pk_field', 'pk_value', 'meta')

    FIELD_MAP = {  # noqa: WPS115
        'smallint': IntegerField[M],
        'bigint': IntegerField[M],
        'bool': BooleanField[M],
        'date': DateField[M],
        'datetime': DateTimeField[M],
        'decimal': DecimalField[M],
        'double': FloatField[M],
        'float': FloatField[M],
        'int': IntegerField[M],
        'time': TimeField[M],
    }

    meta: ModelMetaLike
    pk_value: object
    pk_field: peewee.Field

    def __init__(self, instance: M):
        # We need to add the type var here
        # Not sure if it's a bug: https://github.com/microsoft/pyright/issues/1577
        self.ctx: M = instance
        self.meta = cast(ModelLike, self.ctx)._meta  # type: ignore
        self.pk_field = self.meta.primary_key
        self.pk_value = self.ctx.get_id()

        # Important that the init comes after setting the above attributes
        super().__init__()

    def initialize_fields(self):
        # # Pull all the "normal" fields off the model instance meta.
        for name, field in self.meta.fields.items():
            if getattr(field, 'primary_key', False):
                continue
            self._meta.fields[name] = self.convert_field(name, field)

        # Many-to-many fields are not stored in the meta fields dict.
        # Pull them directly off the class.
        for mtm_name in dir(type(self.ctx)):  # noqa: WPS421
            mtm_field = getattr(type(self.ctx), mtm_name, None)
            if isinstance(mtm_field, peewee.ManyToManyField):
                self._meta.fields[mtm_name] = self.convert_field(mtm_name, mtm_field)

        super().initialize_fields()

    def convert_field(self, name: str, field: peewee.Field) -> Field[M]:
        field_type = field.field_type.lower()

        pwv_field = ModelValidator.FIELD_MAP.get(field_type, StringField[M])

        validators: List[ValidatorFn[M]] = []
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
            validators.append(validate_model_unique(field, cast(ModelLike, self.ctx).select(), self.pk_field, self.pk_value))

        if isinstance(field, peewee.ForeignKeyField):
            rel_field = cast(peewee.Field, field.rel_field)
            return ModelChoiceField[M](cast(ModelLike, field.rel_model), rel_field, default=default, validators=validators)

        if isinstance(field, peewee.ManyToManyField):
            meta = cast(ModelLike, field.rel_model)._meta  # type: ignore
            return ManyModelChoiceField[M](
                cast(ModelLike, field.rel_model), meta.primary_key, default=default, validators=validators,
            )

        return pwv_field(default=default, validators=validators)

    def validate(self, data: Optional[Data] = None, only: Optional[Iterable[str]] = None, exclude: Optional[Iterable[str]] = None):  # type: ignore  # noqa: WPS231,E501
        data = dict(data or {})
        only = only or self._meta.only
        exclude = exclude or self._meta.exclude

        for name, _ in self.meta.fields.items():
            if name in exclude or (only and name not in only):
                continue
            try:
                data.setdefault(name, getattr(self.ctx, name, None))
            except (peewee.DoesNotExist):
                instance_data = cast(ModelLike, self.ctx).__data__  # noqa: WPS609
                data.setdefault(name, instance_data.get(name, None))

        # This will set self.data which we should use from now on.
        super().validate(data=data, only=only, exclude=exclude, ctx=self.ctx)

        if not self.errors:
            self.perform_index_validation(self.data)

        return not self.errors

    def perform_index_validation(self, data: Data):  # noqa: WPS231
        # Build a list of dict containing query values for each unique index.
        index_data: List[Dict[str, object]] = []
        for columns, unique in self.meta.indexes:
            if not unique:
                continue
            index_data.append({col: data.get(col, None) for col in columns})

        # Then query for each unique index to see if the value is unique.
        for index in index_data:
            query = cast(ModelLike, self.ctx).filter(**index)
            # If we have a primary key, need to exclude the current record from the check.
            if self.pk_field and self.pk_value:
                query = query.where(~(self.pk_field == self.pk_value))
            if query.count():
                err = ValidationError('index', fields=str.join(', ', index.keys()))
                for col in index.keys():
                    self.add_error(col, err)

    def save(self, force_insert: bool = False) -> int:
        delayed: Data = {}
        for field, value in self.data.items():
            model_field = getattr(type(self.ctx), field, None)

            # If this is a many-to-many field, we cannot save it to the instance until the instance
            # is saved to the database. Collect these fields and delay the setting until after
            # the model instance is saved.
            if isinstance(model_field, peewee.ManyToManyField):
                if value is not None:  # pragma: no cover
                    delayed[field] = value
                continue

            setattr(self.ctx, field, value)

        rv = cast(ModelLike, self.ctx).save(force_insert=force_insert)

        for delayed_field, delayed_value in delayed.items():
            setattr(self.ctx, delayed_field, delayed_value)

        return rv  # noqa: R504
