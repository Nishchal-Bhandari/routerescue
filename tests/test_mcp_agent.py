"""Real stdio tool discovery plus Deep Agent integration with a scripted model.

No external LLM or LangSmith delivery is claimed by these tests.
"""
import json
import uuid
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from routerescue import store
from routerescue.providers.fixtures import bookings,dependencies
from routerescue.domain.models import TripInput
from routerescue.agent.planner import mcp_configuration,invoke_agent,plan


class ScriptedToolModel(GenericFakeChatModel):
    def bind_tools(self,tools,**kwargs):
        return self


@pytest.fixture
def scoped_trip(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'mcp.sqlite3'))
    monkeypatch.setenv('LANGSMITH_TRACING','false')
    store.initialize()
    trip={**TripInput().model_dump(mode='json'),'id':'test-trip','owner_id':'test-owner','version':1,'constraint_version':1,'bookings':bookings('flight'),'dependencies':dependencies('flight')}
    with store.connection() as db:
        db.execute('INSERT INTO trips VALUES(?,?,?)',(trip['id'],trip['owner_id'],store.dump(trip)))
    return trip


@pytest.mark.asyncio
async def test_real_stdio_discovery_invocation_and_scope(scoped_trip):
    client=MultiServerMCPClient(mcp_configuration('test-owner','test-trip'))
    tools={t.name:t for t in await client.get_tools()}
    assert set(tools)=={'get_trip','verify_event','get_impacts','search_transport','search_stays','get_transfer','revalidate_offer','evaluate_options'}
    result=await tools['search_transport'].ainvoke({'mode':'bus'})
    text=json.dumps(result)
    assert 'SIMULATED' in text and 'scenic' in text
    other=MultiServerMCPClient(mcp_configuration('wrong-owner','test-trip'))
    tool=next(t for t in await other.get_tools() if t.name=='get_trip')
    denied=await tool.ainvoke({})
    assert 'Trip not found' in json.dumps(denied)
    assert 'A weekend in Bengaluru' not in json.dumps(denied)


@pytest.mark.asyncio
async def test_deep_agent_calls_real_mcp_tool_and_persists_checkpoint(scoped_trip):
    messages=iter([
        AIMessage(content='',tool_calls=[{'name':'get_trip','args':{},'id':'call-trip','type':'tool_call'}]),
        AIMessage(content='',tool_calls=[{'name':'search_transport','args':{'mode':'all'},'id':'call-search','type':'tool_call'}]),
        AIMessage(content=json.dumps({'candidate_ids':['A','B','C','D'],'evidence_ids':['EV-INVENTORY-1'],'searched_modes':['bus','air']}))
    ])
    model=ScriptedToolModel(messages=messages)
    result=await invoke_agent('test-owner','test-trip',str(uuid.uuid4()),'scripted-test',model_override=model)
    assert result['status']=='COMPLETE' and result['tool_calls']==2 and result['model_calls']==3
    assert store.database_path().with_name('agent-checkpoints.sqlite3').exists()


@pytest.mark.asyncio
async def test_no_key_and_paid_model_guard(monkeypatch):
    monkeypatch.setenv('AGENT_MODE','fixture')
    assert (await plan('owner','trip','run'))['status']=='UNAVAILABLE'
    monkeypatch.setenv('AGENT_MODE','openrouter');monkeypatch.setenv('OPENROUTER_API_KEY','test-placeholder')
    monkeypatch.setenv('OPENROUTER_MODEL','paid/model');monkeypatch.setenv('ALLOW_PAID_MODELS','false')
    result=await plan('owner','trip','run')
    assert result['status']=='UNAVAILABLE' and 'Paid model blocked' in result['message']


@pytest.mark.asyncio
async def test_malformed_output_corrected_once(scoped_trip):
    model=ScriptedToolModel(messages=iter([AIMessage(content='not valid JSON'),AIMessage(content='{"candidate_ids":[],"evidence_ids":[],"searched_modes":[]}')]))
    result=await invoke_agent('test-owner','test-trip',str(uuid.uuid4()),'scripted-test',model_override=model)
    assert result['status']=='COMPLETE' and result['model_calls']==2


@pytest.mark.asyncio
async def test_provider_failure_is_visible_fallback(monkeypatch):
    import routerescue.agent.planner as planner
    async def fail(*args,**kwargs): raise TimeoutError('test provider timeout')
    monkeypatch.setenv('AGENT_MODE','openrouter')
    monkeypatch.setenv('OPENROUTER_API_KEY','test-placeholder')
    monkeypatch.setenv('OPENROUTER_MODEL','openrouter/free')
    monkeypatch.setattr(planner,'invoke_agent',fail)
    result=await planner.plan('owner','trip','run')
    assert result['status']=='FAILED' and 'TimeoutError' in result['message']
