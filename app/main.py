import os
from flask import Flask, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, Any, List
from flask_cors import CORS
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in environment.")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Store conversations with expiration tracking
conversation_history = {}

def build_initial_prompt(user_prompt: str, influencer_data: Dict[str, Any]) -> str:
    profile_lines = []
    for key, value in influencer_data.items():
        if isinstance(value, (list, dict)):
            profile_lines.append(f"{key}: {value}")
        else:
            profile_lines.append(f"{key}: {value}")
    profile_section = "\n".join(profile_lines) if profile_lines else "None"

    return f"""
You are writing an email as a representative from InfluAI. Craft an email with:
1. SUBJECT (under 60 chars, attention-grabbing)
2. Two newlines  
3. BODY with:
   - Personalized greeting mentioning their recent work
   - Anchor rate 20% above typical
   - Clear deliverables and perks
   - Urgency and social proof
   - Multiple CTAs
   - No bold formatting (remove ** or any markdown)
   - For contact, use: "DM me @InfluAI" or "email us at hello@influai.com"
   - Maintain professional but friendly tone

--- Influencer Profile ---
{profile_section}

--- User Instruction ---
{user_prompt}

Return EXACTLY:
- First line = SUBJECT
- A blank line
- The full BODY
- No mentions of "top influencer" or similar phrases
- Clean, professional formatting without markdown
""".strip()

def clean_response(text: str) -> str:
    """Clean up the AI response to remove markdown and unwanted phrases."""
    # Remove markdown formatting
    text = text.replace("**", "").replace("*", "")
    # Replace any mentions of top/leading/best influencer
    text = text.replace("top influencer", "team at InfluAI")
    text = text.replace("leading negotiator", "InfluAI representative")
    text = text.replace("best in the business", "InfluAI")
    text = text.replace("Priyansh Arora", "InfluAI team")
    # Ensure consistent contact info
    text = text.replace("@[Your Instagram Handle]", "@InfluAI")
    text = text.replace("@[Insert Instagram Handle]", "@InfluAI")
    text = text.replace("[Your Phone Number]", "hello@influai.com")
    return text.strip()

def cleanup_old_conversations():
    """Remove conversations older than 24 hours"""
    now = datetime.now()
    expired_keys = [
        key for key, value in conversation_history.items()
        if now - value["last_activity"] > timedelta(hours=24)
    ]
    for key in expired_keys:
        del conversation_history[key]

@app.route("/negotiate", methods=["POST"])
def negotiate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    user_prompt = data.get("userPrompt", "").strip()
    influencer_data = data.get("influencerData", {})

    if not user_prompt:
        return jsonify({"error": "'userPrompt' is required."}), 400

    full_prompt = build_initial_prompt(user_prompt, influencer_data)

    try:
        response = model.generate_content(full_prompt)
        
        if not response.text:
            return jsonify({"error": "Empty response from Gemini"}), 500
            
        ai_text = clean_response(response.text.strip())
        
        parts = ai_text.split("\n\n", 1)
        subject = parts[0].strip() if len(parts) > 0 else ""
        body = parts[1].strip() if len(parts) > 1 else ai_text

        return jsonify({
            "subject": subject,
            "body": body
        })

    except Exception as e:
        return jsonify({
            "error": f"Gemini API error: {str(e)}",
            "type": type(e).__name__
        }), 500

@app.route("/negotiate-conversation", methods=["POST"])
def negotiate_conversation():
    cleanup_old_conversations()  # Clean up before processing new request
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    conversation_id = data.get("conversationId")
    user_message = data.get("userMessage", "").strip()
    influencer_data = data.get("influencerData", {})

    if not conversation_id:
        return jsonify({"error": "'conversationId' is required."}), 400
    if not user_message:
        return jsonify({"error": "'userMessage' is required."}), 400

    # Initialize new conversation if needed
    if conversation_id not in conversation_history:
        initial_prompt = build_initial_prompt(
            "Initial negotiation email", 
            influencer_data
        )
        conversation_history[conversation_id] = {
            "history": [
                {"role": "user", "content": initial_prompt},
                {"role": "model", "content": model.generate_content(initial_prompt).text}
            ],
            "last_activity": datetime.now()
        }
    
    # Add user message to history
    conversation_history[conversation_id]["history"].append(
        {"role": "user", "content": user_message}
    )
    conversation_history[conversation_id]["last_activity"] = datetime.now()

    try:
        # Generate response with full context
        response = model.generate_content(
            conversation_history[conversation_id]["history"]
        )
        
        if not response.text:
            return jsonify({"error": "Empty response from Gemini"}), 500
            
        ai_text = clean_response(response.text.strip())
        
        # Add AI response to history
        conversation_history[conversation_id]["history"].append(
            {"role": "model", "content": ai_text}
        )

        return jsonify({
            "response": ai_text,
            "conversationId": conversation_id
        })

    except Exception as e:
        return jsonify({
            "error": f"Gemini API error: {str(e)}",
            "type": type(e).__name__
        }), 500

@app.route("/end-conversation", methods=["POST"])
def end_conversation():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    conversation_id = data.get("conversationId")
    if not conversation_id:
        return jsonify({"error": "'conversationId' is required."}), 400

    if conversation_id in conversation_history:
        del conversation_history[conversation_id]
    
    return jsonify({"status": "success", "message": "Conversation ended"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model": "gemini-1.5-flash",
        "active_conversations": len(conversation_history)
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
