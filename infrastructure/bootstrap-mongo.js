// Trusted local setup only; root and generated passwords remain inside container env.
const admin = new Mongo('mongodb://support_bootstrap:' + encodeURIComponent(process.env.MONGO_INITDB_ROOT_PASSWORD) + '@localhost:27017/admin?directConnection=true').getDB('admin');
let initialised = false;
try {
  const status = admin.runCommand({replSetGetStatus:1});
  initialised = Boolean(status.ok);
} catch (error) {
  if (error.code !== 94) throw error;
}
if (!initialised) {
  const result = admin.runCommand({replSetInitiate:{_id:'rs0',members:[{_id:0,host:'localhost:27017'}]}});
  if (!result.ok) throw new Error('Replica set initiation failed');
}
let primary = false;
for (let i=0;i<60;i++) { if(admin.runCommand({hello:1}).isWritablePrimary) {primary=true;break;} sleep(1000); }
if (!primary) throw new Error('Replica set not ready');
for (const [name,password,database] of [
  ['support_app',process.env.SUPPORT_APP_PASSWORD,'student_support_dev'],
  ['support_test',process.env.SUPPORT_TEST_PASSWORD,'student_support_test']
]) {
  if (!admin.getUser(name)) admin.createUser({user:name,pwd:password,roles:[{role:'readWrite',db:database}]});
}
print('Replica set and separate development/test users ready.');

if (!admin.getUser('support_schema')) {
  admin.createUser({user:'support_schema',pwd:process.env.SUPPORT_SCHEMA_PASSWORD,
    roles:[{role:'dbAdmin',db:'student_support_dev'},{role:'dbAdmin',db:'student_support_test'}]});
}

// Stage 07 collection privileges replace broad readWrite on the public identity.
const collections=['users','teams','memberships','cases','messages','internal_notes',
 'referrals','sessions','auth_attempts','submission_keys','triage_claims',
 'privileged_grants','service_principals'];
function ensureRole(database,name,privileges) {
 const target=admin.getSiblingDB(database);
 const definition={privileges:privileges,roles:[]};
 if(target.getRole(name)) target.updateRole(name,definition); else target.createRole({...definition,role:name});
}
for(const database of ['student_support_dev','student_support_test']) {
 ensureRole(database,'support_web',[
  ...collections.map(collection=>({resource:{db:database,collection},actions:['find','insert','update','remove']})),
  {resource:{db:database,collection:'rate_limits'},actions:['find','insert','update']},
  {resource:{db:database,collection:'disposal_records'},actions:['find','insert','update']},
  {resource:{db:database,collection:'account_closures'},actions:['find','insert','update']},
  {resource:{db:database,collection:'enrolment_invitations'},actions:['find','insert','update']},
  {resource:{db:database,collection:'case_events'},actions:['find','insert']},
  {resource:{db:database,collection:'audit_events'},actions:['insert']},
  {resource:{db:database,collection:'notification_outbox'},actions:['find','insert','update']}
 ]);
 ensureRole(database,'support_audit_reader',[{resource:{db:database,collection:'audit_events'},actions:['find']}]);
 ensureRole(database,'support_notification_worker',[
  {resource:{db:database,collection:'notification_outbox'},actions:['find','update']},
  {resource:{db:database,collection:'users'},actions:['find']},
  {resource:{db:database,collection:'service_principals'},actions:['find']}
 ]);
}
for(const [user,password,roles] of [
 ['support_app',process.env.SUPPORT_APP_PASSWORD,[{role:'support_web',db:'student_support_dev'}]],
 ['support_web_test',process.env.SUPPORT_WEB_TEST_PASSWORD,[{role:'support_web',db:'student_support_test'}]],
 ['support_fixture',process.env.SUPPORT_FIXTURE_PASSWORD,[{role:'readWrite',db:'student_support_dev'}]],
 ['support_audit',process.env.SUPPORT_AUDIT_PASSWORD,[{role:'support_audit_reader',db:'student_support_dev'}]],
 ['support_audit_test',process.env.SUPPORT_AUDIT_TEST_PASSWORD,[{role:'support_audit_reader',db:'student_support_test'}]],
 ['support_worker',process.env.SUPPORT_WORKER_PASSWORD,[{role:'support_notification_worker',db:'student_support_dev'}]],
 ['support_worker_test',process.env.SUPPORT_WORKER_TEST_PASSWORD,[{role:'support_notification_worker',db:'student_support_test'}]]
]) {
 if(admin.getUser(user)) admin.updateUser(user,{roles}); else admin.createUser({user,pwd:password,roles});
}

if(!admin.getUser('support_restore')) admin.createUser({user:'support_restore',pwd:process.env.SUPPORT_RESTORE_PASSWORD,roles:[{role:'readWrite',db:'student_support_restore_test'}]});
admin.updateUser('support_schema',{roles:['student_support_dev','student_support_test','student_support_restore_test'].map(db=>({role:'dbAdmin',db}))});
