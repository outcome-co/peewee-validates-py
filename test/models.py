import peewee

try:
    M2M_RELATED = 'related_name'
    from playhouse.fields import ManyToManyField  # noqa: WPS433
except ImportError:
    M2M_RELATED = 'backref'
    from peewee import ManyToManyField  # noqa: WPS433, WPS440

database = peewee.SqliteDatabase(':memory:')


def getname():
    return 'Tim'


class BasicFields(peewee.Model):
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

    class Meta:
        database = database  # noqa: WPS434
        indexes = (
            (('gender', 'name'), True),
            (('name', 'organization'), True),
        )


class Student(peewee.Model):
    name = peewee.CharField(max_length=10)

    class Meta:
        database = database  # noqa: WPS434


class Course(peewee.Model):
    name = peewee.CharField(max_length=10)

    params = {M2M_RELATED: 'courses'}
    students = ManyToManyField(Student, **params)

    class Meta:
        database = database  # noqa: WPS434


Organization.create_table(safe=True)
PayGrade.create_table(safe=True)
ComplexPerson.create_table(safe=True)
Person.create_table(safe=True)
BasicFields.create_table(safe=True)

Student.create_table(safe=True)
Course.create_table(safe=True)
Course.students.get_through_model().create_table(safe=True)

organization = Organization(name='main')
organization.save()
