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
