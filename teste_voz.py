from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key="xxx")
voices = client.voices.get_all()

for v in voices.voices:
    print(v.name, v.voice_id)