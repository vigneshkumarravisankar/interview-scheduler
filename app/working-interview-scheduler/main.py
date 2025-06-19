from calendar_api.oauth import get_calendar_service, get_free_busy, create_event_with_fallback
from calendar_api.bitmask import generate_time_slots, compute_bitmasks
from mpc.scheduler import secure_bitmask_intersection
import os

def main():
    # Set the email password as an environment variable
    # In a real application, you would set this securely, not in code
    os.environ["EMAIL_PASSWORD"] = "pypd ixjt cvhj iyql"  # Replace with your actual App Password

    use_mock = False  # Set to False for real Calendar API

    if use_mock:
        interviewer_busy_times = [
            [{'start': "2025-06-17T09:00:00Z", 'end': "2025-06-20T09:30:00Z"}],
            [{'start': "2025-06-17T09:30:00Z", 'end': "2025-06-20T10:00:00Z"}],
            [{'start': "2025-06-17T10:00:00Z", 'end': "2025-06-20T10:30:00Z"}],
        ]
        service = None  # Mock mode doesn't need this
    else:
        service = get_calendar_service()
        start_time = "2025-06-17T09:00:00Z"
        end_time = "2025-06-20T12:00:00Z"

        calendar_ids = [
            "rvkvigneshkumar02@gmail.com",
            "s.prathap08032004@gmail.com",
            "kldhanwanth@gmail.com"
        ]

        interviewer_busy_times = []
        for cid in calendar_ids:
            busy = get_free_busy(service, start_time, end_time, calendar_id=cid)
            interviewer_busy_times.append(busy)

    # Step 2: Generate 30-minute slots
    time_slots = generate_time_slots("2025-06-17T11:00:00Z", "2025-06-20T12:00:00Z", 30)

    # Step 3: Convert to bitmasks
    interviewer_masks = compute_bitmasks(interviewer_busy_times, time_slots)

    # Step 4: Secure intersection
    common = secure_bitmask_intersection(interviewer_masks)

    print("📅 Time Slots:", time_slots)
    print("✅ Common Free Slots:", common)

    # Step 5: Find and schedule first available slot
    if 1 in common:
        first_available_index = common.index(1)
        chosen_slot = time_slots[first_available_index]
        print(f"🎯 Chosen Slot: {chosen_slot}")

        if not use_mock:
            event = create_event_with_fallback(service, chosen_slot)
            if event:
                print("✅ Interview scheduled successfully with email notifications sent.")
            else:
                print("❌ Failed to schedule the interview.")
    else:
        print("❌ No common available slot.")

if __name__ == "__main__":
    main()