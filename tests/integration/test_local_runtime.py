"""Opt-in checks against the actual generated, isolated dependency stack."""
import os
from pathlib import Path
import secrets
import pytest
from dotenv import dotenv_values
from pymongo.errors import OperationFailure
from app import create_app

pytestmark = [pytest.mark.runtime, pytest.mark.skipif(os.getenv('RUN_RUNTIME') != '1', reason='Set RUN_RUNTIME=1 with the local stack running')]


def test_real_dependencies_and_database_credential_isolation():
    config=dict(dotenv_values(Path(__file__).resolve().parents[2]/'.env'))
    development=create_app(config)
    try:
        response=development.test_client().get('/health/ready')
        assert response.status_code==200 and response.json=={'status':'ready'}
        test_uri=f"mongodb://support_test:{config['MONGO_TEST_PASSWORD']}@localhost:27017/admin?replicaSet=rs0&directConnection=true"
        testing=create_app({**config,'APP_ENV':'testing','MONGODB_URI':test_uri,'MONGODB_DATABASE':'student_support_test'})
        client=testing.extensions['mongo']
        try:
            with pytest.raises(OperationFailure) as error:
                client.student_support_dev.isolation_probe.find_one({})
            assert error.value.code==13
            with pytest.raises(OperationFailure) as error:
                development.extensions['mongo'].student_support_test.isolation_probe.find_one({})
            assert error.value.code==13
            # Actual replica-set transaction, synthetic probe, explicitly aborted.
            probe=secrets.token_hex(12)
            with client.start_session() as session:
                session.start_transaction()
                client.student_support_test.isolation_probe.insert_one({'_id':probe,'synthetic':True},session=session)
                session.abort_transaction()
            assert client.student_support_test.isolation_probe.find_one({'_id':probe}) is None
        finally:
            client.close()
    finally:
        development.extensions['mongo'].close()
