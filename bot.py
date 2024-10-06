import discord
from discord.ext import commands
import requests
import yt_dlp
import asyncio
import os
import random

#디스코드/api 토큰 키들
TOKEN = 'MTI4OTgwNDc0MzIwNzU1NTE2Mg.GIQ8Zs.HIyj9iBBVg60ybb0xfEBgewuM5EW04w-oM6kcE'
NEWS_API_KEY = 'fcb4a607ef834352974ce2247eb45839'
YOUTUBE_API_KEY = 'AIzaSyDXTFDsD1oK0rtbfYf-F0LoRwfDJ6LZkwA'

# 쿠키 파일 경로 설정
cookies_file = 'cookies.txt'

# yt-dlp 설정
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'cookiefile': cookies_file,  # 쿠키 파일 사용
    'quiet': True,
    'no_warnings': True,
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# /로 명령 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# 유튜브에서 오디오를 추출하는 클래스
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url']
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# 유튜브 API를 이용해 키워드로 영상을 검색하는 함수
def search_youtube(query):
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&q={query}&key={YOUTUBE_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        search_results = response.json()['items']
        if len(search_results) > 0:
            video_id = search_results[0]['id']['videoId']
            return f"https://www.youtube.com/watch?v={video_id}"
        else:
            return None
    else:
        return None

# 재생 제어를 위한 View 정의
class PlayerControls(discord.ui.View):
    def __init__(self, voice_client):
        super().__init__()
        self.voice_client = voice_client

    @discord.ui.button(label="일시 정지", style=discord.ButtonStyle.primary)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            await interaction.response.send_message("노래를 일시 정지했습니다.", ephemeral=True)

    @discord.ui.button(label="재개", style=discord.ButtonStyle.success)
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            await interaction.response.send_message("노래를 다시 재생합니다.", ephemeral=True)

    @discord.ui.button(label="정지", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.voice_client.stop()
        await interaction.response.send_message("노래를 정지했습니다.", ephemeral=True)

# 봇이 준비되었을 때 실행되는 이벤트
@bot.event
async def on_ready():
    print(f'봇이 로그인되었습니다. {bot.user.name}')

# '/재생' 명령어에 반응하여 유튜브 링크 또는 키워드로 재생하는 기능
@bot.command()
async def 재생(ctx, *, input):
    if not ctx.author.voice:
        await ctx.send("먼저 음성 채널에 들어가 주세요!")
        return

    channel = ctx.author.voice.channel
    voice_client = await channel.connect()

    # 입력이 URL인지 여부를 체크
    if input.startswith("http://") or input.startswith("https://"):
        url = input  # 입력이 유튜브 링크일 경우
    else:
        url = search_youtube(input)  # 입력이 키워드일 경우 유튜브에서 검색

    if url is None:
        await ctx.send(f"'{input}'에 대한 검색 결과를 찾을 수 없습니다.")
        return

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop)
        voice_client.play(player, after=lambda e: print(f'오류 발생: {e}') if e else None)

    await ctx.send(f"지금 재생 중: {player.title}", view=PlayerControls(voice_client))

# '/안녕' 명령어에 반응하는 기능
@bot.command()
async def 안녕(ctx):
    await ctx.send(f'{ctx.author.mention} 안녕?')

# 봇 실행
bot.run(TOKEN)