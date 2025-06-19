# calendar_api/bitmask.py

from datetime import datetime, timedelta

def generate_time_slots(start_time_str, end_time_str, slot_duration_minutes=30):
    time_format = "%Y-%m-%dT%H:%M:%SZ"
    start_dt = datetime.strptime(start_time_str, time_format)
    end_dt = datetime.strptime(end_time_str, time_format)

    slots = []
    current = start_dt
    while current + timedelta(minutes=slot_duration_minutes) <= end_dt:
        slot_start = current.strftime(time_format)
        slot_end = (current + timedelta(minutes=slot_duration_minutes)).strftime(time_format)
        slots.append((slot_start, slot_end))
        current += timedelta(minutes=slot_duration_minutes)

    return slots


from datetime import datetime, timedelta

def compute_bitmasks(busy_times_list, time_slots):
    time_format = "%Y-%m-%dT%H:%M:%SZ"
    bitmasks = []

    for busy_times in busy_times_list:
        bitmask = []
        for slot in time_slots:
            slot_start_str, slot_end_str = slot
            slot_start = datetime.strptime(slot_start_str, time_format)
            slot_end = datetime.strptime(slot_end_str, time_format)

            is_busy = False
            for busy in busy_times:
                busy_start = datetime.strptime(busy["start"], time_format)
                busy_end = datetime.strptime(busy["end"], time_format)

                # Check overlap
                if slot_start < busy_end and slot_end > busy_start:
                    is_busy = True
                    break

            bitmask.append(0 if is_busy else 1)
        bitmasks.append(bitmask)

    return bitmasks


def pick_first_available_slot(bitmask):
    for i, val in enumerate(bitmask):
        if val == 1:
            return i
    return None
