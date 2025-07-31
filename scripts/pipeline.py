from datetime import datetime, timezone
import os, yaml, openai, requests, subprocess, datetime, uuid, pathlib
from feedgen.feed import FeedGenerator

root = pathlib.Path(__file__).parent.parent
eps = yaml.safe_load((root/'prompts/episodios.yml').read_text())
ep = next((e for e in eps if e['estado']=='pendiente'), None)
if not ep:
    quit()

# 1· Generar guion
openai.api_key = os.getenv("OPENAI_API_KEY")
guion = openai.ChatCompletion.create(
    model="gpt-4o-mini",
    messages=[{"role":"user","content": ep['prompt']}]
).choices[0].message.content

# 2· Texto → voz
audio = root/f"audio/{ep['id']}.mp3"; audio.parent.mkdir(exist_ok=True)
r = requests.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{os.getenv('VOICE_ID')}/stream",
    headers={"xi-api-key": os.getenv("EL_API_KEY")},
    json={"text": guion, "model_id": "eleven_multilingual_v2"}
)
if r.status_code != 200:
    print("ElevenLabs error:", r.status_code, r.text)
    raise SystemExit("TTS failed")
audio.write_bytes(r.content)

# 3· Normalizar LUFS
tmp = audio.with_suffix('.tmp.mp3')
subprocess.run(["ffmpeg","-y","-i", audio,
               "-af","loudnorm=I=-14:TP=-1:LRA=7", tmp], check=True)
tmp.replace(audio)

# 4· Actualizar RSS
fg, rss = FeedGenerator(), root/'feed.xml'
fg.title("Autopodcast de Avenida")
fg.link(href=os.getenv('FEED_URL').rsplit('/',1)[0], rel='self')
fg.description("Podcast generado automáticamente con IA")
# if rss.exists():
#   fg.parse_feed(rss.read_text())
base = os.getenv('FEED_URL').rsplit('/',1)[0]
it = fg.add_entry()
it.id(str(uuid.uuid4()))
it.title(ep['titulo'])
it.description(guion[:160])
it.enclosure(f"{base}/audio/{audio.name}", str(audio.stat().st_size), 'audio/mpeg')
it.pubDate(datetime.datetime.now(datetime.timezone.utc))
fg.rss_file(rss)

# 5· Marcar publicado
ep['estado'] = 'publicado'
(root/'prompts/episodios.yml').write_text(yaml.dump(eps, allow_unicode=True))
