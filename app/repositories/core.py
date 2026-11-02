"""Typed repository primitives. Call only after service policy; no public raw filters."""
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo


class InvalidInput(ValueError):
    pass


def identifier(value):
    if not isinstance(value,str):
        raise InvalidInput('Invalid identifier.')
    try:
        parsed=UUID(value)
    except (ValueError,AttributeError):
        raise InvalidInput('Invalid identifier.') from None
    if str(parsed)!=value:
        raise InvalidInput('Invalid identifier.')
    return value


def plain_text(value,maximum):
    if not isinstance(value,str):
        raise InvalidInput('Text must be a string.')
    value=value.strip()
    if not 1<=len(value)<=maximum:
        raise InvalidInput('Invalid text length.')
    return value


def london_time(value):
    if not isinstance(value,datetime) or value.tzinfo is None:
        raise InvalidInput('An aware UTC timestamp is required.')
    return value.astimezone(ZoneInfo('Europe/London')).strftime('%-d %B %Y, %H:%M %Z')


def utc_now():
    return datetime.now(timezone.utc)


class Repositories:
    def __init__(self,database):
        self.database=database

    def get_user(self,user_id,session=None):
        return self.database.users.find_one({'_id':identifier(user_id)},session=session)

    def get_case(self,case_id,session=None):
        return self.database.cases.find_one({'_id':identifier(case_id)},session=session)

    def student_cases(self,student_id,limit=20,after=None):
        if type(limit) is not int or not 1<=limit<=100:
            raise InvalidInput('Invalid page size.')
        query={'student_id':identifier(student_id),'archive_state':'active'}
        if after is not None:
            if not isinstance(after,tuple) or len(after)!=2 or not isinstance(after[0],datetime) or after[0].tzinfo is None:
                raise InvalidInput('Invalid page cursor.')
            stamp,key=after[0],identifier(after[1])
            query['$or']=[{'updated_at':{'$lt':stamp}},{'updated_at':stamp,'_id':{'$lt':key}}]
        # No direct document serialization in a route; services must build safe views.
        return list(self.database.cases.find(query).sort([('updated_at',-1),('_id',-1)]).limit(limit))
