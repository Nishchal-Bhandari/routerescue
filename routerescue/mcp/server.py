"""Private stdio MCP process. Capability is bound to one owner and trip by parent."""
import os
from mcp.server.fastmcp import FastMCP
from routerescue.store import connection, get_trip as read_trip, events_for
from routerescue.providers.fixtures import offers, envelope
from routerescue.domain.engine import impacts, evaluate, rank, frontier
from routerescue.providers.inventory import search_inventory

mcp = FastMCP('RouteRescue read-only travel tools')


def context():
    owner, trip_id = os.environ.get('MCP_OWNER_ID'), os.environ.get('MCP_TRIP_ID')
    if not owner or not trip_id:
        raise ValueError('Missing scoped capability')
    with connection() as db:
        trip = read_trip(db, trip_id, owner)
        if not trip: raise ValueError('Trip not found')
        events = events_for(db, trip_id)
    return trip, events


@mcp.tool()
def get_trip() -> dict:
    """Read this process's authorized trip and constraints. No arbitrary trip lookup."""
    trip, _ = context()
    return envelope(trip)


@mcp.tool()
def verify_event() -> dict:
    """Return synthetic disruption evidence for this trip; never live status."""
    _, events = context()
    return envelope({'events':events,'verification':'USER_REPORTED','note':'Traveller report; not an airline-confirmed cancellation.'})


@mcp.tool()
def get_impacts() -> dict:
    """Compute affected and unaffected bookings using fixture dependency rules."""
    trip, events = context()
    return envelope(impacts(trip, events))


@mcp.tool()
def search_transport(mode: str = 'all') -> dict:
    """Search bounded synthetic transport inventory. mode is all, bus, air or train."""
    if mode not in ('all','bus','air','train'): raise ValueError('Unsupported mode')
    trip, events = context()
    inventory=search_inventory(trip,events)
    return envelope([o for o in inventory if o['mode']!='stay' and (mode=='all' or o['mode']==mode)])


@mcp.tool()
def search_stays() -> dict:
    """Search replacement hotel fixture with explicit cutoff and transfer facts."""
    trip,events=context()
    return envelope([offer for offer in search_inventory(trip,events) if offer['mode']=='stay'])


@mcp.tool()
def get_transfer() -> dict:
    """Return scoped candidate transfer legs, durations and fixture evidence."""
    trip, events=context()
    return envelope([{'option_id':o['id'],'legs':[l for l in o['legs'] if l['mode']=='transfer']} for o in search_inventory(trip,events)])


@mcp.tool()
def revalidate_offer(offer_id: str, expected_version: int) -> dict:
    """Recheck scoped synthetic inventory version and availability; no transaction."""
    trip, events=context()
    offer=next((o for o in search_inventory(trip,events) if o['id']==offer_id),None)
    return envelope({'status':'UNAVAILABLE' if not offer or offer['availability_state']!='AVAILABLE' else ('CHANGED' if offer['version']!=expected_version else 'UNCHANGED'),'offer':offer})


@mcp.tool()
def evaluate_options() -> dict:
    """Check current inventory against this user's budget, report time, arrival and needs; return ranked IDs and explicit trade-offs."""
    trip,events=context()
    evaluations=[evaluate(offer,trip['constraints']) for offer in search_inventory(trip,events)]
    return envelope({'evaluations':evaluations,'ranked_ids':rank(evaluations,trip['constraints']['preference']),'frontier_ids':frontier(evaluations)})


if __name__=='__main__':
    mcp.run(transport='stdio')
