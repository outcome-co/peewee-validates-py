from test.models import BasicFields, ComplexPerson, Course, Organization, Person, Student
from typing import Dict, cast

import peewee
from playhouse.postgres_ext import ArrayField, BinaryJSONField, HStoreField

from outcome.peewee_validates.peewee_validates import DEFAULT_MESSAGES
from outcome.peewee_validates.peewee_validates import M as ModelType  # noqa: N811
from outcome.peewee_validates.peewee_validates import ManyModelChoiceField, ModelValidator, QueryLike, ValidationError

student_tim = Student(name='tim')


def test_instance():
    instance = Person()
    validator = ModelValidator(instance)
    assert validator.validate({'name': 'tim'})
    assert validator.data['name'] == 'tim'


def test_required():
    validator = ModelValidator(Person())
    assert not validator.validate()
    assert validator.errors['name'] == DEFAULT_MESSAGES['required']


def test_clean():
    class TestValidator(ModelValidator[ModelType]):
        def clean(self, data: Dict[str, object]):
            super().clean(data)
            v = data['name']
            assert isinstance(v, str)
            data['name'] = v + 'awesome'  # noqa: WPS336
            return data

    validator = TestValidator(Person())
    assert validator.validate({'name': 'tim'})
    assert validator.data['name'] == 'timawesome'


def test_clean_error():
    class TestValidator(ModelValidator[ModelType]):
        def clean(self, data: Dict[str, object]) -> Dict[str, object]:
            raise ValidationError('required')

    validator = TestValidator(Person())
    assert not validator.validate({'name': 'tim'})
    assert validator.data['name'] == 'tim'
    assert validator.errors['__base__'] == DEFAULT_MESSAGES['required']


def test_choices():
    validator = ModelValidator(ComplexPerson(name='tim'))

    assert not validator.validate({'organization': 1, 'gender': 'S'})
    assert validator.errors['gender'] == DEFAULT_MESSAGES['one_of'].format(choices='M, F')
    assert 'name' not in validator.errors

    assert validator.validate({'organization': 1, 'gender': 'M'})


def test_default():
    validator = ModelValidator(BasicFields())
    assert not validator.validate()
    assert validator.data['field1'] == 'Tim'
    assert validator.errors['field2'] == DEFAULT_MESSAGES['required']
    assert validator.errors['field3'] == DEFAULT_MESSAGES['required']


def test_related_required_missing():  # noqa: WPS218
    validator = ModelValidator(ComplexPerson(name='tim', gender='M'))

    assert not validator.validate({'organization': 999})
    assert validator.errors['organization'] == DEFAULT_MESSAGES['related'].format(field='id', values=999)  # noqa: WPS432

    assert not validator.validate({'organization': None})
    assert validator.errors['organization'] == DEFAULT_MESSAGES['required']

    assert not validator.validate()
    assert validator.errors['organization'] == DEFAULT_MESSAGES['required']


def test_related_optional_missing():
    validator = ModelValidator(ComplexPerson(name='tim', gender='M', organization=1))

    assert not validator.validate({'pay_grade': 999})
    assert validator.errors['pay_grade'] == DEFAULT_MESSAGES['related'].format(field='id', values=999)  # noqa: WPS432

    assert validator.validate({'pay_grade': None})

    assert validator.validate()


def test_related_required_int():
    org = Organization.create(name='new1')
    validator = ModelValidator(ComplexPerson(name='tim', gender='M'))
    assert validator.validate({'organization': org.id})


def test_related_required_instance():
    org = Organization.create(name='new1')
    validator = ModelValidator(ComplexPerson(name='tim', gender='M'))
    assert validator.validate({'organization': org})


def test_related_required_dict():
    org = Organization.create(name='new1')
    validator = ModelValidator(ComplexPerson(name='tim', gender='M'))
    assert validator.validate({'organization': {'id': org.id}})


def test_related_required_dict_missing():
    validator = ModelValidator(ComplexPerson(name='tim', gender='M'))
    validator.validate({'organization': {}})
    assert validator.errors['organization'] == DEFAULT_MESSAGES['required']


def test_related_optional_dict_missing():
    validator = ModelValidator(ComplexPerson(name='tim', gender='M', organization=1))
    assert validator.validate({'pay_grade': {}})


def test_unique():
    person = Person.create(name='tim')

    validator = ModelValidator(Person(name='tim'))
    assert not validator.validate({'gender': 'M'})
    assert validator.errors['name'] == DEFAULT_MESSAGES['unique']

    validator = ModelValidator(person)
    assert validator.validate({'gender': 'M'})


def test_unique_index():
    obj1 = BasicFields.create(field1='one', field2='two', field3='three')
    obj2 = BasicFields(field1='one', field2='two', field3='three')

    validator = ModelValidator(obj2)
    assert not validator.validate()
    assert validator.errors['field1'] == DEFAULT_MESSAGES['index']
    assert validator.errors['field2'] == DEFAULT_MESSAGES['index']

    validator = ModelValidator(obj1)
    assert validator.validate()


def test_validate_only():
    obj = BasicFields(field1='one')

    validator = ModelValidator(obj)
    assert validator.validate(only=('field1',))


def test_save():
    obj = BasicFields(field1='one', field2='124124', field3='1232314')

    validator = ModelValidator(obj)
    assert validator.validate({'field1': 'updated'})

    validator.save()

    assert obj.id
    assert obj.field1 == 'updated'


def test_m2m_empty():
    validator = ModelValidator(student_tim)

    assert validator.validate()

    assert validator.validate({'courses': []})


def test_m2m_missing():
    validator = ModelValidator(student_tim)

    assert not validator.validate({'courses': [1, 33]})
    assert validator.errors['courses'] == DEFAULT_MESSAGES['related'].format(field='id', values=[1, 33])


def test_m2m_ints():
    validator = ModelValidator(student_tim)

    c1 = Course.create(name='course1')
    c2 = Course.create(name='course2')

    assert validator.validate({'courses': [c1.id, c2.id]})

    assert validator.validate({'courses': c1.id})

    assert validator.validate({'courses': str(c1.id)})


def test_m2m_instances():
    validator = ModelValidator(student_tim)

    c1 = Course.create(name='course1')
    c2 = Course.create(name='course2')

    assert validator.validate({'courses': [c1, c2]})

    assert validator.validate({'courses': c1})


def test_m2m_dicts():
    validator = ModelValidator(student_tim)

    c1 = Course.create(name='course1')
    c2 = Course.create(name='course2')

    assert validator.validate({'courses': [{'id': c1.id}, {'id': c2.id}]})

    assert validator.validate({'courses': {'id': c1.id}})


def test_m2m_dicts_blank():
    validator = ModelValidator(student_tim)

    assert validator.validate({'courses': [{}, {}]})

    assert validator.validate({'courses': {}})


def test_m2m_save():
    obj = student_tim
    validator = ModelValidator(obj)

    c1 = Course.create(name='course1')
    c2 = Course.create(name='course2')

    assert validator.validate({'courses': [c1, c2]})

    validator.save()

    assert obj.id
    assert c1 in obj.courses
    assert c2 in obj.courses


def test_m2m_save_blank():
    obj = student_tim
    validator = ModelValidator(obj)

    assert validator.validate({'courses': [{}, {}]})

    validator.save()

    assert obj.id


def test_overrides():
    class CustomValidator(ModelValidator[ModelType]):
        students = ManyModelChoiceField[ModelType](cast(QueryLike, Student.select()), Student.name)

    Student.create(name='tim')
    Student.create(name='bob')

    obj = Course.create(name='course1')

    validator = CustomValidator(obj)

    data = {'students': [{'name': 'tim'}, 'bob']}
    assert validator.validate(data)

    validator.save()

    assert obj.id
    assert len(obj.students) == 2


class ArrayModel(peewee.Model):
    items = ArrayField(peewee.IntegerField)


def test_array_type():
    m = ArrayModel(items=[1, 2])
    validator = ModelValidator(m)
    validator.validate()
    assert not validator.errors


def test_invalid_array():
    m = ArrayModel(items=True)
    validator = ModelValidator(m)
    assert not validator.validate()


class JSONModel(peewee.Model):
    doc = BinaryJSONField()


def test_json_type():
    m = JSONModel(doc={'items': [1, 2]})
    validator = ModelValidator(m)
    validator.validate()
    assert not validator.errors


class MappingModel(peewee.Model):
    mapping = HStoreField()


def test_valid_mapping_type():
    m = MappingModel(mapping={'items': 1})
    validator = ModelValidator(m)
    validator.validate()
    assert not validator.errors


def test_invalid_mapping_type():
    m = MappingModel(mapping=True)
    validator = ModelValidator(m)
    assert not validator.validate()
