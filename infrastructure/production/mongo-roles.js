// DBA-only setup. Connect using an injected administrative URI, never argv secrets.
if (process.env.APP_ENV !== 'production') throw new Error('Production operator context required.');
const database = process.env.MONGODB_DATABASE || '';
if (!/^[a-z][a-z0-9_]{2,62}$/.test(database) || ['admin','local','config','student_support_dev','student_support_test'].includes(database) || database.startsWith('student_support_restore_')) throw new Error('Separate production application DB required.');
const uri = process.env.MONGODB_ADMIN_URI || '';
const options = new Map();
for (const pair of uri.matchAll(/[?&]([^=]+)=([^&]+)/g)) {
 const key=pair[1].toLowerCase(), value=pair[2].toLowerCase();
 if(options.has(key)) throw new Error('Duplicate connection options refused.');
 options.set(key,value);
}
if (!/^mongodb(?:\+srv)?:\/\//.test(uri) || (options.get('tls') || (uri.startsWith('mongodb+srv://')?'true':'false'))!=='true' || ['tlsinsecure','tlsallowinvalidcertificates','tlsallowinvalidhostnames'].some(k=>(options.get(k)||'false')!=='false')) throw new Error('Verified administrative TLS required.');
const admin = new Mongo(uri).getDB('admin');
const target=admin.getSiblingDB(database);
const resource=collection=>({db:database,collection});
const ordinary=['users','teams','memberships','referrals','triage_claims','privileged_grants'];
const web=[...ordinary.map(collection=>({resource:resource(collection),actions:['find','insert','update']})),
 ...['sessions','auth_attempts','submission_keys'].map(collection=>({resource:resource(collection),actions:['find','insert','update','remove']})),
 {resource:resource('cases'),actions:['find','insert','update']},
 ...['messages','internal_notes'].map(collection=>({resource:resource(collection),actions:['find','insert']})),
 ...['account_closures','enrolment_invitations','disposal_records','rate_limits','notification_outbox'].map(collection=>({resource:resource(collection),actions:['find','insert','update']})),
 {resource:resource('case_events'),actions:['find','insert']},
 {resource:resource('audit_events'),actions:['insert']}];
const worker=[{resource:resource('notification_outbox'),actions:['find','update']},...['users','service_principals'].map(collection=>({resource:resource(collection),actions:['find']}))];
const audit=[{resource:resource('audit_events'),actions:['find']}];
const maintenance=[...['users','teams','memberships','cases','messages','internal_notes','referrals','sessions','auth_attempts','submission_keys','triage_claims','privileged_grants','service_principals','account_closures','enrolment_invitations','disposal_records','rate_limits','notification_outbox','case_events'].map(collection=>({resource:resource(collection),actions:['find','insert','update','remove']})),{resource:resource('audit_events'),actions:['find','insert']}];
for (const [name,privileges] of [['support_web',web],['support_notification_worker',worker],['support_audit_reader',audit],['support_maintenance',maintenance]]) {
 const definition={privileges,roles:[]};
 if(target.getRole(name)) target.updateRole(name,definition); else target.createRole({...definition,role:name});
}
// Root/DBA credentials remain outside all application runtimes. User creation and
// secret rotation are performed by the university DBA using these role definitions.
print('Production least-privilege role definitions prepared; no credentials printed.');
