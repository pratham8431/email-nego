import os
from flask import Flask, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv
from typing import Dict, Any

# ----------------------------------------------------------------------------
# 1) Load environment variables
# ----------------------------------------------------------------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("Missing GEMINI_API_KEY in environment.")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ----------------------------------------------------------------------------
# 2) Initialize Flask app
# ----------------------------------------------------------------------------
app = Flask(__name__)

# ----------------------------------------------------------------------------
# 3) Helper: Build negotiation prompt
# ----------------------------------------------------------------------------
def build_negotiation_prompt(user_prompt: str, influencer_data: Dict[str, Any]) -> str:
    profile_lines = []
    for key, value in influencer_data.items():
        if isinstance(value, (list, dict)):
            profile_lines.append(f"{key}: {value}")
        else:
            profile_lines.append(f"{key}: {value}")
    profile_section = "\n".join(profile_lines) if profile_lines else "None"

    return f"""
You are Priyansh Arora, India's most audacious influencer negotiator. Craft an email with:
1. SUBJECT (under 60 chars, attention-grabbing)
2. Two newlines  
3. BODY with:
   - Personalized greeting mentioning their recent work
   - Anchor rate 20% above typical
   - Clear deliverables and perks
   - Urgency and social proof
   - Multiple CTAs

--- Influencer Profile ---
{profile_section}

--- User Instruction ---
{user_prompt}

Return EXACTLY:
- First line = SUBJECT
- A blank line
- The full BODY
""".strip()

# ----------------------------------------------------------------------------
# 4) POST /negotiate
# ----------------------------------------------------------------------------
@app.route("/negotiate", methods=["POST"])
def negotiate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    user_prompt = data.get("userPrompt", "").strip()
    influencer_data = data.get("influencerData", {})

    if not user_prompt:
        return jsonify({"error": "'userPrompt' is required."}), 400

    full_prompt = build_negotiation_prompt(user_prompt, influencer_data)

    try:
        response = model.generate_content(full_prompt)
        
        if not response.text:
            return jsonify({"error": "Empty response from Gemini"}), 500
            
        ai_text = response.text.strip()
        
        # Parse response
        parts = ai_text.split("\n\n", 1)
        subject = parts[0].strip() if len(parts) > 0 else ""
        body = parts[1].strip() if len(parts) > 1 else ai_text

        return jsonify({
            "subject": subject,
            "body": body,
            "full_prompt": full_prompt  # For debugging
        })

    except Exception as e:
        return jsonify({
            "error": f"Gemini API error: {str(e)}",
            "type": type(e).__name__
        }), 500

# ----------------------------------------------------------------------------
# 5) Health check
# ----------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model": "gemini-1.5-flash"
    })

# ----------------------------------------------------------------------------
# 6) Run the app
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
