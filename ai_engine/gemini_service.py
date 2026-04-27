"""
Gemini AI Chat Service with Persistent Memory System
=====================================================

This service implements a memory-aware conversational AI using Google's Gemini API.
Every message in a conversation is stored in the database and replayed as context
on each new request, ensuring the AI never loses track of the conversation.

Memory Management Strategy:
1. FULL REPLAY (< 50 messages): All messages are sent as conversation history
2. SUMMARY + RECENT (>= 50 messages): Older messages are summarized into a 
   single system message, then recent messages are appended
3. CONTEXT INJECTION: System prompt includes farmer's land data, soil type,
   crop history, and weather for personalized responses
"""

import logging
import time
from typing import Optional
from django.conf import settings
from google import genai

from .models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)

# ============================================
# Gemini Client (singleton-like)
# ============================================
_client = None


def get_gemini_client():
    """Get or create the Gemini API client."""
    global _client
    if _client is None:
        api_key = settings.GEMINI_API_KEY
        if not api_key or api_key == 'your-gemini-api-key-here':
            raise ValueError(
                "GEMINI_API_KEY is not configured. "
                "Please set it in your .env file."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _candidate_models() -> list[str]:
    """Build an ordered model list: primary, secondary, tertiary, then safe fallbacks."""
    primary = getattr(settings, 'GEMINI_MODEL', '') or 'gemini-2.5-flash'
    secondary = getattr(settings, 'GEMINI_SECONDARY_MODEL', '') or 'gemini-2.5-flash-lite-preview'
    tertiary = getattr(settings, 'GEMINI_TERTIARY_MODEL', '') or 'gemini-2.5-flash'
    # Keep additional known fast models as tail fallbacks for transient saturation.
    fallback_models = [
        'gemini-2.0-flash',
        'gemini-1.5-flash',
    ]
    ordered = [primary, secondary, tertiary, *fallback_models]
    deduped = []
    for model in ordered:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def _generate_with_resilience(client, *, contents, config=None):
    """Try multiple models with small retries to survive transient 503/429 errors."""
    last_error = None
    for model in _candidate_models():
        for attempt in range(3):
            try:
                return client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                last_error = e
                error_text = str(e).lower()
                transient = (
                    '503' in error_text
                    or 'unavailable' in error_text
                    or '429' in error_text
                    or 'exhausted' in error_text
                    or 'deadline exceeded' in error_text
                    or 'timeout' in error_text
                )
                if transient and attempt < 2:
                    # Quick exponential backoff for burst capacity issues.
                    time.sleep(0.7 * (2 ** attempt))
                    continue
                break

    raise RuntimeError(f"Gemini request failed after retries and fallbacks: {last_error}")


# ============================================
# System Prompt Builder
# ============================================
def build_system_prompt(session: ChatSession) -> str:
    """
    Build a context-rich system prompt that includes:
    - Base personality and instructions
    - Farmer's land parcel data (if linked)
    - Crop history and current stages
    - Soil type information
    """

    base_prompt = """You are SofolKrishok AI Assistant — a knowledgeable, friendly agricultural advisor 
for Bangladeshi farmers. You provide expert guidance on farming, crops, diseases, weather, 
soil management, and market trends.

CORE BEHAVIORS:
- Respond in the same language the user writes in (Bengali or English)
- Be practical and specific — farmers need actionable advice, not theory
- When discussing diseases, reference local treatment options available in Bangladesh
- Consider Bangladesh's climate zones, growing seasons, and common crops
- If you recommend pesticides or fertilizers, mention locally available brands when possible
- For weather-related advice, consider the tropical monsoon climate
- Be encouraging and supportive — farming is hard work

IMPORTANT: You have access to the farmer's context below. Use it to give personalized, 
relevant advice. Never say "I don't know your farm details" — you DO know them and do not use any religious greetings"""

    context_parts = [base_prompt]

    # Add land parcel context if session is linked to one
    if session.land_parcel:
        land = session.land_parcel
        context_parts.append(f"""
--- FARMER'S LAND CONTEXT ---
Land Name: {land.name}
Location: {land.location or 'Not specified'}
Area: {land.area_acres or 'Not specified'} acres
Soil Type: {land.soil_type or 'Not classified yet'}
Coordinates: ({land.latitude}, {land.longitude})""")

        # Add crop track history
        tracks = land.crop_tracks.all().prefetch_related('stages')
        if tracks.exists():
            context_parts.append("\n--- CROP HISTORY ---")
            for track in tracks[:5]:  # Last 5 tracks
                context_parts.append(
                    f"• {track.crop_name} ({track.season}) — Status: {track.get_status_display()}"
                )
                current_stages = track.stages.filter(is_current=True)
                if current_stages.exists():
                    stage = current_stages.first()
                    context_parts.append(f"  Current Stage: {stage.title}")
                    if stage.tasks_json:
                        context_parts.append(f"  Pending Tasks: {', '.join(str(t) for t in stage.tasks_json[:3])}")

    # Add conversation summary if exists (for long conversations)
    if session.summary:
        context_parts.append(f"""
--- CONVERSATION SUMMARY (earlier context) ---
{session.summary}""")

    return "\n".join(context_parts)


# ============================================
# History Builder (Memory Replay)
# ============================================
def build_message_history(session: ChatSession) -> list[dict]:
    """
    Build the conversation history to send to Gemini.
    
    Implements a sliding window:
    - If <= CHAT_MAX_HISTORY_MESSAGES: send all messages
    - If > CHAT_MAX_HISTORY_MESSAGES: summarize older messages, send recent ones
    """
    max_messages = getattr(settings, 'CHAT_MAX_HISTORY_MESSAGES', 50)
    messages = session.messages.exclude(role='system').order_by('created_at')
    total = messages.count()

    history = []

    if total <= max_messages:
        # Send ALL messages as history
        for msg in messages:
            role = 'user' if msg.role == 'user' else 'model'
            history.append({
                'role': role,
                'parts': [{'text': msg.content}],
            })
    else:
        # Sliding window: only send the most recent messages
        recent_messages = messages[total - max_messages:]
        for msg in recent_messages:
            role = 'user' if msg.role == 'user' else 'model'
            history.append({
                'role': role,
                'parts': [{'text': msg.content}],
            })

    return history


# ============================================
# Summary Generator (for long conversations)
# ============================================
def generate_conversation_summary(session: ChatSession) -> str:
    """
    Generate a summary of the conversation so far.
    Called when message count exceeds CHAT_SUMMARY_THRESHOLD.
    """
    threshold = getattr(settings, 'CHAT_SUMMARY_THRESHOLD', 40)
    messages = session.messages.exclude(role='system').order_by('created_at')

    if messages.count() <= threshold:
        return session.summary  # No update needed

    # Gather the older messages that need summarization
    older_count = messages.count() - threshold
    older_messages = messages[:older_count]

    # Build a condensed text of older messages
    condensed = []
    for msg in older_messages[:30]:  # Cap at 30 messages for summary input
        prefix = "Farmer" if msg.role == 'user' else "AI"
        condensed.append(f"{prefix}: {msg.content[:200]}")

    conversation_text = "\n".join(condensed)

    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"""Summarize this farming conversation in 3-5 sentences. 
Capture the key topics discussed, any problems identified, advice given, 
and important decisions made. Be concise but preserve critical details.

Conversation:
{conversation_text}""",
        )
        summary = response.text
        session.summary = summary
        session.save(update_fields=['summary'])
        return summary
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        return session.summary


# ============================================
# Main Chat Function
# ============================================
def chat_with_gemini(
    session: ChatSession,
    user_message: str,
    extra_context: Optional[dict] = None,
) -> str:
    """
    Send a message to Gemini with full conversation history (memory).
    
    Flow:
    1. Save user message to DB
    2. Build system prompt with farmer context
    3. Load conversation history from DB
    4. Send everything to Gemini
    5. Save AI response to DB
    6. Trigger summary if needed
    7. Return response
    
    Args:
        session: The ChatSession to use
        user_message: The farmer's new message
        extra_context: Optional dict with additional data (e.g., disease scan result)
    
    Returns:
        The AI assistant's response text
    """

    # 1. Build the context-rich system prompt
    system_prompt = build_system_prompt(session)

    # Add extra context to the system prompt if provided
    if extra_context:
        if 'disease_result' in extra_context:
            system_prompt += f"\n\n--- RECENT DISEASE SCAN ---\n{extra_context['disease_result']}"
        if 'weather_data' in extra_context:
            system_prompt += f"\n\n--- CURRENT WEATHER ---\n{extra_context['weather_data']}"

    # 2. Build conversation history from DB (the memory replay)
    history = build_message_history(session)

    try:
        client = get_gemini_client()

        # 3. Send to Gemini with full context and resilient retries/fallbacks
        response = _generate_with_resilience(
            client,
            contents=[
                *history,
                {'role': 'user', 'parts': [{'text': user_message}]},
            ],
            config={
                'system_instruction': system_prompt,
                'temperature': 0.7,
                'max_output_tokens': 2048,
            },
        )

        assistant_response = (response.text or '').strip()
        if not assistant_response:
            raise RuntimeError('Gemini returned an empty response.')

    except Exception as e:
        error_str = str(e)
        logger.error(f"Gemini API error: {error_str}")

        if "429" in error_str or "exhausted" in error_str.lower():
            raise ValueError(
                "AI quota exceeded right now. Please retry in 1-2 minutes or update Gemini billing/limits."
            )
        if "503" in error_str or "unavailable" in error_str.lower():
            raise ValueError(
                "AI service is temporarily busy (Gemini capacity). Please retry in a few moments."
            )
        raise ValueError(
            "AI service request failed. Please verify GEMINI_API_KEY and GEMINI_MODEL settings."
        )

    # 4. Persist the successful user + assistant exchange
    user_msg_metadata = extra_context or {}
    ChatMessage.objects.create(
        session=session,
        role='user',
        content=user_message,
        metadata=user_msg_metadata,
    )

    ChatMessage.objects.create(
        session=session,
        role='assistant',
        content=assistant_response,
    )

    # 5. Update session timestamp and auto-title if it's the first message
    session.save(update_fields=['updated_at'])

    if session.message_count <= 2 and session.title == "New Chat":
        # Auto-generate a title from the first message
        try:
            title_response = _generate_with_resilience(
                client,
                contents=f"Generate a short title (max 6 words) for a farming conversation that starts with: '{user_message[:100]}'. Return ONLY the title, nothing else.",
            )
            session.title = title_response.text.strip().strip('"')[:255]
            session.save(update_fields=['title'])
        except Exception:
            pass

    # 6. Check if we need to generate a summary for older messages
    threshold = getattr(settings, 'CHAT_SUMMARY_THRESHOLD', 40)
    if session.message_count > threshold and not session.summary:
        # Generate summary in the background (could be Celery task later)
        generate_conversation_summary(session)

    return assistant_response


def auto_title_session(session: ChatSession, first_message: str) -> None:
    """Generate a descriptive title for a chat session based on the first message."""
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"Generate a short title (max 6 words) for a farming conversation that starts with: '{first_message[:200]}'. Return ONLY the title text, no quotes.",
        )
        session.title = response.text.strip().strip('"\'')[:255]
        session.save(update_fields=['title'])
    except Exception as e:
        logger.warning(f"Auto-title failed: {e}")
