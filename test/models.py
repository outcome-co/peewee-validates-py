from __future__ import annotations

from typing import Any, Sequence, cast

import peewee

M2M_RELATED = 'backref'


database = peewee.SqliteDatabase(':memory:')


def getname():
    return 'Tim'


class BasicFields(peewee.Model):
    id: int  # noqa: A003
    field1 = peewee.CharField(default=getname)
    field2 = peewee.CharField()
    field3 = peewee.CharField()

    class Meta:
        database = database  # noqa: WPS434
        indexes = (
            (('field1', 'field2'), True),
            (('field3',), False),
        )


class Organization(peewee.Model):
    id: int  # noqa: A003
    name = peewee.CharField(null=False)

    class Meta:
        database = database  # noqa: WPS434


class PayGrade(peewee.Model):
    name = peewee.CharField(null=False)

    class Meta:
        database = database  # noqa: WPS434


class Person(peewee.Model):
    name = peewee.CharField(null=False, max_length=5, unique=True)

    class Meta:
        database = database  # noqa: WPS434


class ComplexPerson(Person):
    GENDER_CHOICES = (('M', 'Male'), ('F', 'Female'))  # noqa: WPS115
    gender = peewee.CharField(choices=GENDER_CHOICES)

    organization = peewee.ForeignKeyField(Organization, null=False)
    pay_grade = peewee.ForeignKeyField(PayGrade, null=True)

    class Meta:  # type: ignore
        database = database  # noqa: WPS434
        indexes = (
            (('gender', 'name'), True),
            (('name', 'organization'), True),
        )


class Student(peewee.Model):
    id: int  # noqa: A003
    name = peewee.CharField(max_length=10)
    courses: Sequence[Course]

    class Meta:
        database = database  # noqa: WPS434


class Course(peewee.Model):
    id: int  # noqa: A003
    name = peewee.CharField(max_length=10)

    params = {M2M_RELATED: 'courses'}
    students: Sequence[Student] = cast(Any, peewee.ManyToManyField(Student, **params))

    class Meta:
        database = database  # noqa: WPS434


Organization.create_table(safe=True)
PayGrade.create_table(safe=True)
ComplexPerson.create_table(safe=True)
Person.create_table(safe=True)
BasicFields.create_table(safe=True)

Student.create_table(safe=True)
Course.create_table(safe=True)
Course.students.get_through_model().create_table(safe=True)  # type: ignore

organization = Organization(name='main')
organization.save()
