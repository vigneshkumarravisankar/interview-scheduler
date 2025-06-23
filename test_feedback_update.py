#!/usr/bin/env python3
"""
Test script for updating interview feedback using natural language input
"""

from app.services.interview_core_service import InterviewCoreService

def test_feedback_update():
    """Test the natural language feedback update functionality"""
    
    print("🚀 Testing Feedback Update for SIVASUBRAMANI K N")
    print("=" * 50)
    
    # Parameters from user request
    candidate_name = "SIVASUBRAMANI K N"
    job_role_name = "Fullstack Developer"
    round_number = 1
    rating = 9
    feedback_text = "Seems to be in good touch with the basics"
    selection_status = "yes"  # will be selected for next round
    
    print(f"📋 Input Parameters:")
    print(f"   • Candidate: {candidate_name}")
    print(f"   • Job Role: {job_role_name}")
    print(f"   • Round: {round_number}")
    print(f"   • Rating: {rating}/10")
    print(f"   • Feedback: {feedback_text}")
    print(f"   • Selected for Next Round: {selection_status}")
    print()
    
    try:
        # First, let's check if the candidate exists
        print("🔍 Checking if candidate exists...")
        candidate = InterviewCoreService.get_candidate_by_name_and_role(
            candidate_name, job_role_name
        )
        
        if candidate:
            print(f"✅ Found candidate: {candidate.get('candidate_name')} - {candidate.get('job_role')}")
            print(f"   • Status: {candidate.get('status')}")
            print(f"   • Completed Rounds: {candidate.get('completedRounds', 0)}")
            print(f"   • Total Rounds: {len(candidate.get('feedback', []))}")
        else:
            print(f"❌ Candidate '{candidate_name}' with role '{job_role_name}' not found")
            print("\n📋 Available candidates:")
            all_candidates = InterviewCoreService.list_candidates_for_feedback()
            for i, c in enumerate(all_candidates[:10], 1):  # Show first 10
                print(f"   {i}. {c.get('candidate_name')} - {c.get('job_role')} ({c.get('status')})")
            return False
        
        print()
        print("🔄 Updating feedback...")
        
        # Update the feedback
        success = InterviewCoreService.update_feedback_by_natural_input(
            candidate_name=candidate_name,
            job_role_name=job_role_name,
            round_number=round_number,
            is_selected_for_next_round=selection_status,
            rating_out_of_10=rating,
            feedback_text=feedback_text
        )
        
        if success:
            print("✅ Feedback updated successfully!")
            
            # Get updated candidate info
            updated_candidate = InterviewCoreService.get_candidate_by_name_and_role(
                candidate_name, job_role_name
            )
            
            if updated_candidate:
                print(f"\n📊 Updated Status:")
                print(f"   • Overall Status: {updated_candidate.get('status')}")
                print(f"   • Completed Rounds: {updated_candidate.get('completedRounds')}/{len(updated_candidate.get('feedback', []))}")
                print(f"   • Next Round Index: {updated_candidate.get('nextRoundIndex')}")
                
                # Show the updated feedback for the round
                feedback_array = updated_candidate.get('feedback', [])
                if round_number <= len(feedback_array):
                    round_feedback = feedback_array[round_number - 1]
                    print(f"\n📝 Round {round_number} Feedback:")
                    print(f"   • Interviewer: {round_feedback.get('interviewer_name')}")
                    print(f"   • Rating: {round_feedback.get('rating_out_of_10')}/10")
                    print(f"   • Selection: {round_feedback.get('isSelectedForNextRound')}")
                    print(f"   • Feedback: {round_feedback.get('feedback')}")
            
        else:
            print("❌ Failed to update feedback")
            
        return success
        
    except Exception as e:
        print(f"❌ Error during feedback update: {e}")
        import traceback
        print(f"📍 Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🎯 Interview Feedback Update Test")
    print("=" * 40)
    
    try:
        result = test_feedback_update()
        print(f"\n🏁 Test Result: {'SUCCESS' if result else 'FAILED'}")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        print(f"📍 Full traceback: {traceback.format_exc()}")
