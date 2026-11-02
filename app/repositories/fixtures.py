"""Idempotent synthetic fixture v1. These are not working OIDC login accounts."""
from datetime import datetime, timezone
from uuid import uuid5, NAMESPACE_URL
from app.services.references import validate_references

VERSION='synthetic-v1'


def fixture_id(label):
    return str(uuid5(NAMESPACE_URL,'student-support/synthetic-v1/'+label))


def fixture_documents(issuer):
    stamp=datetime(2026,11,2,10,tzinfo=timezone.utc)
    users=[]
    names=['student_a','student_b','officer_assigned','officer_unassigned','officer_other',
           'manager_finance','manager_disability','triage','administrator','approver','reviewer','disabled']
    for name in names:
        roles={'student_a':['student'],'student_b':['student'],'administrator':['administrator'],
               'approver':['access_approver'],'reviewer':['audit_reviewer']}.get(name,[])
        document={'_id':fixture_id(name),'identity_issuer':issuer,'identity_subject':'synthetic-placeholder:'+name,
                  'display_name':name.replace('_',' ').title()+' (synthetic)','account_status':'disabled' if name=='disabled' else 'active',
                  'global_roles':roles,'authorization_revision':0,'created_at':stamp}
        if 'student' in roles:document['student_reference']='SYN-'+name.upper()
        users.append(document)
    teams=[{'_id':fixture_id('team_'+name),'name':name.title()+' (synthetic)','category_scope':[name],
            'active':True,'authorization_revision':0} for name in ['finance','disability']]
    memberships=[]
    for user,team,role in [('officer_assigned','finance','officer'),('officer_unassigned','finance','officer'),
                            ('officer_other','disability','officer'),('manager_finance','finance','manager'),
                            ('manager_disability','disability','manager'),('triage','finance','triage')]:
        memberships.append({'_id':fixture_id('membership_'+user),'user_id':fixture_id(user),'team_id':fixture_id('team_'+team),
                            'role':role,'active':True,'granted_by':fixture_id('administrator'),'granted_at':stamp})
    cases=[]
    for label,student,category,officer in [('case_a','student_a','finance','officer_assigned'),
          ('case_a_second','student_a','finance',None),('case_b','student_b','finance',None),
          ('case_other','student_b','disability','officer_other')]:
        cases.append({'_id':fixture_id(label),'reference':'SS-DEMO-'+label.upper(),'student_id':fixture_id(student),
            'category':category,'description':'Synthetic support request for persistence verification.',
            'team_id':fixture_id('team_'+category),'assignee_id':fixture_id(officer) if officer else None,
            'status':'New','priority':'standard','version':1,'created_at':stamp,'updated_at':stamp,'archive_state':'active','legal_hold':False})
    return {'users':users,'teams':teams,'memberships':memberships,'cases':cases,
            'messages':[{'_id':fixture_id('message_a'),'case_id':fixture_id('case_a'),'author_id':fixture_id('student_a'),
                         'body':'Synthetic student-visible message.','created_at':stamp}],
            'internal_notes':[{'_id':fixture_id('note_a'),'case_id':fixture_id('case_a'),'author_id':fixture_id('officer_assigned'),
                               'body':'SYNTHETIC_NOTE_NEVER_STUDENT','created_at':stamp}],
            'service_principals':[{'_id':fixture_id('worker'),'name':'Synthetic notification worker','kind':'notification_worker','active':True,'authorization_revision':0}]}


def seed_fixtures(database,issuer):
    if database.name not in {'student_support_dev','student_support_test'}:
        raise ValueError('Fixtures are restricted to isolated local databases.')
    documents=fixture_documents(issuer)
    with database.client.start_session() as session:
        with session.start_transaction():
            for collection,records in documents.items():
                for record in records:
                    record={**record,'fixture_version':VERSION}
                    if collection in {'memberships','cases','messages','internal_notes'}:
                        validate_references(database,collection,record,session=session)
                    database[collection].update_one({'_id':record['_id']},{'$setOnInsert':record},upsert=True,session=session)
    return sum(map(len,documents.values()))


def reset_fixtures(database):
    if database.name not in {'student_support_dev','student_support_test'}:
        raise ValueError('Fixture reset is restricted to isolated local databases.')
    # Explicit operator action. Never delete a collection/database or unlabelled records.
    from .schema import SCHEMAS
    from app.services.references import REFERENCES
    from .core import InvalidInput
    with database.client.start_session() as session:
        with session.start_transaction():
            fixture_ids={name:[r['_id'] for r in database[name].find({'fixture_version':VERSION},{'_id':1},session=session)] for name in SCHEMAS}
            for name,fields in REFERENCES.items():
                for field,target in fields.items():
                    ids=fixture_ids.get(target,[])
                    if ids and database[name].find_one({field:{'$in':ids},'fixture_version':{'$ne':VERSION}},session=session):
                        raise InvalidInput('Fixture reset would orphan records outside this fixture version.')
            all_ids=[key for keys in fixture_ids.values() for key in keys]
            if database.audit_events.find_one({'target_id':{'$in':all_ids},'fixture_version':{'$ne':VERSION}},session=session):
                raise InvalidInput('Fixture reset would remove targets referenced by other audit records.')
            for name in reversed(list(SCHEMAS)):
                database[name].delete_many({'fixture_version':VERSION},session=session)
