from calendar_api.oauth import get_calendar_service, get_actual_busy_slots, create_event_with_fallback
from calendar_api.bitmask import generate_time_slots, compute_bitmasks
from mpc.scheduler import secure_bitmask_intersection
import os

# Set email credentials
os.environ["EMAIL_PASSWORD"] = "pypd ixjt cvhj iyql"  # ✅ Make sure this is secured in production

# Participants
INTERVIEWER_EMAILS = [
    "rrvigneshkumar2002@gmail.com",
    "kldhanwanth@gmail.com"
]
CANDIDATE_EMAIL = "sathyaprathap2004@gmail.com"

def main():
    service = get_calendar_service()
    
    # Define time window (UTC)
    start_time = "2025-06-20T09:00:00Z"
    end_time = "2025-06-20T12:00:00Z"

    # Step 1: Fetch busy slots for interviewers
    interviewer_busy_times = []
    for email in INTERVIEWER_EMAILS:
        busy = get_actual_busy_slots(service, calendar_id=email, start_time=start_time, end_time=end_time)
        print(f"📛 Busy slots for {email}: {busy}")
        interviewer_busy_times.append(busy)

    # Step 2: Generate 30-minute time slots in the given window
    time_slots = generate_time_slots(start_time, end_time, 30)
    print("📅 Time Slots:", time_slots)

    # Step 3: Convert to bitmasks for all interviewers
    interviewer_masks = compute_bitmasks(interviewer_busy_times, time_slots)

    # Step 4: Secure intersection to find common free slots
    common = secure_bitmask_intersection(interviewer_masks)
    print("✅ Common Free Slots:", common)

    # Step 5: Choose first available common slot and schedule event
    if 1 in common:
        first_available_index = common.index(1)
        chosen_slot = time_slots[first_available_index]
        print(f"🎯 Chosen Slot: {chosen_slot}")

        event = create_event_with_fallback(service, chosen_slot)
        if event:
            print("✅ Interview scheduled successfully with email notifications sent.")
        else:
            print("❌ Failed to schedule the interview.")
    else:
        print("❌ No common available slot.")

if __name__ == "__main__":
    main()
