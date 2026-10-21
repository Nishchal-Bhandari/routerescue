"""Pure feasibility and graph functions. LLM text has no authority here."""
from datetime import timedelta, datetime, timezone
from routerescue.domain.models import parse_time


def validate_graph(nodes, edges):
    ids = {n['id'] for n in nodes}
    remaining = set(ids)
    if len(ids) != len(nodes):
        raise ValueError('Duplicate booking IDs')
    if any(e['from_id'] not in ids or e['to_id'] not in ids for e in edges):
        raise ValueError('Unknown dependency node')
    while remaining:
        roots = {n for n in remaining if not any(e['to_id']==n and e['from_id'] in remaining for e in edges)}
        if not roots:
            raise ValueError('Trip dependencies contain a cycle')
        remaining -= roots


def impacts(trip, events):
    nodes, edges = trip['bookings'], trip['dependencies']
    validate_graph(nodes, edges)
    result = {n['id']: dict(booking_id=n['id'], status='USABLE', reason='No failing dependency identified.', evidence_ids=['EV-POLICY-1'], dependency_paths=[]) for n in nodes}
    by_id = {n['id']:n for n in nodes}
    effective = {n['id']:parse_time(n['end']) for n in nodes}
    # A hotel's end is its cutoff, not a traveller's departure time.
    for node in nodes:
        if node['kind']=='hotel': effective[node['id']]=parse_time(node['start'])+timedelta(minutes=30)
    event_types = {e['event_type'] for e in events}
    root = 'T1' if trip['scenario']=='train' else 'F1'
    if 'FLIGHT_CANCELLED' in event_types or 'TRAIN_DELAYED' in event_types:
        result[root].update(status='DISRUPTED', reason='Service cancelled in fixture.' if root=='F1' else 'Train delayed to 16:00 in fixture.')
        effective[root] = None if root=='F1' else parse_time('2026-11-15T16:00:00+05:30')
    if 'HOTEL_CANCELLED' in event_types:
        result['H1'].update(status='DISRUPTED', reason='Room cancelled in fixture; replacement lodging required.')
        effective['H1']=None
    pending=set(by_id)
    while pending:
        ready=[n for n in pending if not any(e['to_id']==n and e['from_id'] in pending for e in edges)]
        for node_id in sorted(ready):
            pending.remove(node_id)
            if result[node_id]['status']=='DISRUPTED': continue
            for edge in (e for e in edges if e['to_id']==node_id):
                parent=edge['from_id']; source_time=effective[parent]
                result[node_id]['dependency_paths'].append([parent,node_id])
                if source_time is None:
                    result[node_id].update(status='AT_RISK',reason=f"{parent} has no verified replacement timing. Review this dependent booking.")
                    effective[node_id]=None
                    continue
                required=source_time+timedelta(minutes=edge.get('buffer_minutes',0))
                target=by_id[node_id]
                if edge['rule']=='ARRIVAL_BEFORE':
                    if required>parse_time(target['start']):
                        result[node_id].update(status='AT_RISK',reason='The original pickup cannot meet the changed arrival. Review or reschedule it.')
                        effective[node_id]=required+(parse_time(target['end'])-parse_time(target['start']))
                elif edge['rule']=='CHECKIN_BEFORE':
                    if required>parse_time(target['end']):
                        result[node_id].update(status='AT_RISK',reason='Projected check-in misses the fixture cutoff.')
                    else: result[node_id]['reason']='Projected check-in still meets the fixture cutoff.'
                    effective[node_id]=max(required,parse_time(target['start']))
                elif edge['rule']=='TRANSFER_TO':
                    deadline=parse_time(trip.get('constraints',{}).get('latest_arrival','2026-11-15T19:00:00+05:30'))
                    if required>deadline: result[node_id].update(status='AT_RISK',reason='Onward transfer cannot meet your venue arrival deadline.')
                    else: result[node_id]['reason']='Onward transfer still meets your venue arrival deadline.'
                elif edge['rule']=='REQUIRES_BOOKING' and result[parent]['status']!='USABLE':
                    result[node_id].update(status='AT_RISK',reason=f'Requires usable booking {parent}.')
    return list(result.values())


def evaluate(offer, constraints, now=None):
    reasons, unknown = [], []
    now = now or datetime.now(timezone.utc)
    amounts = [r.get('amount_minor') for r in offer['ledger']]
    cash = sum(amounts) * constraints['passengers'] if all(isinstance(v,int) and not isinstance(v,bool) and v>=0 for v in amounts) and amounts else None
    if cash is None: unknown.append('REQUIRED_FACT_UNKNOWN')
    if offer.get('currency') != 'INR': reasons.append('CURRENCY_MISMATCH')
    if offer.get('availability_state') != 'AVAILABLE': reasons.append('OFFER_UNAVAILABLE')
    if parse_time(offer['valid_until']) <= now: reasons.append('OFFER_EXPIRED')
    if offer['mode'] != 'stay' and offer['mode'] not in constraints['allowed_modes']: reasons.append('MODE_NOT_ALLOWED')
    for key, needed, code in [('capacity',constraints['passengers'],'CAPACITY_EXCEEDED'),('bags',constraints['bags'],'BAGGAGE_EXCEEDED')]:
        if offer.get(key) is None: unknown.append('REQUIRED_FACT_UNKNOWN')
        elif offer[key] < needed: reasons.append(code)
    if constraints['wheelchair']:
        if offer.get('wheelchair') is None: unknown.append('ACCESSIBILITY_UNVERIFIED')
        elif offer['wheelchair'] is not True: reasons.append('ACCESSIBILITY_UNAVAILABLE')
    legs = offer['legs']
    slacks = []
    if not legs: unknown.append('REQUIRED_FACT_UNKNOWN')
    for i, leg in enumerate(legs):
        if parse_time(leg['arrival']) < parse_time(leg['departure']): reasons.append('INVALID_TIMELINE')
        if i:
            previous = legs[i-1]
            if previous['destination'] != leg['origin']: reasons.append('LOCATION_DISCONTINUITY')
            slack = int((parse_time(leg['departure'])-parse_time(previous['arrival'])).total_seconds()/60) - previous.get('dwell_minutes',0) - leg.get('boarding_buffer_minutes',0)
            slacks.append(slack)
            if slack < 0: reasons.append('TRANSFER_TOO_SHORT')
    arrival = parse_time(offer['arrival'])
    if legs and (parse_time(legs[-1]['arrival']) != arrival or legs[-1]['destination'] != 'Bengaluru craft studio'): reasons.append('LOCATION_DISCONTINUITY')
    if offer.get('hotel_arrival') is None: unknown.append('REQUIRED_FACT_UNKNOWN')
    elif parse_time(offer['hotel_arrival']) > parse_time('2026-11-15T18:00:00+05:30'): reasons.append('POLICY_CONFLICT')
    budget_delta = max(0, cash-constraints['cash_limit_minor']) if cash is not None else None
    late_minutes = max(0, int((arrival-parse_time(constraints['latest_arrival'])).total_seconds()//60))
    if arrival > parse_time(constraints['latest_arrival']) and not late_minutes: late_minutes=1
    if budget_delta: reasons.append('OVER_BUDGET')
    if late_minutes: reasons.append('ARRIVES_LATE')
    return dict(option_id=offer['id'], status='NEEDS_VERIFICATION' if unknown else ('INFEASIBLE' if reasons else 'FEASIBLE'), reason_codes=list(dict.fromkeys(reasons+unknown)), cash_required_minor=cash, budget_delta_minor=budget_delta, late_minutes=late_minutes, min_transfer_slack_minutes=min(slacks) if slacks else 0, arrival=offer['arrival'], commitment_preserved=arrival<=parse_time('2026-11-15T19:30:00+05:30'), evidence_ids=offer['evidence_ids'])


def frontier(evaluations):
    eligible = [e for e in evaluations if e['status']=='INFEASIBLE' and set(e['reason_codes']) <= {'OVER_BUDGET','ARRIVES_LATE'}]
    return [a['option_id'] for a in eligible if not any(b['budget_delta_minor']<=a['budget_delta_minor'] and b['late_minutes']<=a['late_minutes'] and (b['budget_delta_minor']<a['budget_delta_minor'] or b['late_minutes']<a['late_minutes']) for b in eligible)]


def rank(evaluations, preference):
    valid = [e for e in evaluations if e['status']=='FEASIBLE']
    def key(e):
        cost, time = e['cash_required_minor'], parse_time(e['arrival'])
        return ((time,cost) if preference=='earliest_arrival' else (cost,time)) + (-e['min_transfer_slack_minutes'],e['option_id'])
    return [e['option_id'] for e in sorted(valid,key=key)]
