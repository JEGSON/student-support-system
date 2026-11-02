"""Reference integrity checks before trusted service writes; not an access policy."""
from app.repositories.core import identifier, InvalidInput

REFERENCES={
 'memberships':{'user_id':'users','team_id':'teams','granted_by':'users'},
 'cases':{'student_id':'users','team_id':'teams','assignee_id':'users','resolution_message_id':'messages','originating_referral_id':'referrals'},
 'messages':{'case_id':'cases','author_id':'users','correction_of':'messages'},
 'internal_notes':{'case_id':'cases','author_id':'users','supersedes_id':'internal_notes'},
 'case_events':{'case_id':'cases','actor_id':'users','old_assignee':'users','new_assignee':'users'},
 'referrals':{'source_case_id':'cases','target_team_id':'teams','requested_by':'users','source_approved_by':'users','decided_by':'users','target_case_id':'cases'},
 'audit_events':{'actor_id':'users','service_id':'service_principals'},
 'notification_outbox':{'recipient_user_id':'users','case_id':'cases'},
 'sessions':{'user_id':'users'},'submission_keys':{'user_id':'users','result_id':'cases'},
 'triage_claims':{'case_id':'cases','user_id':'users','team_id':'teams'},
 'privileged_grants':{'user_id':'users','requested_by':'users','approved_by':'users','team_id':'teams'},
}


def validate_references(database,collection,document,session=None):
    if collection not in REFERENCES:
        raise InvalidInput('Unsupported reference contract.')
    for field,target in REFERENCES[collection].items():
        value=document.get(field)
        if value is not None:
            record=database[target].find_one({'_id':identifier(value)},session=session)
            if record is None:
                raise InvalidInput('Referenced record is unavailable.')
            if field in {'correction_of','supersedes_id','resolution_message_id'} and record['case_id']!=document.get('case_id',document.get('_id')):
                raise InvalidInput('Referenced record belongs to another case.')
    if collection=='cases':
        student=database.users.find_one({'_id':identifier(document['student_id'])},session=session)
        if student is None or 'student' not in student['global_roles']:
            raise InvalidInput('Case ownership requires a student account.')
        team=database.teams.find_one({'_id':identifier(document['team_id']),'active':True},session=session)
        if team is None or document['category'] not in team['category_scope']:
            raise InvalidInput('Category routing is unavailable.')
        if document.get('assignee_id'):
            assignee=database.users.find_one({'_id':document['assignee_id'],'account_status':'active'},session=session)
            membership=database.memberships.find_one({'user_id':document['assignee_id'],'team_id':document['team_id'],
                'active':True,'role':{'$in':['officer','manager']}},session=session)
            if not assignee or not membership:
                raise InvalidInput('Assignee is not eligible for this team.')
