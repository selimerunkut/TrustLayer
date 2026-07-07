# TrustLayer voice demo transcript

- Sent a manual typed chat message to the live TrustLayer voice endpoint on `https://trustlayer.37-27-94-136.sslip.io/api/betty/voice-chat`.
- Received a contextual assistant reply for a Rome trip planning prompt.
- Sent the reply through `/api/betty/voice-ui-turn` and confirmed the transcript sync route returned `200 OK`.
- Hit `/api/betty/tts` and observed a deployed-environment `invalid_api_key` failure from ElevenLabs.
- Verified the frontend now falls back to native browser speech synthesis so the assistant can still speak audibly when the TTS provider is unavailable.
- Saved the evidence in `tests/manual/trustlayer-voice-evidence-bundle.json`.
